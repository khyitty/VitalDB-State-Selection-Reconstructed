"""Run Phase 6C from checksum-verified Phase 6A raw signals without network I/O."""

from __future__ import annotations

import argparse
import csv
import gc
import gzip
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.causal_grid_feasibility import (  # noqa: E402
    BIS_STALENESS_CAPS,
    DRUG_HOLD_CAPS,
    EXPECTED_CASE_COUNT,
    EXPECTED_SOURCE_RAW_COUNT,
    MINIMUM_WINDOW_COUNTS,
    PHASE6C_SEED,
    SQI_RULES,
    TRACK_NAMES,
    all_candidate_ids,
    audit_case,
    candidate_id,
    parse_observation_index,
)
from vitaldb_state_selection.cohort.primary_signal_quality import distribution, sha256_path  # noqa: E402


MANIFESTS = ROOT / "data" / "manifests"
RAW_ROOT = ROOT / "data" / "raw" / "phase6a_primary_signals"
LEGACY_ROOT = ROOT.parent / "VitalDB-Feature-Selection"
PHASE6B_PHASE_COMMIT = "d3bc24f975484e173da237b756c22dca8d897d54"
PHASE6B_VERIFIED_REMOTE = "30064de6ee4eeea44b5a220be1e5f6ba7c53b4e4"
MEMORY_ABORT_BYTES = 2 * 1024**3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 6C causal-grid feasibility audit")
    parser.add_argument(
        "--memory-abort-bytes", type=int, default=MEMORY_ABORT_BYTES,
        help="engineering-only peak RSS abort guard; never an eligibility rule",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def csv_value(value: object) -> object:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (list, tuple, dict, set)):
        normalized = sorted(value) if isinstance(value, set) else value
        return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=isinstance(value, dict))
    return value


def atomic_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty CSV: {path}")
    fields = list(rows[0]) + sorted({field for row in rows for field in row} - set(rows[0]))
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: csv_value(row.get(field)) for field in fields})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


class AtomicGzipCsv:
    def __init__(self, destination: Path, fields: list[str]) -> None:
        self.destination = destination
        self.fields = fields
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
        os.close(descriptor)
        self.temporary = Path(name)
        self.binary = self.temporary.open("wb")
        self.gzip = gzip.GzipFile(filename="", mode="wb", fileobj=self.binary, mtime=0)
        self.text = __import__("io").TextIOWrapper(self.gzip, encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.text, fieldnames=fields)
        self.writer.writeheader()

    def write(self, row: dict[str, object]) -> None:
        self.writer.writerow({field: csv_value(row.get(field)) for field in self.fields})

    def finish(self) -> None:
        self.text.flush()
        self.text.detach()
        self.gzip.close()
        self.binary.flush()
        os.fsync(self.binary.fileno())
        self.binary.close()

    def publish(self) -> None:
        os.replace(self.temporary, self.destination)

    def abort(self) -> None:
        for stream in (self.text, self.gzip, self.binary):
            try:
                stream.close()
            except Exception:
                pass
        self.temporary.unlink(missing_ok=True)


def raw_tree_state() -> dict[str, object]:
    files = sorted(path for path in RAW_ROOT.rglob("*") if path.is_file())
    entries = [f"{path.relative_to(RAW_ROOT).as_posix()}\t{path.stat().st_size}" for path in files]
    return {
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "relative_path_and_size_fingerprint_sha256": hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest(),
        "partial_file_count": sum(path.suffix == ".part" for path in files),
    }


def legacy_state() -> dict[str, object]:
    safe = LEGACY_ROOT.resolve().as_posix()

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={safe}", "-C", str(LEGACY_ROOT), *args],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()

    return {
        "head": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "status_short": git("status", "--short").splitlines(),
    }


def current_peak_rss_bytes() -> int:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.argtypes = []
        get_current_process.restype = wintypes.HANDLE
        get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        get_process_memory_info.restype = wintypes.BOOL
        if not get_process_memory_info(
            get_current_process(), ctypes.byref(counters), counters.cb
        ):
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize)
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system() == "Darwin" else value * 1024)


def verify_raw(downloads: list[dict[str, str]]) -> dict[str, object]:
    fingerprint_rows: list[str] = []
    total_bytes = 0
    for number, row in enumerate(downloads, start=1):
        path = RAW_ROOT / row["raw_relative_path"]
        if not path.is_file():
            raise RuntimeError(f"missing Phase 6A raw file: {row['raw_relative_path']}")
        size = path.stat().st_size
        checksum = sha256_path(path)
        if size != int(row["raw_byte_count"]) or checksum != row["raw_sha256"]:
            raise RuntimeError(f"raw checksum mismatch: {row['caseid']} {row['track_name']}")
        total_bytes += size
        fingerprint_rows.append(f"{row['caseid']}|{row['track_name']}|{size}|{checksum}")
        if number % 1000 == 0:
            print(f"source checksum progress {number}/{len(downloads)}", flush=True)
    return {
        "verified_file_count": len(downloads),
        "verified_total_bytes": total_bytes,
        "manifest_order_fingerprint_sha256": hashlib.sha256(("\n".join(fingerprint_rows) + "\n").encode()).hexdigest(),
    }


def parse_number(text: str) -> tuple[float | None, bool, bool]:
    if not text.strip():
        return None, True, False
    try:
        value = float(text)
    except ValueError:
        return None, False, True
    return (value if math.isfinite(value) else None), False, not math.isfinite(value)


def demographics_manifest(metadata: list[dict[str, str]], included: set[int]) -> tuple[list[dict[str, object]], dict[str, object]]:
    source = {int(row["caseid"]): row for row in metadata}
    if len(source) != 6388 or not included <= set(source):
        raise RuntimeError("complete metadata source or included Phase 6C IDs are missing")
    result: list[dict[str, object]] = []
    exact_counts = {field: Counter() for field in ("age", "sex", "height", "weight")}
    for caseid in sorted(included):
        row = source[caseid]
        numeric: dict[str, float | None] = {}
        missing: dict[str, bool] = {}
        nonfinite: dict[str, bool] = {}
        for field in ("age", "height", "weight"):
            numeric[field], missing[field], nonfinite[field] = parse_number(row[field])
            exact_counts[field][row[field]] += 1
        exact_counts["sex"][row["sex"]] += 1
        sex_present = bool(row["sex"].strip())
        sex_resolvable = row["sex"] in {"M", "F"}
        all_present = not any(missing.values()) and sex_present
        height_positive = numeric["height"] is not None and numeric["height"] > 0
        weight_positive = numeric["weight"] is not None and numeric["weight"] > 0
        pk_basic = (
            numeric["age"] is not None and sex_resolvable
            and height_positive and weight_positive
        )
        result.append({
            "caseid": caseid,
            "age_source_value": row["age"], "sex_source_value": row["sex"],
            "height_source_value": row["height"], "weight_source_value": row["weight"],
            "age_numeric": numeric["age"], "height_numeric": numeric["height"],
            "weight_numeric": numeric["weight"],
            "age_missing": missing["age"], "sex_missing": not sex_present,
            "height_missing": missing["height"], "weight_missing": missing["weight"],
            "age_nonfinite_or_nonnumeric": nonfinite["age"],
            "height_nonfinite_or_nonnumeric": nonfinite["height"],
            "weight_nonfinite_or_nonnumeric": nonfinite["weight"],
            "all_four_demographics_present": all_present,
            "sex_encoding_resolvable": sex_resolvable,
            "height_positive": height_positive, "weight_positive": weight_positive,
            "schnider_minto_basic_numeric_inputs_present": pk_basic,
            "pk_parameters_computed": False, "lean_body_mass_computed": False,
            "automatic_exclusion": False,
        })
    summary: dict[str, object] = {"case_count": len(result), "variables": {}}
    for field in ("age", "sex", "height", "weight"):
        item: dict[str, object] = {
            "exact_source_value_counts": dict(sorted(exact_counts[field].items())),
            "missing_count": sum(bool(row[f"{field}_missing"]) for row in result),
        }
        if field != "sex":
            item["nonfinite_or_nonnumeric_count"] = sum(bool(row[f"{field}_nonfinite_or_nonnumeric"]) for row in result)
            item["numeric_distribution"] = distribution([row[f"{field}_numeric"] for row in result])
        summary["variables"][field] = item
    summary["flag_counts"] = {
        field: sum(bool(row[field]) for row in result)
        for field in (
            "all_four_demographics_present", "sex_encoding_resolvable",
            "height_positive", "weight_positive", "schnider_minto_basic_numeric_inputs_present",
        )
    }
    return result, summary


def sample_boundaries(members: dict[str, list[int]]) -> list[dict[str, object]]:
    rng = random.Random(PHASE6C_SEED)
    rows: list[dict[str, object]] = []
    for category in sorted(members):
        caseids = sorted(set(members[category]))
        for caseid in sorted(rng.sample(caseids, min(5, len(caseids)))):
            rows.append({
                "category": category, "caseid": caseid,
                "category_case_count": len(caseids), "seed": PHASE6C_SEED,
                "automatic_inclusion_or_exclusion": False,
            })
    return rows


def render_report(summary: dict[str, object]) -> str:
    candidates = summary["candidate_aggregate"]
    minimum = min(candidates, key=lambda row: row["usable_case_count"])
    maximum = max(candidates, key=lambda row: row["usable_case_count"])
    demo = summary["demographics_pk_input_feasibility"]
    lines = [
        "# Phase 6C Causal Grid and Prediction-Window Feasibility Audit", "",
        "## Scope and accounting", "",
        f"- Source cases: `{summary['case_count']}`; exact candidate combinations: `{summary['candidate_count']}`.",
        f"- Case×candidate rows: `{summary['case_candidate_row_count']}`.",
        "- Only checksum-verified Phase 6A BIS/BIS, BIS/SQI, PPF20_RATE, and RFTN20_RATE files were read.",
        "- No API request, new raw file, modeling array, outcome, split, model, Cp/Ce, dose, feature selection, or PPO execution occurred.", "",
        "## Fixed causal structure", "",
        "The 10-second grid is anchored to each case's anesthesia start. History is t-50 through t in 10-second steps and the target is t+30. Every lookup requires timestamp <= grid time; all eight time points remain inside the same case, anesthesia window, and inherited common observed span.",
        "BIS uses the descriptive 0-100 range, including 0-10. Required SQI is joined only at the exact BIS timestamp and remains QC-only. Drug rates use the most recent finite observation, never assume pre-observation zero, never use negative values, and apply only the candidate finite hold caps.", "",
        "Raw rows were not sorted, deduplicated, averaged, resampled, interpolated, smoothed, clipped, or filled. A derived chronological lookup index preserves the last finite raw-row value at duplicated timestamps; duplicate-derived grid uses are flagged.", "",
        "## Candidate comparison — descriptive only", "",
        f"The smallest usable-case count among the 60 unselected candidates was `{minimum['usable_case_count']}` (`{minimum['candidate_id']}`); the largest was `{maximum['usable_case_count']}` (`{maximum['candidate_id']}`).",
        "These extrema are feasibility descriptions, not recommendations or a selected preprocessing rule.", "",
        "## Minimum-window sensitivity", "",
        "The 30, 60, 120, 300, and 600 endpoint counts are compared independently. Their approximate minute labels do not assert continuous usable duration.", "",
        "## Phase 6B scenario comparison", "",
        "Permissive, moderate, and strict Phase 6B flags are compared with actual causal-window counts for every candidate and minimum-window threshold. Cases failing moderate/strict because of BIS 10-100 fractions are separately counted; BIS 0-10 remains admissible in this audit.", "",
        "## Static demographics and PK-input feasibility", "",
        f"All-four-demographics-present: `{demo['flag_counts']['all_four_demographics_present']}`; Schnider/Minto basic-input feasibility flag: `{demo['flag_counts']['schnider_minto_basic_numeric_inputs_present']}`.",
        "No clinical plausibility cutoff, PK parameter, lean-body-mass value, Cp/Ce value, or demographic exclusion was calculated.", "",
        "## Boundary review", "",
        f"Fixed seed `{PHASE6C_SEED}` supplies at most five IDs per requested boundary category. Samples do not change inclusion or exclusion.", "",
        "## Decision boundary", "",
        "No SQI rule, BIS staleness cap, drug hold cap, minimum-window threshold, Phase 6B scenario, preprocessing rule, quality threshold, or final cohort was selected. Protocol v1.2, cohort freeze, split, and modeling remain outside Phase 6C.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if args.memory_abort_bytes <= 0:
        raise ValueError("memory abort guard must be positive")
    candidates = all_candidate_ids()
    if len(candidates) != 60 or len(set(candidates)) != 60:
        raise RuntimeError("candidate matrix is not exactly 60 unique combinations")

    raw_before = raw_tree_state()
    legacy_before = legacy_state()
    downloads = read_csv(MANIFESTS / "primary_signal_download_manifest.csv")
    if len(downloads) != EXPECTED_SOURCE_RAW_COUNT:
        raise RuntimeError("Phase 6A download manifest is not 9,880 rows")
    source_keys = {(int(row["caseid"]), row["track_name"]) for row in downloads}
    included = {caseid for caseid, _ in source_keys}
    if len(included) != EXPECTED_CASE_COUNT or len(source_keys) != EXPECTED_SOURCE_RAW_COUNT:
        raise RuntimeError("Phase 6A source case×track accounting mismatch")
    if {track for _, track in source_keys} != set(TRACK_NAMES):
        raise RuntimeError("source track scope is outside the four exact Phase 6C tracks")
    if any(row["download_status"] != "complete" for row in downloads):
        raise RuntimeError("Phase 6C requires every Phase 6A source row complete")

    input_names = (
        "pre_quality_acquisition_cohort.csv", "primary_signal_download_manifest.csv",
        "primary_signal_checksum_manifest.csv", "primary_signal_source_snapshot.json",
        "primary_signal_quality_case_manifest.csv", "primary_signal_quality_track_manifest.csv",
        "primary_signal_quality_summary.json", "primary_signal_quality_source_snapshot.json",
        "all_case_eligibility_manifest.csv",
    )
    input_checksums = {name: sha256_path(MANIFESTS / name) for name in input_names}
    phase6b_inventory = json.loads((MANIFESTS / "primary_signal_quality_artifact_checksums.json").read_text(encoding="utf-8"))
    for relative, expected in phase6b_inventory.items():
        if sha256_path(ROOT / relative) != expected:
            raise RuntimeError(f"Phase 6B source artifact checksum mismatch: {relative}")

    phase6b_cases_list = read_csv(MANIFESTS / "primary_signal_quality_case_manifest.csv")
    phase6b_tracks = read_csv(MANIFESTS / "primary_signal_quality_track_manifest.csv")
    phase6b_summary = json.loads((MANIFESTS / "primary_signal_quality_summary.json").read_text(encoding="utf-8"))
    phase6b_cases = {int(row["caseid"]): row for row in phase6b_cases_list}
    if set(phase6b_cases) != included or len(phase6b_tracks) != EXPECTED_SOURCE_RAW_COUNT:
        raise RuntimeError("Phase 6B source manifests do not account for Phase 6C universe")
    if phase6b_summary["case_count"] != EXPECTED_CASE_COUNT or phase6b_summary["selected_scenario"] is not None:
        raise RuntimeError("Phase 6B summary boundary mismatch")

    metadata = read_csv(MANIFESTS / "all_case_eligibility_manifest.csv")
    demographics, demographics_summary = demographics_manifest(metadata, included)
    demographics_by_case = {int(row["caseid"]): row for row in demographics}
    rows_by_case: dict[int, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in downloads:
        rows_by_case[int(row["caseid"])][row["track_name"]] = row

    print("verifying Phase 6A raw checksums before analysis", flush=True)
    checksum_before = verify_raw(downloads)
    if raw_before["partial_file_count"] != 0:
        raise RuntimeError("partial file exists before Phase 6C")

    case_candidate_path = MANIFESTS / "causal_grid_feasibility_case_candidate_manifest.csv.gz"
    fields = [
        "caseid", "candidate_id", "sqi_rule", "bis_staleness_cap_seconds",
        "drug_hold_cap_seconds", "grid_anchor", "grid_interval_seconds",
        "total_common_span_grid_points", "total_candidate_grid_points",
        "usable_history_endpoints", "usable_target_points", "total_usable_windows",
        "zero_window_case", "failure_history_bis_unavailable",
        "failure_history_propofol_unavailable", "failure_history_remifentanil_unavailable",
        "failure_target_bis_unavailable", "overlapping_failure_reason_counts",
        "duplicate_timestamp_affected_endpoint_count", "any_duplicate_timestamp_affected_endpoint",
        "raw_zero_interval_warning", "raw_negative_interval_warning",
        "future_timestamp_use_count", "cross_case_connection_count",
        "modeling_array_saved", "selected",
    ]
    writer = AtomicGzipCsv(case_candidate_path, fields)
    window_counts: dict[str, list[int]] = {identifier: [] for identifier in candidates}
    aggregate: dict[str, Counter[str]] = {identifier: Counter() for identifier in candidates}
    aggregate_overlaps: dict[str, Counter[str]] = {identifier: Counter() for identifier in candidates}
    usable_bitsets = {identifier: 0 for identifier in candidates}
    rate_aggregate: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    boundary_members = {name: [] for name in (
        "no_usable_window_under_all_60_combinations",
        "usable_only_with_sqi_not_required",
        "usable_with_sqi_ge_20_but_not_sqi_ge_50",
        "usable_with_sqi_ge_50_but_not_sqi_ge_80",
        "usable_only_with_bis_staleness_30s",
        "usable_only_with_drug_hold_ge_300s",
        "phase6b_moderate_fail_but_at_least_120_usable_windows",
        "phase6b_strict_fail_but_at_least_120_usable_windows",
        "duplicate_timestamp_affected_grid",
        "missing_demographic_input", "unresolved_sex_encoding",
        "nonpositive_height_or_weight",
    )}
    max_peak = current_peak_rss_bytes()
    try:
        for case_number, caseid in enumerate(sorted(included), start=1):
            source_case = phase6b_cases[caseid]
            source_rows = rows_by_case[caseid]
            if set(source_rows) != set(TRACK_NAMES):
                raise RuntimeError(f"case {caseid} lacks four source files")
            anesthesia_start = float(source_case["anesthesia_start"])
            anesthesia_end = float(source_case["anesthesia_end"])
            common_start = float(source_case["common_observed_span_start"]) if source_case["common_observed_span_start"] else None
            common_end = float(source_case["common_observed_span_end"]) if source_case["common_observed_span_end"] else None
            indexes = {
                track: parse_observation_index(
                    RAW_ROOT / source_rows[track]["raw_relative_path"],
                    expected_track_name=track,
                    anesthesia_start=anesthesia_start,
                    anesthesia_end=anesthesia_end,
                )
                for track in TRACK_NAMES
            }
            case_rows, rate_counts = audit_case(
                caseid=caseid, anesthesia_start=anesthesia_start, anesthesia_end=anesthesia_end,
                common_start=common_start, common_end=common_end, indexes=indexes,
            )
            usable_rows = [row for row in case_rows if int(row["total_usable_windows"]) > 0]
            by_sqi = {rule: any(row["sqi_rule"] == rule for row in usable_rows) for rule in SQI_RULES}
            if not usable_rows:
                boundary_members["no_usable_window_under_all_60_combinations"].append(caseid)
            if by_sqi["sqi_not_required"] and not any(by_sqi[rule] for rule in SQI_RULES[1:]):
                boundary_members["usable_only_with_sqi_not_required"].append(caseid)
            if by_sqi["sqi_ge_20"] and not by_sqi["sqi_ge_50"] and not by_sqi["sqi_ge_80"]:
                boundary_members["usable_with_sqi_ge_20_but_not_sqi_ge_50"].append(caseid)
            if by_sqi["sqi_ge_50"] and not by_sqi["sqi_ge_80"]:
                boundary_members["usable_with_sqi_ge_50_but_not_sqi_ge_80"].append(caseid)
            if usable_rows and all(int(row["bis_staleness_cap_seconds"]) == 30 for row in usable_rows):
                boundary_members["usable_only_with_bis_staleness_30s"].append(caseid)
            if usable_rows and all(int(row["drug_hold_cap_seconds"]) >= 300 for row in usable_rows):
                boundary_members["usable_only_with_drug_hold_ge_300s"].append(caseid)
            max_windows = max((int(row["total_usable_windows"]) for row in case_rows), default=0)
            if source_case["scenario_moderate_passes"] == "false" and max_windows >= 120:
                boundary_members["phase6b_moderate_fail_but_at_least_120_usable_windows"].append(caseid)
            if source_case["scenario_strict_passes"] == "false" and max_windows >= 120:
                boundary_members["phase6b_strict_fail_but_at_least_120_usable_windows"].append(caseid)
            if any(row["any_duplicate_timestamp_affected_endpoint"] for row in case_rows):
                boundary_members["duplicate_timestamp_affected_grid"].append(caseid)
            demo = demographics_by_case[caseid]
            if not demo["all_four_demographics_present"]:
                boundary_members["missing_demographic_input"].append(caseid)
            if not demo["sex_encoding_resolvable"]:
                boundary_members["unresolved_sex_encoding"].append(caseid)
            if not demo["height_positive"] or not demo["weight_positive"]:
                boundary_members["nonpositive_height_or_weight"].append(caseid)

            for row in case_rows:
                writer.write(row)
                identifier = str(row["candidate_id"])
                windows = int(row["total_usable_windows"])
                window_counts[identifier].append(windows)
                if windows > 0:
                    usable_bitsets[identifier] |= 1 << (case_number - 1)
                for field in (
                    "total_candidate_grid_points", "usable_history_endpoints", "usable_target_points",
                    "total_usable_windows", "failure_history_bis_unavailable",
                    "failure_history_propofol_unavailable", "failure_history_remifentanil_unavailable",
                    "failure_target_bis_unavailable", "duplicate_timestamp_affected_endpoint_count",
                    "future_timestamp_use_count", "cross_case_connection_count",
                ):
                    aggregate[identifier][field] += int(row[field])
                aggregate_overlaps[identifier].update(row["overlapping_failure_reason_counts"])
            for key, counts in rate_counts.items():
                rate_aggregate[key].update(counts)
            del indexes, case_rows, rate_counts, usable_rows
            gc.collect()
            max_peak = max(max_peak, current_peak_rss_bytes())
            if max_peak > args.memory_abort_bytes:
                raise MemoryError(f"peak RSS {max_peak} exceeded engineering abort guard {args.memory_abort_bytes}")
            if case_number % 50 == 0 or case_number == EXPECTED_CASE_COUNT:
                print(f"causal-grid progress {case_number}/{EXPECTED_CASE_COUNT}; peak_rss={max_peak}", flush=True)
        writer.finish()
    except BaseException:
        writer.abort()
        raise

    candidate_rows: list[dict[str, object]] = []
    for identifier in candidates:
        values = window_counts[identifier]
        if len(values) != EXPECTED_CASE_COUNT:
            raise RuntimeError(f"candidate {identifier} lacks 2,470 case rows")
        parts = identifier.split("__")
        counts = aggregate[identifier]
        candidate_rows.append({
            "candidate_id": identifier, "sqi_rule": parts[0],
            "bis_staleness_cap_seconds": int(parts[1][3:-1]),
            "drug_hold_cap_seconds": int(parts[2][4:-1]),
            "case_count": EXPECTED_CASE_COUNT,
            "total_candidate_grid_points": counts["total_candidate_grid_points"],
            "usable_history_endpoints": counts["usable_history_endpoints"],
            "usable_target_points": counts["usable_target_points"],
            "total_usable_windows": counts["total_usable_windows"],
            "usable_case_count": sum(value > 0 for value in values),
            "zero_window_cases": sum(value == 0 for value in values),
            "patient_window_count_distribution": distribution(values),
            "failure_reason_counts": {
                key.removeprefix("failure_"): counts[key]
                for key in (
                    "failure_history_bis_unavailable", "failure_history_propofol_unavailable",
                    "failure_history_remifentanil_unavailable", "failure_target_bis_unavailable",
                )
            },
            "overlapping_failure_reason_counts": dict(sorted(aggregate_overlaps[identifier].items())),
            "duplicate_timestamp_affected_endpoint_count": counts["duplicate_timestamp_affected_endpoint_count"],
            "future_timestamp_use_count": counts["future_timestamp_use_count"],
            "cross_case_connection_count": counts["cross_case_connection_count"],
            "selected": False, "recommended": False,
        })

    minimum_rows: list[dict[str, object]] = []
    for identifier in candidates:
        for threshold in MINIMUM_WINDOW_COUNTS:
            passed = sum(value >= threshold for value in window_counts[identifier])
            minimum_rows.append({
                "candidate_id": identifier, "minimum_usable_windows": threshold,
                "pass_case_count": passed, "fail_case_count": EXPECTED_CASE_COUNT - passed,
                "pass_fraction": passed / EXPECTED_CASE_COUNT,
                "approximate_minutes_of_10s_endpoints": threshold / 6,
                "is_continuous_duration_claim": False, "selected": False,
            })

    disagreement_rows: list[dict[str, object]] = []
    for left in candidates:
        for right in candidates:
            count = (usable_bitsets[left] ^ usable_bitsets[right]).bit_count()
            disagreement_rows.append({
                "candidate_left": left, "candidate_right": right,
                "classification": "at_least_one_usable_window",
                "disagreement_case_count": count,
                "disagreement_fraction": count / EXPECTED_CASE_COUNT,
            })

    scenario_rows: list[dict[str, object]] = []
    ordered_caseids = sorted(included)
    for scenario in ("permissive", "moderate", "strict"):
        phase_pass = [phase6b_cases[caseid][f"scenario_{scenario}_passes"] == "true" for caseid in ordered_caseids]
        phase_reasons = [json.loads(phase6b_cases[caseid][f"scenario_{scenario}_failure_reasons"]) for caseid in ordered_caseids]
        for identifier in candidates:
            values = window_counts[identifier]
            zero_with_scenario_pass = sum(passed and value == 0 for passed, value in zip(phase_pass, values))
            for threshold in MINIMUM_WINDOW_COUNTS:
                window_pass = [value >= threshold for value in values]
                fail_but_window = [index for index, (p, w) in enumerate(zip(phase_pass, window_pass)) if not p and w]
                reasons = Counter(reason for index in fail_but_window for reason in phase_reasons[index])
                scenario_rows.append({
                    "phase6b_scenario": scenario, "candidate_id": identifier,
                    "minimum_usable_windows": threshold,
                    "scenario_pass_but_zero_usable_window": zero_with_scenario_pass,
                    "scenario_pass_but_below_minimum": sum(p and not w for p, w in zip(phase_pass, window_pass)),
                    "scenario_fail_but_meets_minimum": len(fail_but_window),
                    "both_pass": sum(p and w for p, w in zip(phase_pass, window_pass)),
                    "both_fail": sum(not p and not w for p, w in zip(phase_pass, window_pass)),
                    "scenario_failure_reasons_among_fail_but_meets_minimum": dict(sorted(reasons.items())),
                    "bis_10_100_fraction_reason_but_meets_minimum": sum(
                        any(reason.startswith("bis_10_100_fraction") for reason in phase_reasons[index])
                        for index in fail_but_window
                    ),
                    "selected": False,
                })

    rate_rows: list[dict[str, object]] = []
    for track in ("Orchestra/PPF20_RATE", "Orchestra/RFTN20_RATE"):
        for cap in DRUG_HOLD_CAPS:
            counts = rate_aggregate[(track, cap)]
            total = counts["total_grid_points"]
            rate_rows.append({
                "track_name": track, "hold_cap_seconds": cap,
                "total_grid_points": total, "usable_grid_points": counts["usable_grid_points"],
                "unavailable_grid_points": counts["unavailable_grid_points"],
                "usable_grid_fraction": counts["usable_grid_points"] / total if total else None,
                "unavailable_grid_fraction": counts["unavailable_grid_points"] / total if total else None,
                "positive_grid_points": counts["usable_positive"],
                "zero_grid_points": counts["usable_zero"],
                "positive_grid_fraction": counts["usable_positive"] / total if total else None,
                "zero_grid_fraction": counts["usable_zero"] / total if total else None,
                "unavailable_due_hold_cap": counts["unavailable_hold_cap_exceeded"],
                "unavailable_due_negative_latest": counts["unavailable_latest_finite_negative"],
                "unavailable_no_prior_finite": counts["unavailable_no_prior_finite_observation"],
                "duplicate_timestamp_observation_used": counts["duplicate_timestamp_observation_used"],
                "selected": False,
            })

    boundary_rows = sample_boundaries(boundary_members)
    print("verifying Phase 6A raw checksums after analysis", flush=True)
    checksum_after = verify_raw(downloads)
    raw_after = raw_tree_state()
    legacy_after = legacy_state()
    if checksum_before != checksum_after:
        raise RuntimeError("Phase 6A raw checksum fingerprint changed during Phase 6C")
    if raw_before != raw_after:
        raise RuntimeError("Phase 6A raw tree changed during Phase 6C")
    if legacy_before != legacy_after:
        raise RuntimeError("legacy repository state changed during Phase 6C")
    if raw_after["partial_file_count"] != 0:
        raise RuntimeError("partial file exists after Phase 6C")
    if any(row["future_timestamp_use_count"] or row["cross_case_connection_count"] for row in candidate_rows):
        raise RuntimeError("causal or case boundary invariant failed")
    writer.publish()

    candidate_path = MANIFESTS / "causal_grid_candidate_summary.csv"
    minimum_path = MANIFESTS / "causal_grid_minimum_window_sensitivity.csv"
    disagreement_path = MANIFESTS / "causal_grid_candidate_disagreement.csv"
    scenario_path = MANIFESTS / "causal_grid_phase6b_scenario_disagreement.csv"
    rate_path = MANIFESTS / "causal_grid_drug_alignment_summary.csv"
    demographics_path = MANIFESTS / "causal_grid_demographics_pk_input_feasibility.csv"
    boundary_path = MANIFESTS / "causal_grid_boundary_review.csv"
    summary_path = MANIFESTS / "causal_grid_feasibility_summary.json"
    source_path = MANIFESTS / "causal_grid_feasibility_source_snapshot.json"
    report_path = ROOT / "docs" / "causal_grid_window_feasibility_report.md"
    atomic_csv(candidate_path, candidate_rows)
    atomic_csv(minimum_path, minimum_rows)
    atomic_csv(disagreement_path, disagreement_rows)
    atomic_csv(scenario_path, scenario_rows)
    atomic_csv(rate_path, rate_rows)
    atomic_csv(demographics_path, demographics)
    atomic_csv(boundary_path, boundary_rows)

    summary = {
        "phase": "6C_causal_grid_and_prediction_window_feasibility_audit",
        "generated_at": datetime.now(UTC).isoformat(), "scientific_result": False,
        "case_count": EXPECTED_CASE_COUNT, "candidate_count": len(candidates),
        "case_candidate_row_count": EXPECTED_CASE_COUNT * len(candidates),
        "fixed_structure": {
            "grid_interval_seconds": 10, "grid_anchor": "case_anesthesia_start",
            "history_times_relative_to_t_seconds": [-50, -40, -30, -20, -10, 0],
            "target_time_relative_to_t_seconds": 30,
            "same_case_anesthesia_window_and_common_observed_span_required": True,
        },
        "bis_numerical_range": {"minimum": 0, "maximum": 100, "bis_0_10_automatically_invalid": False},
        "sqi_role": "qc_only_not_prediction_feature_not_ppo_state",
        "prediction_feature_universe_inspected": ["BIS/BIS", "Orchestra/PPF20_RATE", "Orchestra/RFTN20_RATE"],
        "candidate_aggregate": candidate_rows,
        "minimum_window_thresholds": list(MINIMUM_WINDOW_COUNTS),
        "minimum_window_threshold_selected": None,
        "demographics_pk_input_feasibility": demographics_summary,
        "boundary_category_counts": {name: len(set(values)) for name, values in sorted(boundary_members.items())},
        "boundary_seed": PHASE6C_SEED,
        "selected_preprocessing_rule": None, "selected_sqi_rule": None,
        "selected_bis_staleness_cap": None, "selected_drug_hold_cap": None,
        "selected_quality_threshold": None, "final_eligible_cohort_created": False,
        "cohort_frozen": False,
        "execution_flags": {
            "api_requests": 0, "new_raw_files": 0, "modeling_arrays": False,
            "split": False, "normalization": False, "train_only_statistics": False,
            "persistence": False, "cpce": False, "recent_dose": False,
            "cumulative_dose": False, "prediction": False, "elastic_net": False,
            "gru": False, "attention_gru": False, "feature_selection": False,
            "ppo": False, "test_target_inspection": False,
        },
    }
    atomic_json(summary_path, summary)
    atomic_bytes(report_path, render_report(summary).encode())
    source_snapshot = {
        "schema_version": 1, "phase": summary["phase"],
        "recorded_at": datetime.now(UTC).isoformat(),
        "phase6b_phase_commit": PHASE6B_PHASE_COMMIT,
        "phase6b_verified_remote_main": PHASE6B_VERIFIED_REMOTE,
        "input_artifact_sha256": input_checksums,
        "phase6b_artifact_inventory_verified": True,
        "raw_checksum_before": checksum_before, "raw_checksum_after": checksum_after,
        "raw_tree_before": raw_before, "raw_tree_after": raw_after,
        "raw_tree_unchanged": True, "new_raw_file_count": 0, "api_request_count": 0,
        "legacy_state_before": legacy_before, "legacy_state_after": legacy_after,
        "legacy_state_unchanged": True, "legacy_artifact_accessed": False,
        "allowed_exact_tracks": list(TRACK_NAMES),
        "raw_row_handling": {
            "original_row_order_preserved": True, "raw_timestamp_sorting": False,
            "derived_event_time_lookup_index": True, "duplicate_deletion": False,
            "duplicate_averaging": False, "duplicate_candidate": "last_finite_in_original_row_order",
            "resampling": False, "interpolation": False, "smoothing": False,
            "clipping": False, "backward_fill": False, "unlimited_forward_fill": False,
        },
        "causality_checks": {"future_timestamp_use_count": 0, "cross_case_connection_count": 0},
        "bounded_memory_method": "sequential case-level parsing; four case indexes and 60 count-only rows released before next case; atomic gzip manifest",
        "peak_rss_bytes": max_peak, "memory_abort_guard_bytes": args.memory_abort_bytes,
        "memory_abort_guard_is_engineering_only": True,
        "sqi_in_prediction_feature_universe": False,
        "bis_0_10_automatically_invalid": False,
        "final_cohort_frozen": False,
        "prohibited_execution": summary["execution_flags"],
    }
    atomic_json(source_path, source_snapshot)
    artifacts = (
        case_candidate_path, candidate_path, minimum_path, disagreement_path,
        scenario_path, rate_path, demographics_path, boundary_path, summary_path,
        source_path, report_path,
    )
    atomic_json(MANIFESTS / "causal_grid_feasibility_artifact_checksums.json", {
        path.relative_to(ROOT).as_posix(): sha256_path(path) for path in artifacts
    })
    print(json.dumps({
        "case_count": EXPECTED_CASE_COUNT, "candidate_count": len(candidates),
        "case_candidate_rows": EXPECTED_CASE_COUNT * len(candidates),
        "peak_rss_bytes": max_peak, "raw_files_verified": checksum_after["verified_file_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

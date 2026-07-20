"""Run Phase 6B from checksum-verified Phase 6A raw artifacts without network I/O."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.primary_signal_quality import (  # noqa: E402
    DRUG_TRACK_NAMES,
    EXPECTED_CASE_COUNT,
    EXPECTED_TRACK_ROW_COUNT,
    PHASE6B_SEED,
    PRIMARY_SIGNAL_NAMES,
    TRACK_NAMES,
    build_case_record,
    characterize_track,
    distribution,
    fixed_boundary_samples,
    marginal_sensitivity,
    scenario_tables,
    sha256_path,
)


MANIFESTS = ROOT / "data" / "manifests"
RAW_ROOT = ROOT / "data" / "raw" / "phase6a_primary_signals"
LEGACY_ROOT = ROOT.parent / "VitalDB-Feature-Selection"
PHASE6A_REMOTE = "71ecaac71be63b34d90bf91f0acffabf64d50895"
PHASE6A_PHASE_COMMIT = "15d35dad656f931826255c8e1e0cf6deea69be83"
WINDOW_SOURCE_SHA256 = "66c65af9fa72467c29544e6d9c84550449370e61781b703461f83508964f30a8"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 6B outcome-blind signal-quality characterization")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--refresh-derived-views-only", action="store_true",
        help="rerender summary/report checksums from a completed Phase 6B run without reading raw files",
    )
    return parser.parse_args()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _atomic_bytes(path: Path, payload: bytes) -> None:
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


def _atomic_json(path: Path, value: object) -> None:
    _atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _csv_value(value: object) -> object:
    if value is True: return "true"
    if value is False: return "false"
    if isinstance(value, (list, dict, tuple, set)):
        return json.dumps(list(value) if isinstance(value, set) else value, ensure_ascii=False, separators=(",", ":"), sort_keys=isinstance(value, dict))
    return value


def _atomic_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty CSV: {path}")
    preferred = list(rows[0])
    extras = sorted({key for row in rows for key in row} - set(preferred))
    fields = preferred + extras
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _csv_value(row.get(key)) for key in fields})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _raw_tree_state() -> dict[str, object]:
    files = sorted(path for path in RAW_ROOT.rglob("*") if path.is_file())
    entries = [f"{path.relative_to(RAW_ROOT).as_posix()}\t{path.stat().st_size}" for path in files]
    return {
        "file_count": len(files), "total_bytes": sum(path.stat().st_size for path in files),
        "relative_path_and_size_fingerprint_sha256": hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest(),
        "partial_file_count": sum(path.suffix == ".part" for path in files),
    }


def _legacy_state() -> dict[str, object]:
    safe = LEGACY_ROOT.resolve().as_posix()
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={safe}", "-C", str(LEGACY_ROOT), *args],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    return {
        "head": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
        "status_short": git("status", "--short").splitlines(),
    }


def _load_sources() -> tuple[list[dict[str, str]], dict[int, tuple[float, float]], dict[str, object]]:
    source = json.loads((MANIFESTS / "primary_signal_source_snapshot.json").read_text(encoding="utf-8"))
    if source["stage"] != "full" or source["allowed_exact_tracks"] != list(TRACK_NAMES):
        raise RuntimeError("Phase 6A source snapshot does not authorize the exact Phase 6B scope")
    cohort = _read_csv(MANIFESTS / "pre_quality_acquisition_cohort.csv")
    included = {
        int(row["caseid"]) for row in cohort
        if row["included_for_primary_signal_acquisition"] == "true"
    }
    if len(cohort) != 3219 or len(included) != EXPECTED_CASE_COUNT:
        raise RuntimeError("Phase 6A cohort accounting does not equal 3,219/2,470")
    downloads = _read_csv(MANIFESTS / "primary_signal_download_manifest.csv")
    if len(downloads) != EXPECTED_TRACK_ROW_COUNT:
        raise RuntimeError("Phase 6A download manifest does not contain 9,880 rows")
    keys = {(int(row["caseid"]), row["track_name"]) for row in downloads}
    expected = {(caseid, track) for caseid in included for track in TRACK_NAMES}
    if keys != expected:
        raise RuntimeError("Phase 6A case×track keys are duplicated or incomplete")
    if any(row["download_status"] != "complete" for row in downloads):
        raise RuntimeError("Phase 6B requires all Phase 6A raw rows complete")

    window_path = MANIFESTS / "volatile_signal_case_manifest.csv"
    if sha256_path(window_path) != WINDOW_SOURCE_SHA256:
        raise RuntimeError("inherited 3,219-case anesthesia-window source checksum mismatch")
    windows_all = _read_csv(window_path)
    windows = {
        int(row["caseid"]): (float(row["anesthesia_start"]), float(row["anesthesia_end"]))
        for row in windows_all if int(row["caseid"]) in included
    }
    if set(windows) != included or any(end <= start for start, end in windows.values()):
        raise RuntimeError("included Phase 6A cases lack valid inherited anesthesia windows")
    return downloads, windows, source


def _verify_all_raw(downloads: list[dict[str, str]]) -> dict[str, object]:
    fingerprint_rows: list[str] = []
    total_bytes = 0
    for index, row in enumerate(downloads, start=1):
        path = RAW_ROOT / row["raw_relative_path"]
        if not path.is_file():
            raise RuntimeError(f"missing Phase 6A raw file: {row['raw_relative_path']}")
        actual_size = path.stat().st_size
        actual_hash = sha256_path(path)
        if actual_size != int(row["raw_byte_count"]) or actual_hash != row["raw_sha256"]:
            raise RuntimeError(f"Phase 6A raw checksum mismatch: {row['caseid']} {row['track_name']}")
        total_bytes += actual_size
        fingerprint_rows.append(f"{row['caseid']}|{row['track_name']}|{actual_size}|{actual_hash}")
        if index % 1000 == 0:
            print(f"source checksum progress {index}/{len(downloads)}", flush=True)
    return {
        "verified_file_count": len(downloads), "verified_total_bytes": total_bytes,
        "manifest_order_fingerprint_sha256": hashlib.sha256(("\n".join(fingerprint_rows) + "\n").encode()).hexdigest(),
    }


def _characterize(
    downloads: list[dict[str, str]], windows: dict[int, tuple[float, float]], workers: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if workers < 1 or workers > 16:
        raise ValueError("workers must be between 1 and 16")

    source_by_case: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in downloads:
        source_by_case[int(row["caseid"])].append(row)

    def one(caseid: int) -> tuple[list[dict[str, object]], dict[str, object]]:
        start, end = windows[caseid]
        source_rows = source_by_case[caseid]
        if len(source_rows) != len(TRACK_NAMES):
            raise RuntimeError(f"case {caseid} lacks four source rows")
        characterized: list[dict[str, object]] = []
        for row in source_rows:
            path = RAW_ROOT / row["raw_relative_path"]
            parsed = characterize_track(
                path, expected_track_name=row["track_name"],
                anesthesia_start=start, anesthesia_end=end,
                retain_finite_timestamps=True,
            )
            characterized.append({
                "caseid": caseid, "exact_track_name": row["track_name"],
                "expected_file_path": row["raw_relative_path"],
                "source_checksum_sha256": row["raw_sha256"],
                "checksum_status": "verified_before_analysis",
                "track_present_in_phase6a_manifest": True, "raw_file_present": True,
                "source_raw_byte_count": int(row["raw_byte_count"]), **parsed,
            })
        by_name = {str(row["exact_track_name"]): row for row in characterized}
        case_row = build_case_record(caseid, start, end, by_name)
        for row in characterized:
            row.pop("_window_finite_timestamps", None)
        return characterized, case_row

    results: list[dict[str, object]] = []
    case_results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(one, caseid): caseid for caseid in sorted(source_by_case)}
        total = len(futures)
        for completed, future in enumerate(as_completed(futures), start=1):
            case_tracks, case_row = future.result()
            results.extend(case_tracks)
            case_results.append(case_row)
            if completed % 100 == 0 or completed == total:
                print(f"quality characterization progress {completed}/{total}", flush=True)
    return (
        sorted(results, key=lambda row: (int(row["caseid"]), TRACK_NAMES.index(str(row["exact_track_name"])))),
        sorted(case_results, key=lambda row: int(row["caseid"])),
    )


def _aggregate(
    case_rows: list[dict[str, object]], track_rows: list[dict[str, object]],
    marginal: list[dict[str, object]], scenarios: list[dict[str, object]],
    disagreement: list[dict[str, object]], boundaries: list[dict[str, object]],
) -> dict[str, object]:
    by_track: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in track_rows:
        by_track[str(row["exact_track_name"])].append(row)
    track_summaries = {}
    for track, rows in by_track.items():
        track_summaries[track] = {
            "case_count": len(rows),
            "parsing_status_counts": dict(sorted(Counter(str(row["parsing_status"]) for row in rows).items())),
            "total_row_count_distribution": distribution([row["total_row_count"] for row in rows]),
            "window_finite_count_distribution": distribution([row["window_finite_count"] for row in rows]),
            "window_observed_span_ratio_distribution": distribution([row["observed_span_to_anesthesia_duration_ratio"] for row in rows]),
            "window_longest_positive_gap_distribution": distribution([row["window_longest_strictly_positive_gap"] for row in rows]),
            "duplicate_timestamp_case_count": sum(int(row["raw_duplicate_timestamp_count"]) > 0 for row in rows),
            "negative_interval_case_count": sum(int(row["raw_negative_interval_count"]) > 0 for row in rows),
        }
    drug_patterns = Counter()
    for row in case_rows:
        if row["both_drugs_positive_record_present"]: label = "both_positive"
        elif row["propofol_only_positive"]: label = "propofol_only_positive"
        elif row["remifentanil_only_positive"]: label = "remifentanil_only_positive"
        else: label = "both_zero_or_nonpositive"
        if row["negative_drug_rate_present"]: label += "|negative_rate_present"
        drug_patterns[label] += 1
    return {
        "phase": "6B_outcome_blind_primary_signal_quality_characterization",
        "generated_at": datetime.now(UTC).isoformat(), "scientific_result": False,
        "case_count": len(case_rows), "case_track_row_count": len(track_rows),
        "allowed_exact_tracks": list(TRACK_NAMES), "track_summaries": track_summaries,
        "anesthesia_duration_distribution": distribution([row["anesthesia_duration_seconds"] for row in case_rows]),
        "common_observed_span_duration_distribution": distribution([row["common_observed_span_duration_seconds"] for row in case_rows]),
        "common_observed_span_ratio_distribution": distribution([row["common_observed_span_to_anesthesia_duration_ratio"] for row in case_rows]),
        "bis_0_100_fraction_distribution": distribution([row["bis_0_100_fraction_of_finite"] for row in case_rows]),
        "bis_10_100_fraction_distribution": distribution([row["bis_10_100_fraction_of_finite"] for row in case_rows]),
        "sqi_ge_50_fraction_distribution": distribution([row["sqi_ge_50_fraction_of_finite"] for row in case_rows]),
        "drug_record_pattern_counts": dict(sorted(drug_patterns.items())),
        "negative_drug_rate_case_count": sum(bool(row["negative_drug_rate_present"]) for row in case_rows),
        "marginal_sensitivity": marginal, "combined_scenarios": scenarios,
        "pairwise_scenario_disagreement": disagreement,
        "boundary_review_category_counts": {
            category: max(int(row["category_case_count"]) for row in boundaries if row["category"] == category)
            for category in sorted({str(row["category"]) for row in boundaries})
        },
        "boundary_review_seed": PHASE6B_SEED,
        "selected_quality_threshold": None, "selected_scenario": None,
        "final_eligible_cohort_created": False, "cohort_frozen": False,
        "execution_flags": {
            "api_requests": 0, "new_raw_files": 0, "raw_modification": False,
            "interpolation": False, "resampling": False, "normalization": False,
            "prediction_windows": False, "split": False, "persistence": False,
            "cpce": False, "dose_calculation": False, "prediction": False,
            "elastic_net": False, "gru": False, "attention_gru": False,
            "feature_selection": False, "ppo": False,
        },
    }


def _render_report(summary: dict[str, object]) -> str:
    scenarios = {row["scenario"]: row for row in summary["combined_scenarios"]}
    lines = [
        "# Phase 6B Primary Signal Quality Characterization", "",
        "## Facts", "",
        f"- Phase 6A acquisition cases: `{summary['case_count']}`.",
        f"- Exact case×track rows characterized: `{summary['case_track_row_count']}`.",
        "- All measures retain original row order and distinguish the full recording from the inherited anesthesia window.",
        "- Common observed span is only the overlap of first/last finite timestamp ranges; it is not continuous coverage.",
        "- Long gaps are descriptive. Event-style drug-rate cadence may not represent missingness.",
        "- BIS/SQI remains QC-only and was not added to any feature or PPO universe.", "",
        "## Track accounting", "",
        "| Exact track | Cases | Duplicate-timestamp cases | Negative-interval cases |",
        "|---|---:|---:|---:|",
    ]
    for name in TRACK_NAMES:
        item = summary["track_summaries"][name]
        lines.append(
            f"| `{name}` | {item['case_count']} | {item['duplicate_timestamp_case_count']} | {item['negative_interval_case_count']} |"
        )
    lines.extend([
        "", "## Interpretation boundary", "",
        "No quality cutoff, valid-BIS range, SQI threshold, gap rule, or combined scenario was selected.",
        "The tables are outcome-blind sensitivity material for a future Protocol v1.2 human decision.", "",
        "Observed-span ratios use only first/last timestamps. Timestamp-gap rules are descriptive and may behave differently for event-style drug-rate recordings.", "",
        "## Scenario definitions", "",
        "- `permissive`: anesthesia >=20 min; common span >=10 min; BIS 0-100 fraction >=80%; both drug tracks have >=1 positive record; no negative rate.",
        "- `moderate`: anesthesia >=30 min; common span >=20 min; BIS 10-100 fraction >=80%; SQI >=50 fraction >=50%; both drug tracks have >=3 positive records; no negative rate.",
        "- `strict`: anesthesia >=60 min; common span >=30 min; BIS 10-100 fraction >=90%; SQI >=50 fraction >=80%; both drug tracks have >=3 positive records; no negative rate.", "",
        "## Combined scenario comparison", "",
        "| Scenario | Pass | Fail | Selected |", "|---|---:|---:|---|",
    ])
    for name in ("permissive", "moderate", "strict"):
        row = scenarios[name]
        lines.append(f"| {name} | {row['pass_count']} | {row['fail_count']} | no |")
    lines.extend(["", "## Marginal sensitivity", "",
                  "Every row below is an independent comparison, not a selected rule.", "",
                  "| Category | Metric | Threshold | Pass | Fail | Missing measure |",
                  "|---|---|---:|---:|---:|---:|"])
    for row in summary["marginal_sensitivity"]:
        lines.append(
            f"| {row['category']} | `{row['metric']}` | {row['threshold']} | {row['pass_count']} | {row['fail_count']} | {row['missing_measure_count']} |"
        )
    lines.extend(["", "## Boundary review", "",
                  f"Fixed seed `{PHASE6B_SEED}`; at most five IDs per category. Samples do not alter inclusion.", ""])
    for category, count in summary["boundary_review_category_counts"].items():
        lines.append(f"- `{category}`: {count} cases in category")
    lines.extend(["", "## Prohibited work", "",
                  "No API request, raw rewrite, interpolation, resampling, cohort freeze, split, prediction, Cp/Ce, dose calculation, feature selection, or PPO execution occurred.", ""])
    return "\n".join(lines).rstrip()


def main() -> int:
    args = parse_args()
    if args.refresh_derived_views_only:
        summary_path = MANIFESTS / "primary_signal_quality_summary.json"
        boundary_path = MANIFESTS / "primary_signal_quality_boundary_review.csv"
        report_path = ROOT / "docs" / "primary_signal_quality_characterization_report.md"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        boundaries = _read_csv(boundary_path)
        summary["boundary_review_category_counts"] = {
            category: max(
                int(row["category_case_count"])
                for row in boundaries if row["category"] == category
            )
            for category in sorted({row["category"] for row in boundaries})
        }
        _atomic_json(summary_path, summary)
        _atomic_bytes(report_path, (_render_report(summary) + "\n").encode())
        artifacts = (
            MANIFESTS / "primary_signal_quality_case_manifest.csv",
            MANIFESTS / "primary_signal_quality_track_manifest.csv", summary_path,
            MANIFESTS / "primary_signal_quality_marginal_sensitivity.csv",
            MANIFESTS / "primary_signal_quality_scenario_sensitivity.csv",
            MANIFESTS / "primary_signal_quality_scenario_disagreement.csv",
            boundary_path, MANIFESTS / "primary_signal_quality_source_snapshot.json", report_path,
        )
        _atomic_json(MANIFESTS / "primary_signal_quality_artifact_checksums.json", {
            path.relative_to(ROOT).as_posix(): sha256_path(path) for path in artifacts
        })
        print(json.dumps({"refreshed": True, "raw_files_read": 0}, sort_keys=True))
        return 0
    downloads, windows, phase6a_source = _load_sources()
    raw_before = _raw_tree_state()
    legacy_before = _legacy_state()
    checksum_before = _verify_all_raw(downloads)
    track_rows, case_rows = _characterize(downloads, windows, args.workers)
    if len(track_rows) != EXPECTED_TRACK_ROW_COUNT:
        raise RuntimeError("quality track manifest row count mismatch")
    by_case: dict[int, dict[str, dict[str, object]]] = defaultdict(dict)
    for row in track_rows:
        by_case[int(row["caseid"])][str(row["exact_track_name"])] = row
    scenarios, disagreement = scenario_tables(case_rows)
    marginal = marginal_sensitivity(case_rows, by_case)
    boundaries = fixed_boundary_samples(case_rows, by_case)
    summary = _aggregate(case_rows, track_rows, marginal, scenarios, disagreement, boundaries)

    checksum_after = _verify_all_raw(downloads)
    raw_after = _raw_tree_state()
    legacy_after = _legacy_state()
    if checksum_before != checksum_after:
        raise RuntimeError("Phase 6A raw checksum fingerprint changed during Phase 6B")
    if raw_before != raw_after:
        raise RuntimeError("Phase 6A raw tree changed during Phase 6B")
    if legacy_before != legacy_after:
        raise RuntimeError("legacy repository state changed during Phase 6B")
    if raw_after["partial_file_count"] != 0:
        raise RuntimeError("partial files remain in Phase 6A raw root")

    for row in track_rows:
        row.pop("_window_finite_timestamps", None)
        row["checksum_status"] = "verified_before_and_after_analysis"
    case_path = MANIFESTS / "primary_signal_quality_case_manifest.csv"
    track_path = MANIFESTS / "primary_signal_quality_track_manifest.csv"
    summary_path = MANIFESTS / "primary_signal_quality_summary.json"
    marginal_path = MANIFESTS / "primary_signal_quality_marginal_sensitivity.csv"
    scenario_path = MANIFESTS / "primary_signal_quality_scenario_sensitivity.csv"
    disagreement_path = MANIFESTS / "primary_signal_quality_scenario_disagreement.csv"
    boundary_path = MANIFESTS / "primary_signal_quality_boundary_review.csv"
    source_path = MANIFESTS / "primary_signal_quality_source_snapshot.json"
    report_path = ROOT / "docs" / "primary_signal_quality_characterization_report.md"
    _atomic_csv(case_path, case_rows)
    _atomic_csv(track_path, track_rows)
    _atomic_csv(marginal_path, marginal)
    _atomic_csv(scenario_path, scenarios)
    _atomic_csv(disagreement_path, disagreement)
    _atomic_csv(boundary_path, boundaries)
    _atomic_json(summary_path, summary)
    _atomic_bytes(report_path, (_render_report(summary) + "\n").encode())
    source_snapshot = {
        "schema_version": 1, "phase": summary["phase"],
        "recorded_at": datetime.now(UTC).isoformat(),
        "phase6a_phase_commit": PHASE6A_PHASE_COMMIT, "phase6a_verified_remote_main": PHASE6A_REMOTE,
        "input_artifact_sha256": {
            name: sha256_path(MANIFESTS / name) for name in (
                "pre_quality_acquisition_cohort.csv", "primary_signal_download_manifest.csv",
                "primary_signal_checksum_manifest.csv", "primary_signal_source_snapshot.json",
            )
        },
        "anesthesia_window_lineage": {
            "path": "data/manifests/volatile_signal_case_manifest.csv",
            "sha256": WINDOW_SOURCE_SHA256,
            "fields_read": ["caseid", "anesthesia_start", "anesthesia_end"],
            "rationale": "Protocol v1.1 inherits the checksum-verified 3,219-case Phase 5C/5D universe; Phase 6A pre-quality manifest contains IDs and exclusion flags but not window columns",
            "volatile_raw_signal_read": False,
        },
        "raw_checksum_before": checksum_before, "raw_checksum_after": checksum_after,
        "raw_tree_before": raw_before, "raw_tree_after": raw_after,
        "raw_tree_unchanged": True, "new_raw_file_count": 0, "api_request_count": 0,
        "legacy_state_before": legacy_before, "legacy_state_after": legacy_after,
        "legacy_state_unchanged": True, "legacy_artifact_accessed": False,
        "allowed_exact_tracks": list(TRACK_NAMES),
        "bounded_memory_method": "one case-track file per worker; aggregate rows only; never loads the 2.66 GB corpus together",
        "workers": args.workers, "bis_sqi_role": "qc_only_not_prediction_feature_not_ppo_state",
        "selected_quality_threshold": None, "final_cohort_frozen": False,
        "prohibited_execution": summary["execution_flags"],
    }
    _atomic_json(source_path, source_snapshot)
    artifacts = (case_path, track_path, summary_path, marginal_path, scenario_path,
                 disagreement_path, boundary_path, source_path, report_path)
    _atomic_json(MANIFESTS / "primary_signal_quality_artifact_checksums.json", {
        path.relative_to(ROOT).as_posix(): sha256_path(path) for path in artifacts
    })
    print(json.dumps({
        "case_count": len(case_rows), "track_row_count": len(track_rows),
        "scenario_pass_counts": {row["scenario"]: row["pass_count"] for row in scenarios},
        "source_checksum_count": checksum_after["verified_file_count"],
        "source_raw_bytes": checksum_after["verified_total_bytes"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

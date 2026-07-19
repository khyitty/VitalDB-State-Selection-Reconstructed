"""Protocol v1.1 pre-quality cohort accounting and primary-signal acquisition."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import random
import statistics
import tempfile
import threading
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from .guards import CohortGuardError, normalize_caseid


EXPECTED_UNIVERSE_COUNT = 3219
PREFLIGHT_CASE_COUNT = 25
PHASE6A_SEED = 20260720
MAX_ATTEMPTS = 3
PHASE5D_PRIMARY_DEFINITION = "D_longest_positive_run_ge_10s"


@dataclass(frozen=True)
class PrimaryTrackSpec:
    track_name: str
    file_stem: str
    role: str
    official_description: str
    official_unit: str
    concentration: str | None = None


PRIMARY_TRACKS = (
    PrimaryTrackSpec("BIS/BIS", "bis", "primary_bis", "Bispectral index value", "unitless"),
    PrimaryTrackSpec("BIS/SQI", "bis_sqi", "qc_only", "Signal quality index", "%"),
    PrimaryTrackSpec(
        "Orchestra/PPF20_RATE", "ppf20_rate", "primary_drug_rate",
        "Infusion rate (propofol 20 mg/mL)", "mL/hr", "propofol 20 mg/mL",
    ),
    PrimaryTrackSpec(
        "Orchestra/RFTN20_RATE", "rftn20_rate", "primary_drug_rate",
        "Infusion rate (remifentanil 20 mcg/mL)", "mL/hr", "remifentanil 20 mcg/mL",
    ),
)
PRIMARY_TRACK_NAMES = tuple(spec.track_name for spec in PRIMARY_TRACKS)
SPEC_BY_NAME = {spec.track_name: spec for spec in PRIMARY_TRACKS}


@dataclass(frozen=True)
class PrimaryTask:
    caseid: int
    track_name: str
    tids: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.caseid}|{self.track_name}"


class PrimaryTrackParseError(ValueError):
    """A primary-track payload cannot be parsed without changing source rows."""


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".part", dir=path.parent
    )
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
    atomic_bytes(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
    )


def assert_no_partials(raw_root: Path) -> None:
    residual = sorted(raw_root.rglob("*.part")) if raw_root.exists() else []
    if residual:
        raise CohortGuardError(f"partial files remain: {residual[:10]}")


def remove_stale_partials(raw_root: Path) -> list[str]:
    removed: list[str] = []
    if not raw_root.exists():
        return removed
    resolved_root = raw_root.resolve()
    for path in raw_root.rglob("*.part"):
        if resolved_root not in path.resolve().parents:
            raise CohortGuardError("partial path escaped raw root")
        removed.append(path.relative_to(raw_root).as_posix())
        path.unlink()
    return sorted(removed)


def build_pre_quality_manifest(
    phase5c_rows: Sequence[Mapping[str, object]],
    phase5d_records: Sequence[Mapping[str, object]],
    legacy_caseids: set[int],
) -> list[dict[str, object]]:
    if len(legacy_caseids) != 98:
        raise CohortGuardError("legacy actual-use ID artifact must contain 98 unique IDs")
    p5c = {normalize_caseid(row["caseid"]): row for row in phase5c_rows}
    p5d = {normalize_caseid(row["caseid"]): row for row in phase5d_records}
    expected = set(p5c)
    if len(p5c) != EXPECTED_UNIVERSE_COUNT or len(phase5c_rows) != len(p5c):
        raise CohortGuardError("Phase 5C universe must contain 3,219 unique cases")
    if set(p5d) != expected or len(phase5d_records) != len(p5d):
        raise CohortGuardError("Phase 5D records do not exactly match Phase 5C universe")

    rows: list[dict[str, object]] = []
    for caseid in sorted(expected):
        source = p5d[caseid]
        definitions = source.get("definitions")
        if not isinstance(definitions, Mapping) or PHASE5D_PRIMARY_DEFINITION not in definitions:
            raise CohortGuardError(f"case {caseid} lacks Phase 5D primary definition")
        volatile = definitions[PHASE5D_PRIMARY_DEFINITION]
        valid_window = source.get("anesthesia_window_valid")
        if volatile not in (True, False) or valid_window not in (True, False):
            raise CohortGuardError(f"case {caseid} has unresolved Phase 5D flags")
        invalid = not bool(valid_window)
        overlap = caseid in legacy_caseids
        reasons: list[str] = []
        if volatile:
            reasons.append("volatile_positive_run_ge_10s")
        if invalid:
            reasons.append("ineligible_invalid_anesthesia_window")
        if overlap:
            reasons.append("legacy_98_overlap")
        included = not reasons
        rows.append(
            {
                "caseid": caseid,
                "analysis_universe": "exact_primary_plus_age_ge_18_plus_anesthesia_type_exact_general",
                "analysis_universe_count": EXPECTED_UNIVERSE_COUNT,
                "volatile_positive_run_ge_10s": bool(volatile),
                "invalid_anesthesia_window": invalid,
                "legacy_98_overlap": overlap,
                "included_for_primary_signal_acquisition": included,
                "exclusion_reasons": reasons,
                "eligibility_stage": "pre_quality_acquisition_only_not_final_not_frozen",
                "signal_quality_evaluated": False,
                "final_eligibility": "pending_human_review",
                "split_assigned": False,
            }
        )
    if sum(row["invalid_anesthesia_window"] for row in rows) != 1:
        raise CohortGuardError("Protocol v1.1 expects exactly one invalid anesthesia window")
    invalid_caseids = [row["caseid"] for row in rows if row["invalid_anesthesia_window"]]
    if invalid_caseids != [4476]:
        raise CohortGuardError("the preserved invalid anesthesia window must be case 4476")
    return rows


def fixed_seed_preflight_caseids(
    included_caseids: Sequence[int], *, seed: int = PHASE6A_SEED
) -> list[int]:
    unique = sorted(set(map(normalize_caseid, included_caseids)))
    if len(unique) != len(included_caseids) or len(unique) < PREFLIGHT_CASE_COUNT:
        raise CohortGuardError("preflight universe is duplicate or too small")
    chosen = sorted(random.Random(seed).sample(unique, PREFLIGHT_CASE_COUNT))
    if chosen == unique[:PREFLIGHT_CASE_COUNT]:
        raise CohortGuardError("fixed-seed sample unexpectedly equals first 25")
    return chosen


def build_tasks(
    included_caseids: Sequence[int], track_rows: Sequence[Mapping[str, object]]
) -> list[PrimaryTask]:
    included = sorted(set(map(normalize_caseid, included_caseids)))
    if len(included) != len(included_caseids):
        raise CohortGuardError("included acquisition case IDs are duplicated")
    tid_map: dict[tuple[int, str], set[str]] = defaultdict(set)
    included_set = set(included)
    for source in track_rows:
        name = str(source.get("tname", "")).strip()
        if name not in SPEC_BY_NAME:
            continue
        caseid = normalize_caseid(source.get("caseid"))
        if caseid not in included_set:
            continue
        tid = str(source.get("tid", "")).strip()
        if not tid:
            raise CohortGuardError(f"case {caseid} {name} has empty TID")
        tid_map[(caseid, name)].add(tid)
    tasks = [
        PrimaryTask(caseid, name, tuple(sorted(tid_map.get((caseid, name), set()))))
        for caseid in included
        for name in PRIMARY_TRACK_NAMES
    ]
    if len(tasks) != len(included) * len(PRIMARY_TRACKS):
        raise CohortGuardError("primary acquisition task matrix is incomplete")
    return tasks


def parse_primary_track(payload: bytes, *, expected_track_name: str) -> dict[str, object]:
    decoded = gzip.decompress(payload) if payload.startswith(b"\x1f\x8b") else payload
    try:
        text = decoded.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PrimaryTrackParseError(f"UTF-8 decode failed: {exc}") from exc
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise PrimaryTrackParseError("track payload has no header") from exc
    if len(header) < 2 or header[0].strip() != "Time":
        raise PrimaryTrackParseError(f"unexpected track header: {header!r}")
    if header[1].strip() != expected_track_name:
        raise PrimaryTrackParseError(
            f"expected {expected_track_name!r}, got {header[1].strip()!r}"
        )
    sample_count = 0
    non_missing = 0
    duplicate_count = 0
    nonmonotonic_count = 0
    seen: set[float] = set()
    previous: float | None = None
    for row_number, row in enumerate(reader, start=2):
        if not row:
            continue
        sample_count += 1
        if len(row) < 2:
            raise PrimaryTrackParseError(f"row {row_number} has fewer than two columns")
        try:
            timestamp = float(row[0])
        except ValueError as exc:
            raise PrimaryTrackParseError(f"invalid timestamp at row {row_number}") from exc
        if not math.isfinite(timestamp):
            raise PrimaryTrackParseError(f"non-finite timestamp at row {row_number}")
        if timestamp in seen:
            duplicate_count += 1
        if previous is not None and timestamp < previous:
            nonmonotonic_count += 1
        seen.add(timestamp)
        previous = timestamp
        raw_value = row[1].strip()
        if raw_value == "":
            continue
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise PrimaryTrackParseError(f"invalid numeric value at row {row_number}") from exc
        if math.isfinite(value):
            non_missing += 1
    return {
        "sample_count": sample_count,
        "non_missing_sample_count": non_missing,
        "duplicate_timestamp_count": duplicate_count,
        "nonmonotonic_timestamp_count": nonmonotonic_count,
        "resampling_performed": False,
        "interpolation_performed": False,
        "smoothing_performed": False,
        "clipping_performed": False,
    }


def task_paths(raw_root: Path, task: PrimaryTask) -> tuple[Path, Path]:
    case_root = raw_root / "cases" / str(task.caseid)
    stem = SPEC_BY_NAME[task.track_name].file_stem
    return case_root / f"{stem}.signal", case_root / f"{stem}.metadata.json"


def load_verified_metadata(raw_root: Path, task: PrimaryTask) -> dict[str, object] | None:
    if len(task.tids) != 1:
        return None
    signal_path, metadata_path = task_paths(raw_root, task)
    if not signal_path.is_file() or not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        metadata.get("caseid") != task.caseid
        or metadata.get("track_name") != task.track_name
        or metadata.get("tid") != task.tids[0]
        or metadata.get("raw_relative_path") != signal_path.relative_to(raw_root).as_posix()
        or not isinstance(metadata.get("raw_sha256"), str)
        or sha256_path(signal_path) != metadata["raw_sha256"]
    ):
        return None
    return metadata


class ProgressLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.attempts: Counter[str] = Counter()
        self.last: dict[str, dict[str, object]] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line:
                    row = json.loads(line)
                    if row.get("event") == "attempt_finished":
                        self.attempts[str(row["task_key"])] += 1
                        self.last[str(row["task_key"])] = row

    def append(self, row: Mapping[str, object]) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            key = str(row["task_key"])
            self.attempts[key] += 1
            self.last[key] = dict(row)


def download_one_task(
    task: PrimaryTask, *, raw_root: Path, client: object, progress: ProgressLog,
    source_version: str,
) -> dict[str, object]:
    if len(task.tids) != 1:
        raise CohortGuardError("download requires exactly one TID")
    existing = load_verified_metadata(raw_root, task)
    if existing is not None:
        return existing
    attempts = int(progress.attempts[task.key])
    if attempts >= MAX_ATTEMPTS:
        prior = progress.last[task.key]
        return {
            "caseid": task.caseid, "track_name": task.track_name, "tid": task.tids[0],
            "status": "download_failed", "attempt_count": attempts,
            "raw_relative_path": None, "raw_byte_count": 0, "raw_sha256": None,
            "source_version": source_version, "parsing": None,
            "failure_type": prior.get("failure_type") or "AttemptBudgetExhausted",
            "failure_message": prior.get("failure_message"),
        }
    last_failure: dict[str, object] | None = None
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        try:
            payload, response = client.fetch_track(task.tids[0])
            parsing = parse_primary_track(payload, expected_track_name=task.track_name)
            status = "empty_signal" if parsing["sample_count"] == 0 else "complete"
            signal_path, metadata_path = task_paths(raw_root, task)
            atomic_bytes(signal_path, payload)
            metadata = {
                "caseid": task.caseid, "track_name": task.track_name, "tid": task.tids[0],
                "status": status, "attempt_count": attempts,
                "completed_at": datetime.now(UTC).isoformat(),
                "raw_relative_path": signal_path.relative_to(raw_root).as_posix(),
                "raw_byte_count": len(payload),
                "raw_sha256": hashlib.sha256(payload).hexdigest(),
                "source_version": source_version, "response_metadata": response,
                "parsing": parsing, "failure_type": None, "failure_message": None,
            }
            atomic_json(metadata_path, metadata)
            progress.append({
                "event": "attempt_finished", "task_key": task.key,
                "caseid": task.caseid, "track_name": task.track_name,
                "attempt": attempts, "timestamp": metadata["completed_at"],
                "status": status, "failure_type": None, "failure_message": None,
            })
            return metadata
        except Exception as exc:
            retryable = isinstance(exc, requests.RequestException)
            last_failure = {
                "caseid": task.caseid, "track_name": task.track_name, "tid": task.tids[0],
                "status": "download_failed" if retryable else "parsing_failed",
                "attempt_count": attempts, "raw_relative_path": None,
                "raw_byte_count": 0, "raw_sha256": None,
                "source_version": source_version, "parsing": None,
                "failure_type": type(exc).__name__, "failure_message": str(exc),
            }
            progress.append({
                "event": "attempt_finished", "task_key": task.key,
                "caseid": task.caseid, "track_name": task.track_name,
                "attempt": attempts, "timestamp": datetime.now(UTC).isoformat(),
                "status": last_failure["status"], "failure_type": type(exc).__name__,
                "failure_message": str(exc),
            })
            if not retryable:
                break
    assert last_failure is not None
    return last_failure


def manifest_row(
    task: PrimaryTask, metadata: Mapping[str, object] | None, *, source_version: str
) -> dict[str, object]:
    spec = SPEC_BY_NAME[task.track_name]
    row: dict[str, object] = {
        "caseid": task.caseid, "track_name": task.track_name, "track_role": spec.role,
        "prediction_feature_allowed": spec.role != "qc_only",
        "ppo_state_allowed": spec.role != "qc_only",
        "official_description": spec.official_description, "official_unit": spec.official_unit,
        "concentration": spec.concentration, "track_present": bool(task.tids),
        "tid_count": len(task.tids), "tids": list(task.tids),
        "download_status": "track_absent" if not task.tids else "not_completed",
        "attempt_count": 0, "raw_relative_path": None, "raw_byte_count": 0,
        "raw_sha256": None, "sample_count": None, "non_missing_sample_count": None,
        "duplicate_timestamp_count": None, "nonmonotonic_timestamp_count": None,
        "failure_type": None, "failure_message": None, "source_version": source_version,
        "signal_quality_exclusion_applied": False,
    }
    if len(task.tids) > 1:
        row.update(download_status="ambiguous_multiple_tids", failure_type="MultipleExactTrackTids",
                   failure_message="multiple exact TIDs were not merged")
        return row
    if metadata is None:
        return row
    row.update(
        download_status=metadata["status"], attempt_count=metadata["attempt_count"],
        raw_relative_path=metadata.get("raw_relative_path"),
        raw_byte_count=metadata.get("raw_byte_count", 0), raw_sha256=metadata.get("raw_sha256"),
        failure_type=metadata.get("failure_type"), failure_message=metadata.get("failure_message"),
    )
    parsing = metadata.get("parsing")
    if isinstance(parsing, Mapping):
        for key in ("sample_count", "non_missing_sample_count", "duplicate_timestamp_count",
                    "nonmonotonic_timestamp_count"):
            row[key] = parsing[key]
    return row


def build_preflight_summary(
    selected: Sequence[int], all_tasks: Sequence[PrimaryTask],
    results: Mapping[str, Mapping[str, object]], *, disk_free_bytes: int,
    elapsed_seconds: float, source_version: str,
) -> dict[str, object]:
    selected_set = set(selected)
    sample_tasks = [t for t in all_tasks if t.caseid in selected_set]
    present = [t for t in sample_tasks if len(t.tids) == 1]
    structural = [t for t in sample_tasks if len(t.tids) > 1]
    statuses = Counter(str(results[t.key]["status"]) for t in present if t.key in results)
    bytes_observed = [int(results[t.key].get("raw_byte_count", 0)) for t in present if t.key in results]
    full_present_count = sum(len(t.tids) == 1 for t in all_tasks)
    mean_bytes = statistics.fmean(bytes_observed) if bytes_observed else 0.0
    estimated_bytes = math.ceil(mean_bytes * full_present_count)
    parsing_problem_count = statuses["parsing_failed"] + statuses["empty_signal"]
    operational_problem_count = statuses["download_failed"] + len(structural) + (len(present) - len(results))
    operational_gate = parsing_problem_count == 0 and operational_problem_count == 0
    disk_gate = disk_free_bytes >= 2 * estimated_bytes and estimated_bytes > 0
    return {
        "phase": "6A_primary_signal_acquisition_preflight", "seed": PHASE6A_SEED,
        "selection_method": "fixed_seed_simple_random_sample_without_replacement",
        "selected_caseids": list(selected), "selected_case_count": len(selected),
        "sample_case_track_row_count": len(sample_tasks),
        "sample_present_request_count": len(present), "sample_status_counts": dict(sorted(statuses.items())),
        "sample_total_bytes": sum(bytes_observed), "mean_bytes_per_present_track": mean_bytes,
        "elapsed_seconds": elapsed_seconds, "full_present_request_count": full_present_count,
        "estimated_full_bytes": estimated_bytes,
        "estimated_full_elapsed_seconds_at_same_effective_throughput": (
            elapsed_seconds * full_present_count / len(present) if present else None
        ),
        "disk_free_bytes": disk_free_bytes, "required_two_x_estimated_bytes": 2 * estimated_bytes,
        "disk_gate_passed": disk_gate, "operational_gate_passed": operational_gate,
        "parsing_or_empty_problem_count": parsing_problem_count,
        "request_or_structure_problem_count": operational_problem_count,
        "full_download_authorized_by_gate": disk_gate and operational_gate,
        "source_version": source_version, "scientific_result": False,
        "quality_threshold_selected": False,
    }

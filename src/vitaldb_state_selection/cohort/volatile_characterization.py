"""Phase 5C targeted volatile-signal engineering characterization."""

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
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from .guards import CohortGuardError, normalize_caseid


PHASE5C_SEED = 20260720
EXPECTED_UNIVERSE_COUNT = 3219
PREFLIGHT_PER_STRATUM = 2
MAX_ATTEMPTS = 3
OFFICIAL_DATASET_OVERVIEW = (
    "https://vitaldb.net/dataset/?documentId="
    "13qqajnNZzkN7NZ9aXnaQ-47NWy7kx-a6gbrcEsi-gak"
    "&query=overview&sectionId=h.vcpgs1yemdb5"
)


@dataclass(frozen=True)
class VolatileTrackSpec:
    track_name: str
    presence_field: str
    file_stem: str
    device_group: str
    official_description: str
    official_unit: str


VOLATILE_TRACKS = (
    VolatileTrackSpec("Primus/EXP_SEVO", "primus_exp_sevo_present", "primus_exp_sevo", "primus_agent_specific", "Expiratory sevoflurane pressure", "kPa"),
    VolatileTrackSpec("Primus/INSP_SEVO", "primus_insp_sevo_present", "primus_insp_sevo", "primus_agent_specific", "Inspiratory sevoflurane pressure", "kPa"),
    VolatileTrackSpec("Primus/EXP_DES", "primus_exp_des_present", "primus_exp_des", "primus_agent_specific", "Expiratory desflurane pressure", "kPa"),
    VolatileTrackSpec("Primus/INSP_DES", "primus_insp_des_present", "primus_insp_des", "primus_agent_specific", "Inspiratory desflurane pressure", "kPa"),
    VolatileTrackSpec("Solar8000/GAS2_EXPIRED", "solar8000_gas2_expired_present", "solar8000_gas2_expired", "solar_gas2", "Expiratory volatile concentration", "%"),
    VolatileTrackSpec("Solar8000/GAS2_INSPIRED", "solar8000_gas2_inspired_present", "solar8000_gas2_inspired", "solar_gas2", "Inspiratory volatile concentration", "%"),
    VolatileTrackSpec("Primus/MAC", "primus_mac_present", "primus_mac", "primus_mac", "Minimum alveolar concentration of volatile", "unitless"),
)
ALLOWED_TRACK_NAMES = tuple(spec.track_name for spec in VOLATILE_TRACKS)
SPEC_BY_NAME = {spec.track_name: spec for spec in VOLATILE_TRACKS}


@dataclass(frozen=True)
class VolatileTask:
    caseid: int
    track_name: str
    tids: tuple[str, ...]
    anesthesia_start: float
    anesthesia_end: float
    presence_combination: str

    @property
    def key(self) -> str:
        return f"{self.caseid}|{self.track_name}"


class TrackParseError(ValueError):
    """The downloaded bytes cannot be characterized without changing the source."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_bytes(path: Path, payload: bytes) -> None:
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
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_bytes(path, payload)


def remove_stale_partials(raw_root: Path) -> list[str]:
    if not raw_root.exists():
        return []
    removed: list[str] = []
    for path in raw_root.rglob("*.part"):
        resolved = path.resolve()
        if raw_root.resolve() not in resolved.parents:
            raise CohortGuardError(f"partial path escaped raw root: {resolved}")
        path.unlink()
        removed.append(path.relative_to(raw_root).as_posix())
    return sorted(removed)


def assert_no_partials(raw_root: Path) -> None:
    residual = sorted(path.relative_to(raw_root).as_posix() for path in raw_root.rglob("*.part")) if raw_root.exists() else []
    if residual:
        raise CohortGuardError(f"partial files remain: {residual[:10]}")


def build_phase5c_universe(
    manifest_records: Sequence[Mapping[str, object]],
    presence_records: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    presence_by_case = {normalize_caseid(row["caseid"]): row for row in presence_records}
    if len(presence_by_case) != 6388:
        raise CohortGuardError("Phase 5B presence input must contain 6,388 unique cases")
    universe: list[dict[str, object]] = []
    for source in manifest_records:
        caseid = normalize_caseid(source["caseid"])
        if caseid not in presence_by_case:
            raise CohortGuardError(f"Phase 5B presence row missing for case {caseid}")
        if not all(
            source[f"{concept}_track_available"] is True
            for concept in ("bis", "propofol_rate", "remifentanil_rate")
        ):
            continue
        if source["adult_candidate"] is not True:
            continue
        if source["anesthesia_type"] != "General":
            continue
        row = {
            "caseid": caseid,
            "anesthesia_start": float(source["anesthesia_start"]),
            "anesthesia_end": float(source["anesthesia_end"]),
        }
        for spec in VOLATILE_TRACKS:
            value = presence_by_case[caseid][spec.presence_field]
            if value not in (True, False):
                raise CohortGuardError(
                    f"case {caseid} has unresolved presence field {spec.presence_field}"
                )
            row[spec.presence_field] = value
        universe.append(row)
    universe.sort(key=lambda row: int(row["caseid"]))
    caseids = [int(row["caseid"]) for row in universe]
    if len(caseids) != EXPECTED_UNIVERSE_COUNT or len(caseids) != len(set(caseids)):
        raise CohortGuardError(
            f"Phase 5C requires {EXPECTED_UNIVERSE_COUNT} unique cases, got {len(caseids)}"
        )
    return universe


def presence_combination(row: Mapping[str, object]) -> str:
    return "|".join(
        f"{spec.presence_field}={str(bool(row[spec.presence_field])).lower()}"
        for spec in VOLATILE_TRACKS
    )


def stratified_preflight_caseids(
    universe: Sequence[Mapping[str, object]],
    *,
    seed: int = PHASE5C_SEED,
    per_stratum: int = PREFLIGHT_PER_STRATUM,
) -> list[int]:
    if per_stratum < 1:
        raise ValueError("per_stratum must be positive")
    strata: dict[str, list[int]] = defaultdict(list)
    for row in universe:
        strata[presence_combination(row)].append(int(row["caseid"]))
    rng = random.Random(seed)
    selected: list[int] = []
    for combination in sorted(strata):
        members = sorted(strata[combination])
        selected.extend(rng.sample(members, min(per_stratum, len(members))))
    return sorted(selected)


def build_tasks(
    universe: Sequence[Mapping[str, object]],
    track_rows: Sequence[Mapping[str, object]],
) -> list[VolatileTask]:
    universe_by_case = {int(row["caseid"]): row for row in universe}
    tids: dict[tuple[int, str], set[str]] = defaultdict(set)
    for source in track_rows:
        name = str(source.get("tname", "")).strip()
        if name not in SPEC_BY_NAME:
            continue
        caseid = normalize_caseid(source.get("caseid"))
        if caseid not in universe_by_case:
            continue
        tid = str(source.get("tid", "")).strip()
        if not tid:
            raise CohortGuardError(f"case {caseid} {name} has an empty TID")
        tids[(caseid, name)].add(tid)

    tasks: list[VolatileTask] = []
    for caseid, row in sorted(universe_by_case.items()):
        combination = presence_combination(row)
        for spec in VOLATILE_TRACKS:
            task_tids = tuple(sorted(tids.get((caseid, spec.track_name), set())))
            expected_present = bool(row[spec.presence_field])
            if expected_present != bool(task_tids):
                raise CohortGuardError(
                    f"Phase 5B presence disagrees with /trks for case {caseid} {spec.track_name}"
                )
            tasks.append(
                VolatileTask(
                    caseid=caseid,
                    track_name=spec.track_name,
                    tids=task_tids,
                    anesthesia_start=float(row["anesthesia_start"]),
                    anesthesia_end=float(row["anesthesia_end"]),
                    presence_combination=combination,
                )
            )
    if len(tasks) != EXPECTED_UNIVERSE_COUNT * len(VOLATILE_TRACKS):
        raise CohortGuardError("Phase 5C task matrix is incomplete")
    return tasks


def _nearest_rank(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return float(ordered[rank - 1])


def _positive_run_stats(
    observations: Sequence[tuple[float | None, float | None]],
) -> tuple[int, float]:
    run_count = 0
    longest = 0.0
    start: float | None = None
    last: float | None = None
    for timestamp, value in observations:
        positive = timestamp is not None and value is not None and value > 0
        if positive:
            if start is None:
                run_count += 1
                start = timestamp
            last = timestamp
            continue
        if start is not None and last is not None:
            longest = max(longest, max(0.0, last - start))
        start = None
        last = None
    if start is not None and last is not None:
        longest = max(longest, max(0.0, last - start))
    return run_count, longest


def parse_numeric_track(
    payload: bytes,
    *,
    expected_track_name: str,
    anesthesia_start: float,
    anesthesia_end: float,
) -> dict[str, object]:
    decoded = gzip.decompress(payload) if payload.startswith(b"\x1f\x8b") else payload
    try:
        text = decoded.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TrackParseError(f"UTF-8 decode failed: {exc}") from exc
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise TrackParseError("track payload has no header") from exc
    if len(header) < 2 or header[0].strip() != "Time":
        raise TrackParseError(f"unexpected track header: {header!r}")
    if header[1].strip() != expected_track_name:
        raise TrackParseError(
            f"value-column mismatch: expected {expected_track_name!r}, got {header[1].strip()!r}"
        )

    observations: list[tuple[float | None, float | None]] = []
    finite_values: list[float] = []
    finite_timestamps: list[float] = []
    warning_flags: set[str] = set()
    sample_count = 0
    nonfinite_count = 0
    previous_timestamp: float | None = None
    seen_timestamps: set[float] = set()
    for row_number, row in enumerate(reader, start=2):
        if not row:
            continue
        sample_count += 1
        if len(row) < 2:
            raise TrackParseError(f"row {row_number} has fewer than two columns")
        try:
            timestamp = float(row[0])
        except ValueError as exc:
            raise TrackParseError(f"row {row_number} has invalid timestamp {row[0]!r}") from exc
        if not math.isfinite(timestamp):
            raise TrackParseError(f"row {row_number} has non-finite timestamp")
        if previous_timestamp is not None and timestamp < previous_timestamp:
            warning_flags.add("nonmonotonic_timestamp")
        if timestamp in seen_timestamps:
            warning_flags.add("duplicate_timestamp")
        previous_timestamp = timestamp
        seen_timestamps.add(timestamp)
        finite_timestamps.append(timestamp)
        raw_value = row[1].strip()
        if raw_value == "":
            observations.append((timestamp, None))
            continue
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise TrackParseError(f"row {row_number} has invalid value {raw_value!r}") from exc
        if not math.isfinite(value):
            nonfinite_count += 1
            warning_flags.add("nonfinite_value")
            observations.append((timestamp, None))
            continue
        if value < 0:
            warning_flags.add("negative_value")
        finite_values.append(value)
        observations.append((timestamp, value))

    anesthesia_observations = [
        item
        for item in observations
        if item[0] is not None and anesthesia_start <= item[0] <= anesthesia_end
    ]
    positive_run_count, longest_positive = _positive_run_stats(observations)
    window_run_count, window_longest_positive = _positive_run_stats(
        anesthesia_observations
    )
    positive_count = sum(value is not None and value > 0 for _, value in observations)
    zero_count = sum(value == 0 for _, value in observations if value is not None)
    negative_count = sum(value is not None and value < 0 for _, value in observations)
    window_positive_count = sum(
        value is not None and value > 0 for _, value in anesthesia_observations
    )
    summary: dict[str, object] = {
        "sample_count": sample_count,
        "non_missing_sample_count": len(finite_values),
        "nonfinite_sample_count": nonfinite_count,
        "observed_start_timestamp": min(finite_timestamps) if finite_timestamps else None,
        "observed_end_timestamp": max(finite_timestamps) if finite_timestamps else None,
        "anesthesia_window_sample_count": len(anesthesia_observations),
        "minimum": min(finite_values) if finite_values else None,
        "maximum": max(finite_values) if finite_values else None,
        "value_equal_zero_count": zero_count,
        "value_positive_count": positive_count,
        "value_positive_fraction": positive_count / len(finite_values) if finite_values else None,
        "value_negative_count": negative_count,
        "anesthesia_window_positive_count": window_positive_count,
        "anesthesia_window_positive_observed": window_positive_count > 0,
        "positive_run_count": positive_run_count,
        "longest_positive_run_seconds": longest_positive,
        "anesthesia_window_positive_run_count": window_run_count,
        "anesthesia_window_longest_positive_run_seconds": window_longest_positive,
        "warning_flags": sorted(warning_flags),
        "processing": {
            "resampling": False,
            "interpolation": False,
            "smoothing": False,
            "clipping": False,
            "quantile_method": "nearest_rank_observed_values",
        },
    }
    for label, probability in (
        ("q01", 0.01),
        ("q05", 0.05),
        ("q25", 0.25),
        ("q50", 0.50),
        ("q75", 0.75),
        ("q95", 0.95),
        ("q99", 0.99),
    ):
        summary[label] = _nearest_rank(finite_values, probability)
    return summary


def task_paths(raw_root: Path, task: VolatileTask) -> tuple[Path, Path]:
    spec = SPEC_BY_NAME[task.track_name]
    case_root = raw_root / "cases" / str(task.caseid)
    return case_root / f"{spec.file_stem}.signal", case_root / f"{spec.file_stem}.metadata.json"


def load_verified_metadata(raw_root: Path, task: VolatileTask) -> dict[str, object] | None:
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
        or metadata.get("raw_relative_path")
        != signal_path.relative_to(raw_root).as_posix()
    ):
        return None
    expected = metadata.get("raw_sha256")
    if not isinstance(expected, str) or sha256_path(signal_path) != expected:
        return None
    return metadata


class ProgressLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.attempts: Counter[str] = Counter()
        self.last_events: dict[str, dict[str, object]] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                row = json.loads(line)
                if row.get("event") == "attempt_finished":
                    key = str(row["task_key"])
                    self.attempts[key] += 1
                    self.last_events[key] = row

    def attempt_count(self, task: VolatileTask) -> int:
        with self.lock:
            return int(self.attempts[task.key])

    def last_event(self, task: VolatileTask) -> dict[str, object] | None:
        with self.lock:
            event = self.last_events.get(task.key)
            return dict(event) if event is not None else None

    def append(self, row: Mapping[str, object]) -> None:
        payload = json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if row.get("event") == "attempt_finished":
                key = str(row["task_key"])
                self.attempts[key] += 1
                self.last_events[key] = dict(row)


def download_one_task(
    task: VolatileTask,
    *,
    raw_root: Path,
    client: object,
    progress: ProgressLog,
    source_version: str,
) -> dict[str, object]:
    if len(task.tids) != 1:
        raise CohortGuardError("download_one_task requires exactly one TID")
    existing = load_verified_metadata(raw_root, task)
    if existing is not None:
        return existing
    attempt_count = progress.attempt_count(task)
    if attempt_count >= MAX_ATTEMPTS:
        previous = progress.last_event(task)
        if previous is None:
            raise CohortGuardError(f"attempt budget exhausted without state for {task.key}")
        prior_status = str(previous.get("status", "download_failed"))
        failure_type = previous.get("failure_type")
        failure_message = previous.get("failure_message")
        if prior_status in {"complete", "empty_signal", "parsing_failed"}:
            prior_status = "download_failed"
            failure_type = "ChecksumMismatchAttemptBudgetExhausted"
            failure_message = "stored raw artifact or metadata failed checksum verification"
        return {
            "caseid": task.caseid,
            "track_name": task.track_name,
            "tid": task.tids[0],
            "status": prior_status,
            "attempt_count": attempt_count,
            "started_at": None,
            "completed_at": previous.get("timestamp"),
            "raw_relative_path": None,
            "raw_byte_count": 0,
            "raw_sha256": None,
            "source_version": source_version,
            "response_metadata": None,
            "parsing": None,
            "failure_type": failure_type,
            "failure_message": failure_message,
            "retryable": bool(previous.get("retryable", False)),
        }
    last_failure: dict[str, object] | None = None
    while attempt_count < MAX_ATTEMPTS:
        attempt_count += 1
        started_at = datetime.now(UTC).isoformat()
        retryable = False
        try:
            payload, response_metadata = client.fetch_track(task.tids[0])
            if not payload:
                raise TrackParseError("empty response payload")
            raw_sha256 = sha256_bytes(payload)
            signal_path, metadata_path = task_paths(raw_root, task)
            _atomic_bytes(signal_path, payload)
            try:
                parsing = parse_numeric_track(
                    payload,
                    expected_track_name=task.track_name,
                    anesthesia_start=task.anesthesia_start,
                    anesthesia_end=task.anesthesia_end,
                )
                status = "empty_signal" if parsing["sample_count"] == 0 else "complete"
                failure_type = None
                failure_message = None
            except TrackParseError as exc:
                parsing = None
                status = "parsing_failed"
                failure_type = type(exc).__name__
                failure_message = str(exc)
            metadata = {
                "caseid": task.caseid,
                "track_name": task.track_name,
                "tid": task.tids[0],
                "status": status,
                "attempt_count": attempt_count,
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "raw_relative_path": signal_path.relative_to(raw_root).as_posix(),
                "raw_byte_count": len(payload),
                "raw_sha256": raw_sha256,
                "source_version": source_version,
                "response_metadata": response_metadata,
                "parsing": parsing,
                "failure_type": failure_type,
                "failure_message": failure_message,
                "retryable": False,
            }
            atomic_json(metadata_path, metadata)
            progress.append(
                {
                    "event": "attempt_finished",
                    "task_key": task.key,
                    "caseid": task.caseid,
                    "track_name": task.track_name,
                    "attempt": attempt_count,
                    "timestamp": metadata["completed_at"],
                    "status": status,
                    "failure_type": failure_type,
                    "failure_message": failure_message,
                    "retryable": False,
                }
            )
            return metadata
        except Exception as exc:
            retryable = isinstance(exc, requests.RequestException)
            last_failure = {
                "caseid": task.caseid,
                "track_name": task.track_name,
                "tid": task.tids[0],
                "status": "download_failed",
                "attempt_count": attempt_count,
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "raw_relative_path": None,
                "raw_byte_count": 0,
                "raw_sha256": None,
                "source_version": source_version,
                "response_metadata": None,
                "parsing": None,
                "failure_type": type(exc).__name__,
                "failure_message": str(exc),
                "retryable": retryable,
            }
            progress.append(
                {
                    "event": "attempt_finished",
                    "task_key": task.key,
                    "caseid": task.caseid,
                    "track_name": task.track_name,
                    "attempt": attempt_count,
                    "timestamp": last_failure["completed_at"],
                    "status": "download_failed",
                    "failure_type": type(exc).__name__,
                    "failure_message": str(exc),
                    "retryable": retryable,
                }
            )
            if not retryable:
                break
    assert last_failure is not None
    return last_failure


def track_manifest_row(
    task: VolatileTask,
    metadata: Mapping[str, object] | None,
    *,
    raw_root: Path,
    source_version: str,
) -> dict[str, object]:
    spec = SPEC_BY_NAME[task.track_name]
    base: dict[str, object] = {
        "caseid": task.caseid,
        "track_name": task.track_name,
        "official_description": spec.official_description,
        "official_unit": spec.official_unit,
        "unit_review_status": "pending_human_review",
        "track_present": bool(task.tids),
        "tid_count": len(task.tids),
        "tids": list(task.tids),
        "download_status": "track_absent" if not task.tids else "not_completed",
        "attempt_count": 0,
        "raw_relative_path": None,
        "raw_byte_count": 0,
        "raw_sha256": None,
        "source_version": source_version,
        "failure_type": None,
        "failure_message": None,
        "retryable": False,
        "sample_count": None,
        "non_missing_sample_count": None,
        "nonfinite_sample_count": None,
        "observed_start_timestamp": None,
        "observed_end_timestamp": None,
        "anesthesia_window_sample_count": None,
        "minimum": None,
        "maximum": None,
        "q01": None,
        "q05": None,
        "q25": None,
        "q50": None,
        "q75": None,
        "q95": None,
        "q99": None,
        "value_equal_zero_count": None,
        "value_positive_count": None,
        "value_positive_fraction": None,
        "value_negative_count": None,
        "anesthesia_window_positive_count": None,
        "anesthesia_window_positive_observed": None,
        "positive_run_count": None,
        "longest_positive_run_seconds": None,
        "anesthesia_window_positive_run_count": None,
        "anesthesia_window_longest_positive_run_seconds": None,
        "warning_flags": [],
        "resampling_performed": False,
        "interpolation_performed": False,
        "smoothing_performed": False,
        "clipping_performed": False,
    }
    if len(task.tids) > 1:
        base.update(
            download_status="ambiguous_multiple_tids",
            failure_type="MultipleExactTrackTids",
            failure_message="multiple exact TIDs were not merged",
        )
        return base
    if metadata is None:
        return base
    base.update(
        download_status=metadata["status"],
        attempt_count=int(metadata["attempt_count"]),
        raw_relative_path=metadata.get("raw_relative_path"),
        raw_byte_count=int(metadata.get("raw_byte_count", 0)),
        raw_sha256=metadata.get("raw_sha256"),
        failure_type=metadata.get("failure_type"),
        failure_message=metadata.get("failure_message"),
        retryable=bool(metadata.get("retryable", False)),
    )
    parsing = metadata.get("parsing")
    if isinstance(parsing, dict):
        for key in (
            "sample_count", "non_missing_sample_count", "nonfinite_sample_count",
            "observed_start_timestamp", "observed_end_timestamp",
            "anesthesia_window_sample_count", "minimum", "maximum",
            "q01", "q05", "q25", "q50", "q75", "q95", "q99",
            "value_equal_zero_count", "value_positive_count", "value_positive_fraction",
            "value_negative_count", "anesthesia_window_positive_count",
            "anesthesia_window_positive_observed", "positive_run_count",
            "longest_positive_run_seconds", "anesthesia_window_positive_run_count",
            "anesthesia_window_longest_positive_run_seconds", "warning_flags",
        ):
            base[key] = parsing[key]
    return base


def _metric_distribution(values: Sequence[object]) -> dict[str, object]:
    numeric = [float(value) for value in values if value is not None]
    return {
        "available_count": len(numeric),
        "missing_count": len(values) - len(numeric),
        "minimum": min(numeric) if numeric else None,
        "q05": _nearest_rank(numeric, 0.05),
        "q25": _nearest_rank(numeric, 0.25),
        "q50": _nearest_rank(numeric, 0.50),
        "q75": _nearest_rank(numeric, 0.75),
        "q95": _nearest_rank(numeric, 0.95),
        "maximum": max(numeric) if numeric else None,
        "method": "nearest_rank_across_case_level_metrics",
    }


def build_case_manifest(
    universe: Sequence[Mapping[str, object]],
    track_rows: Sequence[Mapping[str, object]],
    *,
    source_version: str,
) -> list[dict[str, object]]:
    tracks_by_case: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in track_rows:
        tracks_by_case[int(row["caseid"])].append(row)
    result: list[dict[str, object]] = []
    for source in universe:
        caseid = int(source["caseid"])
        rows = tracks_by_case.get(caseid, [])
        if len(rows) != len(VOLATILE_TRACKS):
            raise CohortGuardError(f"case {caseid} lacks seven track-manifest rows")
        present = [row for row in rows if row["track_present"] is True]
        failures = [
            row
            for row in present
            if row["download_status"] not in {"complete", "empty_signal"}
        ]
        empty = [row for row in present if row["download_status"] == "empty_signal"]
        if failures:
            case_status = "failed"
        elif not present:
            case_status = "complete_no_allowed_tracks_present"
        elif empty:
            case_status = "complete_with_empty_signal"
        else:
            case_status = "complete"

        def window_positive(group: str | None = None) -> bool:
            return any(
                row["anesthesia_window_positive_observed"] is True
                and (group is None or SPEC_BY_NAME[str(row["track_name"])].device_group == group)
                for row in rows
            )

        any_positive = any(
            isinstance(row["value_positive_count"], int)
            and int(row["value_positive_count"]) > 0
            for row in rows
        )
        all_zero_present_count = sum(
            row["download_status"] == "complete"
            and int(row["non_missing_sample_count"] or 0) > 0
            and int(row["value_positive_count"] or 0) == 0
            and int(row["value_negative_count"] or 0) == 0
            for row in present
        )
        result.append(
            {
                "caseid": caseid,
                "analysis_universe": "exact_primary_plus_adult_plus_exact_general",
                "analysis_universe_frozen": False,
                "anesthesia_start": float(source["anesthesia_start"]),
                "anesthesia_end": float(source["anesthesia_end"]),
                "presence_combination": presence_combination(source),
                "allowed_track_present_count": len(present),
                "allowed_track_absent_count": len(rows) - len(present),
                "download_complete_count": sum(row["download_status"] == "complete" for row in rows),
                "empty_signal_count": len(empty),
                "failed_track_count": len(failures),
                "case_characterization_status": case_status,
                "any_positive_observed_anywhere": any_positive,
                "any_positive_observed_in_anesthesia_window": window_positive(),
                "agent_specific_positive_in_anesthesia_window": window_positive("primus_agent_specific"),
                "gas2_positive_in_anesthesia_window": window_positive("solar_gas2"),
                "mac_positive_in_anesthesia_window": window_positive("primus_mac"),
                "track_present_all_zero_count": all_zero_present_count,
                "warning_track_count": sum(bool(row["warning_flags"]) for row in rows),
                "volatile_exposure_decision": "pending_human_review",
                "tiva_decision": "pending_human_review",
                "final_eligibility": "pending_human_review",
                "legacy_overlap": "pending_not_evaluated",
                "source_version": source_version,
            }
        )
    if len(result) != EXPECTED_UNIVERSE_COUNT:
        raise CohortGuardError("case manifest does not account for all 3,219 cases")
    return result


def _fixed_boundary_sample(
    case_rows: Sequence[Mapping[str, object]],
    *,
    seed: int = PHASE5C_SEED,
    per_category: int = 5,
) -> dict[str, list[int]]:
    categories = {
        "present_track_all_zero": [
            int(row["caseid"])
            for row in case_rows
            if int(row["track_present_all_zero_count"]) > 0
        ],
        "positive_only_outside_anesthesia_window": [
            int(row["caseid"])
            for row in case_rows
            if row["any_positive_observed_anywhere"] is True
            and row["any_positive_observed_in_anesthesia_window"] is False
        ],
        "agent_specific_vs_gas2_or_mac_discordant": [
            int(row["caseid"])
            for row in case_rows
            if bool(row["agent_specific_positive_in_anesthesia_window"])
            != bool(
                row["gas2_positive_in_anesthesia_window"]
                or row["mac_positive_in_anesthesia_window"]
            )
        ],
        "download_parse_or_value_warning": [
            int(row["caseid"])
            for row in case_rows
            if int(row["failed_track_count"]) > 0 or int(row["warning_track_count"]) > 0
        ],
    }
    samples: dict[str, list[int]] = {}
    for offset, (category, caseids) in enumerate(sorted(categories.items())):
        rng = random.Random(seed + offset)
        members = sorted(set(caseids))
        samples[category] = sorted(rng.sample(members, min(per_category, len(members))))
    return samples


def summarize_volatile_characterization(
    case_rows: Sequence[Mapping[str, object]],
    track_rows: Sequence[Mapping[str, object]],
    *,
    source_version: str,
) -> dict[str, object]:
    if len(case_rows) != EXPECTED_UNIVERSE_COUNT:
        raise CohortGuardError("aggregate summary requires exactly 3,219 cases")
    if len(track_rows) != EXPECTED_UNIVERSE_COUNT * len(VOLATILE_TRACKS):
        raise CohortGuardError("aggregate summary requires the complete case-track matrix")
    caseids = [int(row["caseid"]) for row in case_rows]
    if len(caseids) != len(set(caseids)):
        raise CohortGuardError("duplicate case rows in Phase 5C manifest")
    by_track: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in track_rows:
        by_track[str(row["track_name"])].append(row)
    track_summaries: dict[str, object] = {}
    for spec in VOLATILE_TRACKS:
        rows = by_track[spec.track_name]
        present = [row for row in rows if row["track_present"] is True]
        status_counts = Counter(str(row["download_status"]) for row in rows)
        track_summaries[spec.track_name] = {
            "official_description": spec.official_description,
            "official_unit": spec.official_unit,
            "unit_review_status": "pending_human_review",
            "case_count": len(rows),
            "present_case_count": len(present),
            "absent_case_count": len(rows) - len(present),
            "download_status_counts": dict(sorted(status_counts.items())),
            "present_all_observed_values_zero_case_count": sum(
                row["download_status"] == "complete"
                and int(row["non_missing_sample_count"] or 0) > 0
                and int(row["value_positive_count"] or 0) == 0
                and int(row["value_negative_count"] or 0) == 0
                for row in present
            ),
            "anesthesia_window_positive_case_count": sum(
                row["anesthesia_window_positive_observed"] is True for row in present
            ),
            "case_level_metric_distributions": {
                field: _metric_distribution([row[field] for row in present])
                for field in (
                    "minimum",
                    "q05",
                    "q25",
                    "q50",
                    "q75",
                    "q95",
                    "maximum",
                    "value_positive_fraction",
                    "longest_positive_run_seconds",
                    "anesthesia_window_longest_positive_run_seconds",
                )
            },
        }

    presence_counts = Counter(str(row["presence_combination"]) for row in case_rows)
    group_counts = Counter(
        "|".join(
            (
                f"agent_specific_positive={str(bool(row['agent_specific_positive_in_anesthesia_window'])).lower()}",
                f"gas2_positive={str(bool(row['gas2_positive_in_anesthesia_window'])).lower()}",
                f"mac_positive={str(bool(row['mac_positive_in_anesthesia_window'])).lower()}",
            )
        )
        for row in case_rows
    )
    exposure_scenarios = [
        {
            "definition": "any_allowed_track_positive_anywhere",
            "descriptive_case_count": sum(row["any_positive_observed_anywhere"] is True for row in case_rows),
        },
        {
            "definition": "any_allowed_track_positive_in_anesthesia_window",
            "descriptive_case_count": sum(row["any_positive_observed_in_anesthesia_window"] is True for row in case_rows),
        },
        {
            "definition": "primus_agent_specific_positive_in_anesthesia_window",
            "descriptive_case_count": sum(row["agent_specific_positive_in_anesthesia_window"] is True for row in case_rows),
        },
        {
            "definition": "solar_gas2_positive_in_anesthesia_window",
            "descriptive_case_count": sum(row["gas2_positive_in_anesthesia_window"] is True for row in case_rows),
        },
        {
            "definition": "primus_mac_positive_in_anesthesia_window",
            "descriptive_case_count": sum(row["mac_positive_in_anesthesia_window"] is True for row in case_rows),
        },
        {
            "definition": "agent_specific_and_gas2_or_mac_positive_in_anesthesia_window",
            "descriptive_case_count": sum(
                row["agent_specific_positive_in_anesthesia_window"] is True
                and (
                    row["gas2_positive_in_anesthesia_window"] is True
                    or row["mac_positive_in_anesthesia_window"] is True
                )
                for row in case_rows
            ),
        },
    ]
    failure_types = Counter(
        str(row["failure_type"])
        for row in track_rows
        if row["failure_type"] not in (None, "")
    )
    return {
        "phase": "5C_targeted_volatile_signal_characterization",
        "scientific_result": False,
        "decision_support_only": True,
        "analysis_universe": {
            "definition": "exact primary tracks + age >= 18 + anesthesia_type exact General",
            "case_count": len(case_rows),
            "cohort_frozen": False,
            "caseid_fingerprint_sha256": hashlib.sha256(
                ",".join(str(caseid) for caseid in sorted(caseids)).encode("ascii")
            ).hexdigest(),
            "duplicate_case_count": len(caseids) - len(set(caseids)),
            "missing_case_count": EXPECTED_UNIVERSE_COUNT - len(set(caseids)),
        },
        "allowed_exact_tracks": [
            {
                "track_name": spec.track_name,
                "official_description": spec.official_description,
                "official_unit": spec.official_unit,
                "approval_status": "pending_human_review",
            }
            for spec in VOLATILE_TRACKS
        ],
        "source_version": source_version,
        "track_presence_combination_counts": dict(sorted(presence_counts.items())),
        "track_summaries": track_summaries,
        "primus_agent_specific_gas2_mac_positive_combination_counts": dict(sorted(group_counts.items())),
        "manual_review_fixed_seed": PHASE5C_SEED,
        "manual_review_boundary_samples": _fixed_boundary_sample(case_rows),
        "possible_exposure_definition_counts": exposure_scenarios,
        "selected_exposure_definition": None,
        "failure_type_counts": dict(sorted(failure_types.items())),
        "processing": {
            "original_timestamps_used": True,
            "resampling": False,
            "interpolation": False,
            "smoothing": False,
            "clipping": False,
            "abnormal_values_deleted": False,
        },
        "pending_decisions": [
            "volatile_exposure_definition",
            "tiva_classification",
            "final_alias_approval",
            "final_unit_approval",
            "signal_quality_thresholds",
            "legacy_98_overlap",
            "final_eligibility",
        ],
        "execution_flags": {
            "legacy_98_ids_accessed": False,
            "cohort_frozen": False,
            "split_created": False,
            "bis_signal_downloaded": False,
            "propofol_signal_downloaded": False,
            "remifentanil_signal_downloaded": False,
            "prediction_dataset_preprocessed": False,
            "prediction_run": False,
            "feature_selection_run": False,
            "cpce_reconstruction_run": False,
            "ppo_run": False,
            "quality_thresholds_finalized": False,
            "alias_configuration_changed": False,
        },
    }


def build_preflight_summary(
    universe: Sequence[Mapping[str, object]],
    tasks: Sequence[VolatileTask],
    selected_caseids: Sequence[int],
    metadata_by_key: Mapping[str, Mapping[str, object]],
    *,
    raw_root: Path,
    source_version: str,
    disk_free_bytes: int,
    workers: int,
) -> dict[str, object]:
    selected = set(selected_caseids)
    universe_strata = Counter(presence_combination(row) for row in universe)
    universe_combo_by_case = {
        int(row["caseid"]): presence_combination(row) for row in universe
    }
    bytes_by_case: Counter[int] = Counter()
    seconds_by_case: Counter[int] = Counter()
    requested_tasks = [task for task in tasks if task.caseid in selected and len(task.tids) == 1]
    failure_types: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for task in requested_tasks:
        metadata = metadata_by_key.get(task.key)
        if metadata is None:
            statuses["not_completed"] += 1
            failure_types["missing_preflight_result"] += 1
            continue
        status = str(metadata["status"])
        statuses[status] += 1
        bytes_by_case[task.caseid] += int(metadata.get("raw_byte_count", 0))
        response = metadata.get("response_metadata")
        if isinstance(response, dict):
            seconds_by_case[task.caseid] += float(response.get("elapsed_seconds", 0.0))
        if metadata.get("failure_type"):
            failure_types[str(metadata["failure_type"])] += 1

    sample_cases_by_stratum: dict[str, list[int]] = defaultdict(list)
    for caseid in selected_caseids:
        sample_cases_by_stratum[universe_combo_by_case[int(caseid)]].append(int(caseid))
    raw_estimate = 0.0
    worker_seconds_estimate = 0.0
    strata_estimates: list[dict[str, object]] = []
    for combination, population_count in sorted(universe_strata.items()):
        sample_members = sample_cases_by_stratum[combination]
        mean_bytes = statistics.mean(bytes_by_case[caseid] for caseid in sample_members)
        mean_seconds = statistics.mean(seconds_by_case[caseid] for caseid in sample_members)
        raw_estimate += mean_bytes * population_count
        worker_seconds_estimate += mean_seconds * population_count
        strata_estimates.append(
            {
                "presence_combination": combination,
                "population_case_count": population_count,
                "sample_caseids": sorted(sample_members),
                "mean_download_bytes_per_sample_case": mean_bytes,
                "mean_request_seconds_per_sample_case": mean_seconds,
            }
        )
    expected_total_bytes = math.ceil(raw_estimate * 1.20 + 50 * 1024 * 1024)
    required_free_bytes = expected_total_bytes * 2
    operational_gate = not failure_types and statuses.get("not_completed", 0) == 0
    disk_gate = disk_free_bytes >= required_free_bytes
    return {
        "phase": "5C_targeted_volatile_signal_characterization_preflight",
        "engineering_only": True,
        "scientific_result": False,
        "seed": PHASE5C_SEED,
        "sampling_method": "fixed_seed_stratified_by_exact_track_presence_combination",
        "cases_per_stratum": PREFLIGHT_PER_STRATUM,
        "universe_case_count": len(universe),
        "presence_stratum_count": len(universe_strata),
        "sample_case_count": len(selected_caseids),
        "sample_caseids": sorted(selected_caseids),
        "requested_present_track_count": len(requested_tasks),
        "request_status_counts": dict(sorted(statuses.items())),
        "failure_type_counts": dict(sorted(failure_types.items())),
        "observed_total_raw_bytes": sum(bytes_by_case.values()),
        "observed_total_request_seconds": sum(seconds_by_case.values()),
        "strata_estimates": strata_estimates,
        "estimated_full_raw_bytes": math.ceil(raw_estimate),
        "estimate_overhead_policy": "20_percent_plus_50_MiB",
        "estimated_full_required_bytes": expected_total_bytes,
        "disk_free_bytes": disk_free_bytes,
        "disk_gate_required_free_bytes": required_free_bytes,
        "disk_gate_policy": "available_free_space_at_least_2x_estimated_full_required_bytes",
        "disk_gate_passed": disk_gate,
        "operational_gate_passed": operational_gate,
        "full_download_authorized_by_gate": disk_gate and operational_gate,
        "workers_for_estimate": workers,
        "estimated_full_wall_seconds": worker_seconds_estimate / max(1, workers),
        "source_version": source_version,
        "raw_root": Path(*raw_root.parts[-3:]).as_posix(),
        "raw_signals_git_ignored": True,
    }


def render_preflight_report(summary: Mapping[str, object]) -> str:
    gib = 1024 ** 3
    lines = [
        "# Phase 5C Stratified Engineering Preflight",
        "",
        "This fixed-seed preflight is engineering evidence only. It does not define",
        "volatile exposure, TIVA status, eligibility, or a cohort.",
        "",
        "| Measure | Value |",
        "|---|---:|",
        f"| Universe cases | {summary['universe_case_count']} |",
        f"| Presence strata | {summary['presence_stratum_count']} |",
        f"| Preflight cases | {summary['sample_case_count']} |",
        f"| Present-track requests | {summary['requested_present_track_count']} |",
        f"| Observed raw bytes | {summary['observed_total_raw_bytes']} |",
        f"| Estimated full requirement (GiB) | {summary['estimated_full_required_bytes'] / gib:.3f} |",
        f"| Available disk (GiB) | {summary['disk_free_bytes'] / gib:.3f} |",
        f"| Required by 2x gate (GiB) | {summary['disk_gate_required_free_bytes'] / gib:.3f} |",
        f"| Estimated full wall time at {summary['workers_for_estimate']} workers (s) | {summary['estimated_full_wall_seconds']:.1f} |",
        f"| Disk gate passed | {summary['disk_gate_passed']} |",
        f"| Operational gate passed | {summary['operational_gate_passed']} |",
        f"| Full download authorized | {summary['full_download_authorized_by_gate']} |",
        "",
        "## Request outcomes",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status, count in summary["request_status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "No BIS, propofol, remifentanil, CP, CE, or VOL signal was requested.",
            "Raw volatile signals remain under the Git-ignored raw-data root.",
            "",
        ]
    )
    return "\n".join(lines)


def render_volatile_report(summary: Mapping[str, object], preflight: Mapping[str, object]) -> str:
    def metric_triplet(distribution: Mapping[str, object]) -> str:
        def display(value: object) -> str:
            if value is None:
                return "NA"
            return f"{float(value):.4g}"

        return " / ".join(display(distribution[key]) for key in ("q05", "q50", "q95"))

    def readable_combination(combination: str) -> str:
        return combination.replace("_present=", "=").replace("|", "; ")

    universe = summary["analysis_universe"]
    lines = [
        "# Phase 5C Targeted Volatile-Signal Characterization",
        "",
        "## Interpretation boundary",
        "",
        "This is outcome-blind eligibility decision support. Track presence is not",
        "volatile exposure, and a positive recorded value is not a finalized TIVA",
        "exclusion rule. No exposure definition or cutoff was selected.",
        "",
        "## Accounting and preflight gate",
        "",
        "| Measure | Count / status |",
        "|---|---:|",
        f"| Analysis-universe cases | {universe['case_count']} |",
        f"| Duplicate cases | {universe['duplicate_case_count']} |",
        f"| Missing cases | {universe['missing_case_count']} |",
        f"| Case×track rows | {universe['case_count'] * len(VOLATILE_TRACKS)} |",
        f"| Preflight disk gate | {preflight['disk_gate_passed']} |",
        f"| Preflight operational gate | {preflight['operational_gate_passed']} |",
        "",
        "## Track outcomes and descriptive positive recording",
        "",
        "| Exact track | Present | Complete | Empty | Failed | All observed values zero | Positive in anesthesia window |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in summary["track_summaries"].items():
        statuses = item["download_status_counts"]
        failed = sum(
            count
            for status, count in statuses.items()
            if status not in {"complete", "empty_signal", "track_absent"}
        )
        lines.append(
            f"| `{name}` | {item['present_case_count']} | {statuses.get('complete', 0)} | "
            f"{statuses.get('empty_signal', 0)} | {failed} | "
            f"{item['present_all_observed_values_zero_case_count']} | "
            f"{item['anesthesia_window_positive_case_count']} |"
        )
    lines.extend(
        [
            "",
            "## Track-level distributions of case summaries",
            "",
            "Each cell below is the across-case q05 / q50 / q95 of the named case-level",
            "summary. This avoids silently weighting cases by their number of recorded samples.",
            "",
            "| Exact track | Case empirical median | Case maximum | Positive fraction | Longest positive run in anesthesia window (s) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, item in summary["track_summaries"].items():
        metrics = item["case_level_metric_distributions"]
        lines.append(
            f"| `{name}` | {metric_triplet(metrics['q50'])} | "
            f"{metric_triplet(metrics['maximum'])} | "
            f"{metric_triplet(metrics['value_positive_fraction'])} | "
            f"{metric_triplet(metrics['anesthesia_window_longest_positive_run_seconds'])} |"
        )
    lines.extend(
        [
            "",
            "All per-case minimum, empirical quantiles, maximum, counts, fractions, and",
            "positive-run measures remain in the machine-readable summary and track manifest.",
            "Quantiles use observed values only; no resampling, interpolation, smoothing,",
            "clipping, or abnormal-value deletion was performed.",
            "",
            "## Exact track-presence combinations",
            "",
            "| Exact-track presence combination | Cases |",
            "|---|---:|",
        ]
    )
    for combination, count in summary["track_presence_combination_counts"].items():
        lines.append(f"| `{readable_combination(combination)}` | {count} |")
    lines.extend(
        [
            "",
            "## Primus agent-specific, GAS2, and MAC positive-recording combinations",
            "",
            "These are descriptive anesthesia-window recording combinations, not exposure",
            "or TIVA classifications.",
            "",
            "| Recorded-positive combination | Cases |",
            "|---|---:|",
        ]
    )
    for combination, count in summary[
        "primus_agent_specific_gas2_mac_positive_combination_counts"
    ].items():
        lines.append(f"| `{combination.replace('|', '; ')}` | {count} |")
    lines.extend(
        [
            "",
            f"## Fixed-seed boundary samples (seed {summary['manual_review_fixed_seed']})",
            "",
            "| Review category | Case IDs |",
            "|---|---|",
        ]
    )
    for category, caseids in summary["manual_review_boundary_samples"].items():
        displayed = ", ".join(str(caseid) for caseid in caseids) or "none"
        lines.append(f"| `{category}` | {displayed} |")
    lines.extend(
        [
            "",
            "",
            "## Possible exposure definitions — descriptive comparison only",
            "",
            "| Candidate definition | Cases |",
            "|---|---:|",
        ]
    )
    for scenario in summary["possible_exposure_definition_counts"]:
        lines.append(
            f"| `{scenario['definition']}` | {scenario['descriptive_case_count']} |"
        )
    lines.extend(
        [
            "",
            "## Primary-source descriptions",
            "",
            "The official VitalDB overview describes Primus sevoflurane/desflurane",
            "tracks in kPa, Solar8000 GAS2 tracks in %, and Primus/MAC as unitless.",
            "These descriptions are recorded without changing versioned approval status.",
            "",
            f"- [Official VitalDB dataset overview]({OFFICIAL_DATASET_OVERVIEW})",
            "",
            "## Work deliberately not performed",
            "",
            "Legacy 98 IDs were not accessed. No final volatile/TIVA determination, alias",
            "or unit approval, threshold, cohort freeze, split, BIS/drug signal download,",
            "prediction preprocessing, prediction, feature selection, Cp/Ce reconstruction,",
            "or PPO execution occurred. Phase 5C stops here.",
            "",
        ]
    )
    return "\n".join(lines)

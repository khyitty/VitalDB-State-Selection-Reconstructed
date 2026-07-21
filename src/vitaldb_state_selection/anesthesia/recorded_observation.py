"""Strict loader for ignored, train-only Phase 8B observation templates."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from vitaldb_state_selection.cohort.split_guard import SplitGuard, SplitGuardError
from vitaldb_state_selection.cohort.train_observation_templates import (
    EXPECTED_TRAIN_CASES,
    SCHEMA_VERSION,
    TEMPLATE_FORMAT_VERSION,
    private_store_root_sha256,
    template_id_for_case,
    verify_complete_template,
)

from .observation import BISEvent, SQIEvent


class RecordedObservationError(RuntimeError):
    """Raised when private template structure or train membership is invalid."""


@dataclass(frozen=True, slots=True)
class RecordedObservationTemplate:
    template_id: str
    episode_horizon_seconds: float
    bis_events: tuple[BISEvent, ...]
    sqi_events: tuple[SQIEvent, ...]
    source_type: str = "vitaldb_train"

    def __post_init__(self) -> None:
        if self.source_type not in {"vitaldb_train", "vitaldb_test"} or not self.template_id:
            raise RecordedObservationError("recorded template identity or source type is invalid")
        horizon = float(self.episode_horizon_seconds)
        if not math.isfinite(horizon) or horizon <= 0:
            raise RecordedObservationError("recorded template horizon must be finite and positive")
        for events, label in ((self.bis_events, "BIS"), (self.sqi_events, "SQI")):
            timestamps = [event.timestamp_seconds for event in events]
            if any(not math.isfinite(value) or not 0.0 <= value <= horizon for value in timestamps):
                raise RecordedObservationError(f"{label} timestamp outside template horizon")
            if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
                raise RecordedObservationError(f"{label} timestamps must be strictly increasing")
        bis_timestamps = {event.timestamp_seconds for event in self.bis_events}
        if any(event.timestamp_seconds not in bis_timestamps for event in self.sqi_events):
            raise RecordedObservationError("SQI timestamp is not an exact BIS timestamp")
        if any(not math.isfinite(event.value) for event in self.sqi_events):
            raise RecordedObservationError("SQI value must be finite")
        object.__setattr__(self, "episode_horizon_seconds", horizon)

    def bis_between(self, start: float, end: float) -> tuple[BISEvent, ...]:
        return tuple(event for event in self.bis_events if start < event.timestamp_seconds <= end)

    def sqi_between(self, start: float, end: float) -> tuple[SQIEvent, ...]:
        return tuple(event for event in self.sqi_events if start < event.timestamp_seconds <= end)

    def sqi_exact(self, timestamp: float) -> float | None:
        for event in self.sqi_events:
            if event.timestamp_seconds == timestamp:
                return event.value
        return None


def _load_array(path: Path, expected_dtype: np.dtype) -> np.ndarray:
    try:
        array = np.load(path, allow_pickle=False)
    except (ValueError, OSError) as error:
        raise RecordedObservationError(f"private array could not be loaded safely: {path.name}") from error
    if array.dtype.hasobject or array.dtype != expected_dtype:
        raise RecordedObservationError(f"unexpected private array dtype: {path.name}: {array.dtype}")
    if array.ndim != 1 or not array.flags.c_contiguous:
        raise RecordedObservationError(f"private array must be one-dimensional and C-contiguous: {path.name}")
    return array


def load_recorded_template(
    directory: Path | str,
    *,
    split_guard: SplitGuard,
    expected_index_row: dict[str, str] | None = None,
) -> RecordedObservationTemplate:
    directory = Path(directory)
    try:
        fingerprint, metadata = verify_complete_template(directory)
    except Exception as error:
        raise RecordedObservationError(str(error)) from error
    required_metadata = {
        "schema_version": SCHEMA_VERSION,
        "template_format_version": TEMPLATE_FORMAT_VERSION,
        "source_type": "vitaldb_train",
        "assigned_split": "train",
        "raw_bis_values_persisted": False,
        "raw_sqi_values_persisted_private": True,
        "same_template_for_p0_p1": True,
    }
    for field, expected in required_metadata.items():
        if metadata.get(field) != expected:
            raise RecordedObservationError(f"private metadata mismatch: {field}")
    caseid = str(metadata.get("caseid", ""))
    subjectid = str(metadata.get("subjectid", ""))
    try:
        split_guard.assert_subject_case_request([subjectid], [caseid], expected_split="train")
    except SplitGuardError as error:
        raise RecordedObservationError(str(error)) from error
    template_id = str(metadata.get("template_id", ""))
    if template_id != directory.name or template_id != template_id_for_case(caseid):
        raise RecordedObservationError("pseudonymous template ID mismatch")
    if expected_index_row is not None:
        checks = {
            "caseid": caseid,
            "subjectid": subjectid,
            "template_id": template_id,
            "template_payload_tree_sha256": fingerprint,
        }
        for field, expected in checks.items():
            if expected_index_row.get(field) != expected:
                raise RecordedObservationError(f"private index mismatch: {field}")

    bis_timestamp = _load_array(directory / "bis_timestamp_seconds.npy", np.dtype("<f8"))
    bis_available = _load_array(directory / "bis_available.npy", np.dtype(np.bool_))
    sqi_timestamp = _load_array(directory / "sqi_timestamp_seconds.npy", np.dtype("<f8"))
    sqi_value = _load_array(directory / "sqi_value.npy", np.dtype("<f8"))
    if bis_timestamp.size != bis_available.size or sqi_timestamp.size != sqi_value.size:
        raise RecordedObservationError("private timestamp/value length mismatch")
    if not np.isfinite(bis_timestamp).all() or not np.isfinite(sqi_timestamp).all() or not np.isfinite(sqi_value).all():
        raise RecordedObservationError("private arrays contain non-finite values")
    if metadata.get("bis_event_count") != int(bis_timestamp.size):
        raise RecordedObservationError("BIS metadata count mismatch")
    if metadata.get("bis_available_count") != int(bis_available.sum()):
        raise RecordedObservationError("BIS availability metadata count mismatch")
    if metadata.get("sqi_exact_match_count") != int(sqi_timestamp.size):
        raise RecordedObservationError("SQI metadata count mismatch")

    template = RecordedObservationTemplate(
        template_id=template_id,
        episode_horizon_seconds=float(metadata["episode_horizon_seconds"]),
        bis_events=tuple(
            BISEvent(float(timestamp), bool(available))
            for timestamp, available in zip(bis_timestamp.tolist(), bis_available.tolist())
        ),
        sqi_events=tuple(
            SQIEvent(float(timestamp), float(value))
            for timestamp, value in zip(sqi_timestamp.tolist(), sqi_value.tolist())
        ),
    )
    return template


class TrainObservationTemplateStore:
    """Sequential verifier/loader for one complete ignored Phase 8B store."""

    def __init__(self, root: Path | str, repository_root: Path | str) -> None:
        self.root = Path(root)
        self.repository_root = Path(repository_root)
        self.split_guard = SplitGuard.from_repository(self.repository_root)
        index_path = self.root / "private_index.csv"
        if not index_path.is_file():
            raise RecordedObservationError("private index is missing")
        with index_path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != EXPECTED_TRAIN_CASES or len({row["caseid"] for row in rows}) != len(rows):
            raise RecordedObservationError("private index train accounting mismatch")
        if len({row["template_id"] for row in rows}) != len(rows):
            raise RecordedObservationError("private index template collision")
        self.rows = sorted(rows, key=lambda row: (int(row["caseid"]), row["caseid"]))
        self._by_case = {row["caseid"]: row for row in self.rows}

    def load_case(self, caseid: object) -> RecordedObservationTemplate:
        key = str(caseid).strip()
        try:
            row = self._by_case[key]
        except KeyError as error:
            raise RecordedObservationError(f"case is absent from the private train store: {key}") from error
        expected_relative = f"templates/{row['template_id']}"
        if row.get("relative_template_directory") != expected_relative:
            raise RecordedObservationError("private index relative directory mismatch")
        return load_recorded_template(
            self.root / expected_relative,
            split_guard=self.split_guard,
            expected_index_row=row,
        )

    def verify_all(self) -> str:
        fingerprints: list[dict[str, object]] = []
        for row in self.rows:
            template = self.load_case(row["caseid"])
            if template.template_id != row["template_id"]:
                raise RecordedObservationError("loaded template ID mismatch")
            fingerprints.append({
                "template_id": row["template_id"],
                "template_payload_tree_sha256": row["template_payload_tree_sha256"],
            })
        return private_store_root_sha256(fingerprints)

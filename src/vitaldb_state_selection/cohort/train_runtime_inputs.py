"""Train-only, checksum-pinned Phase 8C patient and remifentanil runtime inputs."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence

import numpy as np

from vitaldb_state_selection.anesthesia import (
    S0_FIELDS,
    S1_FIELDS,
    PiecewiseConstantRemifentanilSchedule,
)
from vitaldb_state_selection.anesthesia.recorded_observation import (
    RecordedObservationTemplate,
    TrainObservationTemplateStore,
)
from vitaldb_state_selection.pkpd import PatientProfile, Sex

from .causal_grid_feasibility import ObservationIndex, parse_observation_index
from .split_guard import SplitGuard, SplitGuardError
from .train_observation_templates import (
    PHASE8A_SEAL_PAYLOAD_SHA256,
    PRIVATE_ROOT_RELATIVE as PHASE8B_PRIVATE_ROOT_RELATIVE,
    load_train_cases,
    verify_complete_template,
)


EXPECTED_TRAIN_CASES = 1970
EXPECTED_TEST_CASES = 490
REMIFENTANIL_TRACK = "Orchestra/RFTN20_RATE"
REMIFENTANIL_SOURCE_UNIT = "mL/hr"
REMIFENTANIL_CONCENTRATION_MICROGRAM_PER_ML = 20.0
REMIFENTANIL_RUNTIME_UNIT = "microgram/min"
RAW_ROOT_RELATIVE = Path("data/raw/phase6a_primary_signals")
PRIVATE_ROOT_RELATIVE = Path("data/processed/phase8c_train_runtime_inputs_v1")
RUNTIME_FORMAT_VERSION = "phase8c-train-runtime-v1"
PROFILE_SOURCE_RELATIVE = "data/manifests/subject_linkage_case_manifest.csv"
PHASE8B_EXPECTED_ROOT_SHA256 = "96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2"
PROFILE_PLAUSIBLE_RANGES = {
    "age_years": (18.0, 120.0),
    "height_cm": (100.0, 250.0),
    "weight_kg": (20.0, 400.0),
}
BUNDLE_PAYLOAD_FILES = (
    "metadata.json",
    "patient_profile.json",
    "remifentanil_timestamp_seconds.npy",
    "remifentanil_rate_microgram_per_min.npy",
)


class TrainRuntimeInputError(RuntimeError):
    """Raised before test access or when a private runtime input is unverifiable."""


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(path, canonical_json_bytes(value))


def _npy_bytes(path: Path, array: np.ndarray) -> None:
    with path.open("wb") as stream:
        np.save(stream, array, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _identifier(value: object, field: str) -> str:
    text = str(value).strip()
    if not text or not text.isdecimal():
        raise TrainRuntimeInputError(f"{field} must be an exact decimal identifier")
    return text


def _finite(value: object, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise TrainRuntimeInputError(f"{field} must be finite") from error
    if not math.isfinite(result):
        raise TrainRuntimeInputError(f"{field} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class TrainPatientRecord:
    caseid: str
    subjectid: str
    profile: PatientProfile


def load_train_patient_records(root: Path | str) -> list[TrainPatientRecord]:
    """Parse clinical fields only after a line's case ID passes the sealed train gate."""

    root = Path(root)
    guard = SplitGuard.from_repository(root)
    train_ids = {caseid for caseid, split in guard.case_split.items() if split == "train"}
    source = root / PROFILE_SOURCE_RELATIVE
    records: list[TrainPatientRecord] = []
    seen: set[str] = set()
    with source.open(encoding="utf-8-sig", newline="") as stream:
        header_line = stream.readline()
        if not header_line:
            raise TrainRuntimeInputError("patient profile source has no header")
        header = next(csv.reader([header_line]))
        for line in stream:
            # The first field is caseid and contains no quoted delimiter in this versioned source.
            first_delimiter = line.find(",")
            if first_delimiter <= 0:
                raise TrainRuntimeInputError("malformed patient profile source row")
            caseid = line[:first_delimiter].strip()
            if caseid not in train_ids:
                continue
            row = next(csv.DictReader([header_line, line]))
            if caseid in seen:
                raise TrainRuntimeInputError(f"duplicate train patient profile: {caseid}")
            seen.add(caseid)
            subjectid = _identifier(row.get("subjectid"), "subjectid")
            try:
                guard.assert_subject_case_request([subjectid], [caseid], expected_split="train")
            except SplitGuardError as error:
                raise TrainRuntimeInputError(str(error)) from error
            sex_text = str(row.get("sex_group", "")).strip().lower()
            if sex_text not in {"male", "female"}:
                raise TrainRuntimeInputError(f"unsupported or missing sex for train case {caseid}")
            values = {
                "age_years": _finite(row.get("age"), "age"),
                "height_cm": _finite(row.get("height_cm"), "height_cm"),
                "weight_kg": _finite(row.get("weight_kg"), "weight_kg"),
            }
            for field, value in values.items():
                lower, upper = PROFILE_PLAUSIBLE_RANGES[field]
                if not lower <= value <= upper:
                    raise TrainRuntimeInputError(f"implausible {field} for train case {caseid}")
            profile = PatientProfile(
                age_years=values["age_years"],
                sex=Sex.MALE if sex_text == "male" else Sex.FEMALE,
                height_cm=values["height_cm"],
                weight_kg=values["weight_kg"],
            )
            records.append(TrainPatientRecord(caseid, subjectid, profile))
    if seen != train_ids or len(records) != EXPECTED_TRAIN_CASES:
        raise TrainRuntimeInputError("train patient profile accounting mismatch")
    return sorted(records, key=lambda item: (int(item.caseid), item.caseid))


@dataclass(frozen=True, slots=True)
class RemifentanilLogicalAccess:
    sequence_number: int
    caseid: str
    assigned_split: str
    track_name: str
    expected_source_sha256: str
    observed_source_sha256: str
    access_purpose: str
    status: str


class TrainRemifentanilAccessGuard:
    """Authorize, checksum, and parse only exact RFTN20_RATE sealed-train files."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.raw_root = (self.root / RAW_ROOT_RELATIVE).resolve()
        self.split_guard = SplitGuard.from_repository(self.root)
        manifests = self.root / "data/manifests"
        self._download = self._index(_csv_rows(manifests / "primary_signal_download_manifest.csv"), "download")
        self._checksum = self._index(_csv_rows(manifests / "primary_signal_checksum_manifest.csv"), "checksum")
        self.logical_accesses: list[RemifentanilLogicalAccess] = []

    @staticmethod
    def _index(rows: Iterable[Mapping[str, str]], source: str) -> dict[tuple[str, str], Mapping[str, str]]:
        result: dict[tuple[str, str], Mapping[str, str]] = {}
        for row in rows:
            key = (row.get("caseid", ""), row.get("track_name", ""))
            if key in result:
                raise TrainRuntimeInputError(f"duplicate {source} row: {key}")
            result[key] = row
        return result

    def _authorize(self, caseid: object, track_name: str) -> tuple[str, Mapping[str, str], Mapping[str, str]]:
        cid = _identifier(caseid, "caseid")
        try:
            self.split_guard.assert_train_cases([cid])
        except SplitGuardError as error:
            raise TrainRuntimeInputError(str(error)) from error
        if track_name != REMIFENTANIL_TRACK:
            raise TrainRuntimeInputError(f"track is outside the Phase 8C exact allowlist: {track_name}")
        key = (cid, track_name)
        try:
            download, checksum = self._download[key], self._checksum[key]
        except KeyError as error:
            raise TrainRuntimeInputError(f"unlisted remifentanil source: {key}") from error
        if download.get("download_status") != "complete" or checksum.get("checksum_verified") != "true":
            raise TrainRuntimeInputError(f"remifentanil source is not complete and verified: {key}")
        expected_semantics = {
            "official_unit": REMIFENTANIL_SOURCE_UNIT,
            "concentration": "remifentanil 20 mcg/mL",
        }
        if any(download.get(field) != expected for field, expected in expected_semantics.items()):
            raise TrainRuntimeInputError(f"remifentanil source semantics mismatch: {key}")
        for field in ("raw_relative_path", "raw_byte_count", "raw_sha256"):
            if download.get(field) != checksum.get(field):
                raise TrainRuntimeInputError(f"remifentanil manifest disagreement: {key}: {field}")
        return cid, download, checksum

    def resolve(self, caseid: object) -> tuple[Path, Mapping[str, str]]:
        cid, download, checksum = self._authorize(caseid, REMIFENTANIL_TRACK)
        relative_text = str(download.get("raw_relative_path", ""))
        relative = PurePosixPath(relative_text)
        if not relative_text or relative.is_absolute() or ".." in relative.parts or relative.suffix != ".signal":
            raise TrainRuntimeInputError(f"unsafe remifentanil source path: {relative_text!r}")
        resolved = self.raw_root.joinpath(*relative.parts).resolve(strict=True)
        try:
            resolved.relative_to(self.raw_root)
        except ValueError as error:
            raise TrainRuntimeInputError("remifentanil source escapes the approved raw root") from error
        if not resolved.is_file() or resolved.stat().st_size != int(checksum["raw_byte_count"]):
            raise TrainRuntimeInputError(f"remifentanil source file mismatch: {cid}")
        return resolved, checksum

    def parse_schedule_source(
        self,
        caseid: object,
        anesthesia_start: float,
        anesthesia_end: float,
        *,
        access_purpose: str = "phase8c_train_runtime_input",
    ) -> tuple[ObservationIndex, str]:
        cid, _, checksum = self._authorize(caseid, REMIFENTANIL_TRACK)
        start, end = _finite(anesthesia_start, "anesthesia_start"), _finite(anesthesia_end, "anesthesia_end")
        if end <= start:
            raise TrainRuntimeInputError("anesthesia window must be positive")
        path, _ = self.resolve(cid)
        observed = sha256_path(path)
        expected = str(checksum["raw_sha256"])
        if observed != expected:
            raise TrainRuntimeInputError(f"remifentanil source checksum mismatch: {cid}")
        try:
            index = parse_observation_index(
                path,
                expected_track_name=REMIFENTANIL_TRACK,
                anesthesia_start=start,
                anesthesia_end=end,
            )
            if any(not math.isfinite(value) or value < 0 for value in index.values):
                raise TrainRuntimeInputError(f"invalid remifentanil rate for train case {cid}")
        except Exception:
            self._record(cid, expected, observed, access_purpose, "parse_failed")
            raise
        self._record(cid, expected, observed, access_purpose, "complete")
        return index, observed

    def _record(self, caseid: str, expected: str, observed: str, purpose: str, status: str) -> None:
        self.logical_accesses.append(RemifentanilLogicalAccess(
            len(self.logical_accesses) + 1,
            caseid,
            "train",
            REMIFENTANIL_TRACK,
            expected,
            observed,
            purpose,
            status,
        ))

    def ledger_rows(self) -> list[dict[str, object]]:
        return [asdict(row) for row in self.logical_accesses]

    def record_verified_resume(
        self,
        caseid: object,
        observed_source_sha256: object,
        *,
        access_purpose: str = "phase8c_verified_complete_bundle_resume",
    ) -> None:
        """Restore one logical ledger row without reopening an already verified raw source."""

        cid, _, checksum = self._authorize(caseid, REMIFENTANIL_TRACK)
        expected = str(checksum["raw_sha256"])
        observed = str(observed_source_sha256)
        if observed != expected:
            raise TrainRuntimeInputError(f"resumed bundle source checksum mismatch: {cid}")
        self._record(cid, expected, observed, access_purpose, "complete")


def convert_rftn20_ml_per_hr_to_microgram_per_min(value: float) -> float:
    value = _finite(value, "RFTN20 rate")
    if value < 0:
        raise TrainRuntimeInputError("RFTN20 rate must be nonnegative")
    return value * REMIFENTANIL_CONCENTRATION_MICROGRAM_PER_ML / 60.0


def causal_schedule_arrays(
    source: ObservationIndex,
    *,
    anesthesia_start: float,
    anesthesia_end: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a right-continuous ZOH schedule; consecutive equal rates are compressed."""

    horizon = float(anesthesia_end) - float(anesthesia_start)
    knots: list[tuple[float, float]] = []
    for timestamp, source_rate in zip(source.timestamps, source.values):
        relative = float(timestamp) - float(anesthesia_start)
        if relative < 0 or relative > horizon:
            raise TrainRuntimeInputError("remifentanil timestamp outside anesthesia window")
        rate = convert_rftn20_ml_per_hr_to_microgram_per_min(source_rate)
        relative = 0.0 if relative == 0.0 else relative
        if knots and rate == knots[-1][1]:
            continue
        knots.append((relative, rate))
    if not knots or knots[0][0] > 0.0:
        knots.insert(0, (0.0, 0.0))
    elif knots[0][0] != 0.0:
        raise TrainRuntimeInputError("invalid first remifentanil timestamp")
    compressed = [knots[0]]
    for knot in knots[1:]:
        if knot[1] != compressed[-1][1]:
            compressed.append(knot)
    knots = compressed
    times = np.asarray([item[0] for item in knots], dtype="<f8")
    rates = np.asarray([item[1] for item in knots], dtype="<f8")
    if (
        times.ndim != 1
        or rates.shape != times.shape
        or not np.isfinite(times).all()
        or not np.isfinite(rates).all()
        or np.any(rates < 0)
        or np.any(np.diff(times) <= 0)
    ):
        raise TrainRuntimeInputError("derived remifentanil schedule invariant failed")
    return times, rates


def bundle_id_for_case(caseid: str) -> str:
    payload = f"{RUNTIME_FORMAT_VERSION}\0{PHASE8A_SEAL_PAYLOAD_SHA256}\0{caseid}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def payload_tree(directory: Path) -> tuple[str, list[dict[str, object]]]:
    entries = [
        {"relative_filename": name, "bytes": (directory / name).stat().st_size, "sha256": sha256_path(directory / name)}
        for name in sorted(BUNDLE_PAYLOAD_FILES)
    ]
    lines = "".join(f"{row['relative_filename']}\t{row['bytes']}\t{row['sha256']}\n" for row in entries)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest(), entries


def verify_complete_bundle(directory: Path) -> tuple[str, dict[str, object]]:
    complete_path = directory / "COMPLETE.json"
    if not complete_path.is_file():
        raise TrainRuntimeInputError(f"missing runtime COMPLETE marker: {directory.name}")
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    fingerprint, entries = payload_tree(directory)
    if complete.get("complete") is not True or complete.get("bundle_payload_tree_sha256") != fingerprint:
        raise TrainRuntimeInputError(f"runtime bundle checksum mismatch: {directory.name}")
    if complete.get("payload_files") != entries:
        raise TrainRuntimeInputError(f"runtime bundle inventory mismatch: {directory.name}")
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("bundle_id") != directory.name:
        raise TrainRuntimeInputError("runtime bundle identity mismatch")
    return fingerprint, metadata


def _profile_payload(record: TrainPatientRecord) -> dict[str, object]:
    return {
        "age_years": record.profile.age_years,
        "caseid": record.caseid,
        "height_cm": record.profile.height_cm,
        "sex": record.profile.sex.value,
        "sex_binary_encoding": {"female": 0, "male": 1},
        "subjectid": record.subjectid,
        "weight_kg": record.profile.weight_kg,
    }


@dataclass(frozen=True, slots=True)
class ExtractedRuntimeBundle:
    bundle_id: str
    directory: Path
    fingerprint: str
    metadata: dict[str, object]


def extract_runtime_bundle(
    record: TrainPatientRecord,
    *,
    anesthesia_start: float,
    anesthesia_end: float,
    phase8b_template_root: Path,
    phase8b_index_row: Mapping[str, str],
    access: TrainRemifentanilAccessGuard,
    bundle_root: Path,
) -> ExtractedRuntimeBundle:
    bundle_id = bundle_id_for_case(record.caseid)
    final = bundle_root / bundle_id
    if final.exists():
        fingerprint, metadata = verify_complete_bundle(final)
        if metadata.get("caseid") != record.caseid:
            raise TrainRuntimeInputError("complete runtime bundle belongs to another case")
        access.record_verified_resume(record.caseid, metadata.get("remifentanil_source_file_sha256"))
        return ExtractedRuntimeBundle(bundle_id, final, fingerprint, metadata)
    relative_template = str(phase8b_index_row.get("relative_template_directory", ""))
    template_directory = phase8b_template_root / relative_template
    template_fingerprint, template_metadata = verify_complete_template(template_directory)
    if str(template_metadata.get("caseid")) != record.caseid:
        raise TrainRuntimeInputError("Phase 8B template/case mismatch")
    if template_fingerprint != phase8b_index_row.get("template_payload_tree_sha256"):
        raise TrainRuntimeInputError("Phase 8B template/index mismatch")
    source, source_sha = access.parse_schedule_source(record.caseid, anesthesia_start, anesthesia_end)
    times, rates = causal_schedule_arrays(
        source,
        anesthesia_start=anesthesia_start,
        anesthesia_end=anesthesia_end,
    )
    metadata: dict[str, object] = {
        "assigned_split": "train",
        "bundle_format_version": RUNTIME_FORMAT_VERSION,
        "bundle_id": bundle_id,
        "caseid": record.caseid,
        "subjectid": record.subjectid,
        "episode_horizon_seconds": float(anesthesia_end - anesthesia_start),
        "phase8a_seal_payload_sha256": PHASE8A_SEAL_PAYLOAD_SHA256,
        "phase8b_template_id": phase8b_index_row["template_id"],
        "phase8b_template_payload_tree_sha256": template_fingerprint,
        "raw_source_copied": False,
        "remifentanil_source_file_sha256": source_sha,
        "remifentanil_source_track": REMIFENTANIL_TRACK,
        "remifentanil_source_unit": REMIFENTANIL_SOURCE_UNIT,
        "remifentanil_concentration_microgram_per_ml": REMIFENTANIL_CONCENTRATION_MICROGRAM_PER_ML,
        "remifentanil_runtime_unit": REMIFENTANIL_RUNTIME_UNIT,
        "remifentanil_original_row_count": source.original_row_count,
        "remifentanil_finite_window_row_count": source.finite_row_count,
        "remifentanil_duplicate_timestamp_count": source.duplicate_timestamp_count,
        "remifentanil_zero_interval_count": source.zero_interval_count,
        "remifentanil_negative_interval_count": source.negative_interval_count,
        "remifentanil_schedule_knot_count": int(times.size),
        "duplicate_rule": "last_finite_source_row_at_timestamp_then_exact_equal-rate_compression",
        "initialization_rule": "zero_from_anesthesia_start_until_first_observed_knot",
        "continuity": "right_continuous_zero_order_hold",
        "future_value_exposed": False,
        "post_anesthesia_value_used": False,
    }
    bundle_root.mkdir(parents=True, exist_ok=True)
    temporary = bundle_root / f".{bundle_id}.partial"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    try:
        atomic_json(temporary / "metadata.json", metadata)
        atomic_json(temporary / "patient_profile.json", _profile_payload(record))
        _npy_bytes(temporary / "remifentanil_timestamp_seconds.npy", times)
        _npy_bytes(temporary / "remifentanil_rate_microgram_per_min.npy", rates)
        fingerprint, entries = payload_tree(temporary)
        atomic_json(temporary / "COMPLETE.json", {
            "bundle_payload_tree_sha256": fingerprint,
            "complete": True,
            "payload_files": entries,
        })
        # Windows scanners can briefly hold a just-fsynced file. Retry only the
        # same atomic directory rename; never rewrite a completed destination.
        for attempt in range(12):
            try:
                os.rename(temporary, final)
                break
            except PermissionError:
                if final.exists() or attempt == 11:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return ExtractedRuntimeBundle(bundle_id, final, fingerprint, metadata)


@dataclass(frozen=True, slots=True)
class TrainRuntimeBundle:
    caseid: str
    subjectid: str
    profile: PatientProfile
    observation_template: RecordedObservationTemplate
    remifentanil_schedule: PiecewiseConstantRemifentanilSchedule
    episode_horizon_seconds: float
    bundle_id: str


class TrainRuntimeInputStore:
    """Verified loader that rejects test and unknown case IDs before private path access."""

    def __init__(self, root: Path | str, repository_root: Path | str) -> None:
        self.root = Path(root)
        self.repository_root = Path(repository_root)
        self.split_guard = SplitGuard.from_repository(self.repository_root)
        self.template_store = TrainObservationTemplateStore(
            self.repository_root / PHASE8B_PRIVATE_ROOT_RELATIVE,
            self.repository_root,
        )
        index_path = self.root / "private_index.csv"
        if not index_path.is_file():
            raise TrainRuntimeInputError("Phase 8C private index is missing")
        rows = _csv_rows(index_path)
        if len(rows) != EXPECTED_TRAIN_CASES or len({row.get("caseid") for row in rows}) != len(rows):
            raise TrainRuntimeInputError("Phase 8C private index accounting mismatch")
        self.rows = sorted(rows, key=lambda row: (int(row["caseid"]), row["caseid"]))
        self._by_case = {row["caseid"]: row for row in self.rows}

    def load_case(self, caseid: object) -> TrainRuntimeBundle:
        cid = _identifier(caseid, "caseid")
        try:
            self.split_guard.assert_train_cases([cid])
        except SplitGuardError as error:
            raise TrainRuntimeInputError(str(error)) from error
        try:
            row = self._by_case[cid]
        except KeyError as error:
            raise TrainRuntimeInputError(f"case is absent from the Phase 8C private train store: {cid}") from error
        relative = PurePosixPath(str(row.get("relative_bundle_directory", "")))
        if relative.is_absolute() or ".." in relative.parts or tuple(relative.parts[:1]) != ("bundles",):
            raise TrainRuntimeInputError("unsafe private runtime bundle path")
        directory = self.root.joinpath(*relative.parts)
        fingerprint, metadata = verify_complete_bundle(directory)
        if fingerprint != row.get("bundle_payload_tree_sha256") or metadata.get("caseid") != cid:
            raise TrainRuntimeInputError("private runtime index/bundle mismatch")
        profile_payload = json.loads((directory / "patient_profile.json").read_text(encoding="utf-8"))
        if profile_payload.get("caseid") != cid or profile_payload.get("subjectid") != row.get("subjectid"):
            raise TrainRuntimeInputError("private patient profile identity mismatch")
        profile = PatientProfile(
            age_years=profile_payload["age_years"],
            sex=Sex(str(profile_payload["sex"])),
            height_cm=profile_payload["height_cm"],
            weight_kg=profile_payload["weight_kg"],
        )
        times = np.load(directory / "remifentanil_timestamp_seconds.npy", allow_pickle=False)
        rates = np.load(directory / "remifentanil_rate_microgram_per_min.npy", allow_pickle=False)
        if times.dtype != np.dtype("<f8") or rates.dtype != np.dtype("<f8") or times.shape != rates.shape:
            raise TrainRuntimeInputError("private remifentanil schedule array mismatch")
        schedule = PiecewiseConstantRemifentanilSchedule(tuple(zip(times.tolist(), rates.tolist())))
        template = self.template_store.load_case(cid)
        if template.template_id != metadata.get("phase8b_template_id"):
            raise TrainRuntimeInputError("runtime bundle references a different Phase 8B template")
        horizon = float(metadata["episode_horizon_seconds"])
        return TrainRuntimeBundle(cid, str(row["subjectid"]), profile, template, schedule, horizon, directory.name)

    def verify_all(self) -> str:
        fingerprints = []
        for row in self.rows:
            bundle = self.load_case(row["caseid"])
            if bundle.bundle_id != row["bundle_id"]:
                raise TrainRuntimeInputError("loaded runtime bundle ID mismatch")
            fingerprints.append((row["bundle_id"], row["bundle_payload_tree_sha256"]))
        lines = "".join(f"{bundle_id}\t{fingerprint}\n" for bundle_id, fingerprint in sorted(fingerprints))
        return hashlib.sha256(lines.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ScalerField:
    field_name: str
    state_profile: str
    normalization_method: str
    fitted_or_fixed: str
    center: float
    scale: float
    zero_variance_handling: str
    binary_unchanged: bool


class StateScaler:
    def __init__(self, state_id: str, fields: Sequence[ScalerField], schema_sha256: str) -> None:
        expected = S0_FIELDS if state_id == "S0" else S1_FIELDS if state_id == "S1" else ()
        if tuple(field.field_name for field in fields) != tuple(expected):
            raise TrainRuntimeInputError("scaler field order differs from frozen state schema")
        self.state_id = state_id
        self.fields = tuple(fields)
        self.schema_sha256 = schema_sha256

    def transform(self, values: np.ndarray) -> np.ndarray:
        array = np.asarray(values, dtype=np.float64)
        if array.shape != (len(self.fields),) or not np.isfinite(array).all():
            raise TrainRuntimeInputError("state scaler received an invalid observation")
        output = array.copy()
        for index, field in enumerate(self.fields):
            if not field.binary_unchanged:
                output[index] = (output[index] - field.center) / field.scale
        if not np.isfinite(output).all():
            raise TrainRuntimeInputError("state scaler produced a non-finite observation")
        return output

    def as_manifest(self) -> dict[str, object]:
        return {
            "state_id": self.state_id,
            "dimension": len(self.fields),
            "schema_sha256": self.schema_sha256,
            "fields": [asdict(field) for field in self.fields],
        }


def load_scaler_registry(path: Path | str) -> dict[str, StateScaler]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    result: dict[str, StateScaler] = {}
    for state_id in ("S0", "S1"):
        item = payload["scalers"][state_id]
        fields = [ScalerField(**row) for row in item["fields"]]
        result[state_id] = StateScaler(state_id, fields, item["schema_sha256"])
    return result


def state_schema_sha256(fields: Sequence[str]) -> str:
    return hashlib.sha256(("\n".join(fields) + "\n").encode("utf-8")).hexdigest()


def make_scaler_fields(
    state_id: str,
    statistics: Mapping[str, tuple[int, float, float]],
) -> list[ScalerField]:
    names = S0_FIELDS if state_id == "S0" else S1_FIELDS
    binary_names = {"sex_binary", *(name for name in names if name.startswith("bis_mask_"))}
    result: list[ScalerField] = []
    for name in names:
        if name in binary_names:
            result.append(ScalerField(name, state_id, "identity_binary", "fixed", 0.0, 1.0, "not_applicable", True))
            continue
        count, mean, sample_sd = statistics[name]
        if count <= 0 or not math.isfinite(mean) or not math.isfinite(sample_sd):
            raise TrainRuntimeInputError(f"invalid scaler statistic: {state_id}: {name}")
        zero = sample_sd <= 1e-12
        result.append(ScalerField(
            name,
            state_id,
            "train_standard_score",
            "fitted_train_only",
            mean,
            1.0 if zero else sample_sd,
            "scale_set_to_1_when_sample_sd_le_1e-12",
            False,
        ))
    return result

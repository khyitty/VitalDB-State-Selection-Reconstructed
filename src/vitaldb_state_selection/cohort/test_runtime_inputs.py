"""Sealed-test patient and remifentanil runtime bundles for Phase 8E."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

import numpy as np

from vitaldb_state_selection.anesthesia import PiecewiseConstantRemifentanilSchedule
from vitaldb_state_selection.pkpd import PatientProfile, Sex

from .causal_grid_feasibility import parse_observation_index
from .split_guard import SplitGuard, SplitGuardError
from .test_observation_templates import (
    EXPECTED_TEST_CASES,
    PHASE8A_SEAL_PAYLOAD_SHA256,
    TestObservationTemplateStore,
    atomic_bytes,
    atomic_csv,
    atomic_json,
    sha256_path,
    verify_complete_template,
)
from .train_runtime_inputs import (
    BUNDLE_PAYLOAD_FILES,
    PHASE8B_EXPECTED_ROOT_SHA256,
    PROFILE_PLAUSIBLE_RANGES,
    PROFILE_SOURCE_RELATIVE,
    RAW_ROOT_RELATIVE,
    REMIFENTANIL_CONCENTRATION_MICROGRAM_PER_ML,
    REMIFENTANIL_RUNTIME_UNIT,
    REMIFENTANIL_SOURCE_UNIT,
    REMIFENTANIL_TRACK,
    StateScaler,
    causal_schedule_arrays,
    load_scaler_registry,
)


PRIVATE_ROOT_RELATIVE = Path("data/processed/phase8e_test_runtime_inputs_v1")
TEST_TEMPLATE_ROOT_RELATIVE = Path("data/processed/phase8e_test_observation_templates_v1")
RUNTIME_FORMAT_VERSION = "phase8e-test-runtime-v1"
PHASE8C_EXPECTED_ROOT_SHA256 = "25ad8a860f6c9b0b45febec7ff7d0d0edf88c0f1953229c8d95e207508d3a606"
SCALER_REGISTRY_RELATIVE = Path("data/manifests/phase8c_scaler_registry.json")


class TestRuntimeInputError(RuntimeError):
    """Raised before train access or for unverifiable test runtime data."""


@dataclass(frozen=True, slots=True)
class TestPatientRecord:
    caseid: str
    subjectid: str
    profile: PatientProfile


@dataclass(frozen=True, slots=True)
class RemifentanilAccess:
    sequence_number: int
    caseid: str
    assigned_split: str
    track_name: str
    expected_source_sha256: str
    observed_source_sha256: str
    access_purpose: str
    status: str


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _finite(value: object, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise TestRuntimeInputError(f"{field} must be finite") from error
    if not math.isfinite(result):
        raise TestRuntimeInputError(f"{field} must be finite")
    return result


def load_test_patient_records(root: Path | str) -> list[TestPatientRecord]:
    """Parse a source row only after its case ID is confirmed sealed-test."""

    root = Path(root)
    guard = SplitGuard.from_repository(root)
    test_ids = {caseid for caseid, split in guard.case_split.items() if split == "test"}
    if len(test_ids) != EXPECTED_TEST_CASES:
        raise TestRuntimeInputError("sealed-test membership accounting mismatch")
    records: list[TestPatientRecord] = []
    seen: set[str] = set()
    source = root / PROFILE_SOURCE_RELATIVE
    with source.open(encoding="utf-8-sig", newline="") as stream:
        header_line = stream.readline()
        if not header_line:
            raise TestRuntimeInputError("patient source lacks a header")
        for line in stream:
            delimiter = line.find(",")
            if delimiter <= 0:
                raise TestRuntimeInputError("malformed patient source row")
            caseid = line[:delimiter].strip()
            if caseid not in test_ids:
                continue
            row = next(csv.DictReader([header_line, line]))
            if caseid in seen:
                raise TestRuntimeInputError(f"duplicate test patient profile: {caseid}")
            seen.add(caseid)
            subjectid = str(row.get("subjectid", "")).strip()
            if not subjectid.isdecimal():
                raise TestRuntimeInputError(f"invalid test subject ID: {caseid}")
            try:
                guard.assert_subject_case_request([subjectid], [caseid], expected_split="test")
            except SplitGuardError as error:
                raise TestRuntimeInputError(str(error)) from error
            sex_text = str(row.get("sex_group", "")).strip().lower()
            if sex_text not in {"male", "female"}:
                raise TestRuntimeInputError(f"missing or unsupported sex: {caseid}")
            values = {
                "age_years": _finite(row.get("age"), "age"),
                "height_cm": _finite(row.get("height_cm"), "height_cm"),
                "weight_kg": _finite(row.get("weight_kg"), "weight_kg"),
            }
            for field, value in values.items():
                lower, upper = PROFILE_PLAUSIBLE_RANGES[field]
                if not lower <= value <= upper:
                    raise TestRuntimeInputError(f"implausible {field}: {caseid}")
            records.append(TestPatientRecord(
                caseid,
                subjectid,
                PatientProfile(
                    age_years=values["age_years"],
                    sex=Sex.MALE if sex_text == "male" else Sex.FEMALE,
                    height_cm=values["height_cm"],
                    weight_kg=values["weight_kg"],
                ),
            ))
    if seen != test_ids or len(records) != EXPECTED_TEST_CASES:
        raise TestRuntimeInputError("test patient profile accounting mismatch")
    return sorted(records, key=lambda row: (int(row.caseid), row.caseid))


class TestRemifentanilAccessGuard:
    """Authorize exact RFTN20_RATE for sealed-test cases only."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.raw_root = (self.root / RAW_ROOT_RELATIVE).resolve()
        self.guard = SplitGuard.from_repository(self.root)
        manifests = self.root / "data/manifests"
        self._download = self._index(_csv_rows(manifests / "primary_signal_download_manifest.csv"))
        self._checksum = self._index(_csv_rows(manifests / "primary_signal_checksum_manifest.csv"))
        self.logical_accesses: list[RemifentanilAccess] = []

    @staticmethod
    def _index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
        result: dict[tuple[str, str], dict[str, str]] = {}
        for row in rows:
            key = (row.get("caseid", ""), row.get("track_name", ""))
            if key in result:
                raise TestRuntimeInputError(f"duplicate signal manifest row: {key}")
            result[key] = row
        return result

    def _authorize(self, caseid: object, track: str) -> tuple[str, dict[str, str], dict[str, str]]:
        cid = str(caseid).strip()
        if not cid.isdecimal():
            raise TestRuntimeInputError("caseid must be an exact decimal identifier")
        try:
            self.guard.assert_test_cases([cid])
        except SplitGuardError as error:
            raise TestRuntimeInputError(str(error)) from error
        if track != REMIFENTANIL_TRACK:
            raise TestRuntimeInputError(f"track outside exact remifentanil allowlist: {track}")
        key = (cid, track)
        try:
            download, checksum = self._download[key], self._checksum[key]
        except KeyError as error:
            raise TestRuntimeInputError(f"unlisted remifentanil source: {key}") from error
        if download.get("download_status") != "complete" or checksum.get("checksum_verified") != "true":
            raise TestRuntimeInputError(f"unverified remifentanil source: {key}")
        if download.get("official_unit") != REMIFENTANIL_SOURCE_UNIT or download.get("concentration") != "remifentanil 20 mcg/mL":
            raise TestRuntimeInputError(f"remifentanil semantics mismatch: {key}")
        for field in ("raw_relative_path", "raw_byte_count", "raw_sha256"):
            if download.get(field) != checksum.get(field):
                raise TestRuntimeInputError(f"remifentanil manifest disagreement: {key}: {field}")
        return cid, download, checksum

    def parse(self, caseid: object, start: float, end: float) -> tuple[object, str]:
        cid, download, checksum = self._authorize(caseid, REMIFENTANIL_TRACK)
        relative = PurePosixPath(download["raw_relative_path"])
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".signal":
            raise TestRuntimeInputError("unsafe remifentanil source path")
        path = self.raw_root.joinpath(*relative.parts).resolve(strict=True)
        try:
            path.relative_to(self.raw_root)
        except ValueError as error:
            raise TestRuntimeInputError("remifentanil path escapes approved root") from error
        if path.stat().st_size != int(checksum["raw_byte_count"]):
            raise TestRuntimeInputError(f"remifentanil byte-count mismatch: {cid}")
        observed = sha256_path(path)
        expected = checksum["raw_sha256"]
        if observed != expected:
            raise TestRuntimeInputError(f"remifentanil checksum mismatch: {cid}")
        try:
            source = parse_observation_index(
                path,
                expected_track_name=REMIFENTANIL_TRACK,
                anesthesia_start=float(start),
                anesthesia_end=float(end),
            )
            if any(not math.isfinite(value) or value < 0 for value in source.values):
                raise TestRuntimeInputError(f"invalid remifentanil rate: {cid}")
        except Exception:
            self._record(cid, expected, observed, "parse_failed")
            raise
        self._record(cid, expected, observed, "complete")
        return source, observed

    def _record(self, caseid: str, expected: str, observed: str, status: str) -> None:
        self.logical_accesses.append(RemifentanilAccess(
            len(self.logical_accesses) + 1,
            caseid,
            "test",
            REMIFENTANIL_TRACK,
            expected,
            observed,
            "phase8e_test_runtime_input",
            status,
        ))

    def ledger_rows(self) -> list[dict[str, object]]:
        return [asdict(row) for row in self.logical_accesses]

    def record_verified_resume(self, caseid: object, observed: object) -> None:
        cid, _, checksum = self._authorize(caseid, REMIFENTANIL_TRACK)
        expected = checksum["raw_sha256"]
        if str(observed) != expected:
            raise TestRuntimeInputError(f"resumed test runtime source checksum mismatch: {cid}")
        self._record(cid, expected, str(observed), "complete")


def bundle_id_for_case(caseid: str) -> str:
    payload = f"{RUNTIME_FORMAT_VERSION}\0{PHASE8A_SEAL_PAYLOAD_SHA256}\0{caseid}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _payload_tree(directory: Path) -> tuple[str, list[dict[str, object]]]:
    entries = [
        {"relative_filename": name, "bytes": (directory / name).stat().st_size, "sha256": sha256_path(directory / name)}
        for name in sorted(BUNDLE_PAYLOAD_FILES)
    ]
    lines = "".join(f"{row['relative_filename']}\t{row['bytes']}\t{row['sha256']}\n" for row in entries)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest(), entries


def verify_complete_bundle(directory: Path) -> tuple[str, dict[str, object]]:
    complete_path = directory / "COMPLETE.json"
    if not complete_path.is_file():
        raise TestRuntimeInputError("test runtime COMPLETE marker missing")
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    fingerprint, entries = _payload_tree(directory)
    if complete.get("complete") is not True or complete.get("bundle_payload_tree_sha256") != fingerprint:
        raise TestRuntimeInputError("test runtime checksum mismatch")
    if complete.get("payload_files") != entries:
        raise TestRuntimeInputError("test runtime inventory mismatch")
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("bundle_id") != directory.name:
        raise TestRuntimeInputError("test runtime identity mismatch")
    return fingerprint, metadata


def _profile_payload(record: TestPatientRecord) -> dict[str, object]:
    return {
        "age_years": record.profile.age_years,
        "caseid": record.caseid,
        "height_cm": record.profile.height_cm,
        "sex": record.profile.sex.value,
        "sex_binary_encoding": {"female": 0, "male": 1},
        "subjectid": record.subjectid,
        "weight_kg": record.profile.weight_kg,
    }


def extract_bundle(
    record: TestPatientRecord,
    *,
    anesthesia_start: float,
    anesthesia_end: float,
    template_root: Path,
    template_index_row: Mapping[str, str],
    access: TestRemifentanilAccessGuard,
    bundle_root: Path,
    scaler_sha256: str,
) -> dict[str, object]:
    bundle_id = bundle_id_for_case(record.caseid)
    final = bundle_root / bundle_id
    if final.exists():
        fingerprint, metadata = verify_complete_bundle(final)
        if metadata.get("caseid") != record.caseid:
            raise TestRuntimeInputError("complete test runtime bundle belongs to another case")
        access.record_verified_resume(record.caseid, metadata.get("remifentanil_source_file_sha256"))
        return {"bundle_id": bundle_id, "fingerprint": fingerprint, "metadata": metadata}
    template_directory = template_root / template_index_row["relative_template_directory"]
    template_fingerprint, template_metadata = verify_complete_template(template_directory)
    if template_metadata.get("caseid") != record.caseid or template_fingerprint != template_index_row["template_payload_tree_sha256"]:
        raise TestRuntimeInputError("test template/runtime join mismatch")
    source, source_sha = access.parse(record.caseid, anesthesia_start, anesthesia_end)
    try:
        times, rates = causal_schedule_arrays(source, anesthesia_start=anesthesia_start, anesthesia_end=anesthesia_end)
    except Exception as error:
        raise TestRuntimeInputError(str(error)) from error
    metadata: dict[str, object] = {
        "assigned_split": "test",
        "bundle_format_version": RUNTIME_FORMAT_VERSION,
        "bundle_id": bundle_id,
        "caseid": record.caseid,
        "episode_horizon_seconds": float(anesthesia_end - anesthesia_start),
        "future_value_exposed": False,
        "phase8a_seal_payload_sha256": PHASE8A_SEAL_PAYLOAD_SHA256,
        "raw_source_copied": False,
        "remifentanil_runtime_unit": REMIFENTANIL_RUNTIME_UNIT,
        "remifentanil_source_file_sha256": source_sha,
        "remifentanil_source_track": REMIFENTANIL_TRACK,
        "remifentanil_source_unit": REMIFENTANIL_SOURCE_UNIT,
        "remifentanil_concentration_microgram_per_ml": REMIFENTANIL_CONCENTRATION_MICROGRAM_PER_ML,
        "remifentanil_schedule_knot_count": int(times.size),
        "subjectid": record.subjectid,
        "test_derived_scaler_fit_count": 0,
        "test_template_id": template_index_row["template_id"],
        "test_template_payload_tree_sha256": template_fingerprint,
        "train_scaler_registry_sha256": scaler_sha256,
    }
    bundle_root.mkdir(parents=True, exist_ok=True)
    temporary = bundle_root / f".{bundle_id}.partial"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    try:
        atomic_json(temporary / "metadata.json", metadata)
        atomic_json(temporary / "patient_profile.json", _profile_payload(record))
        for path, value in (
            (temporary / "remifentanil_timestamp_seconds.npy", times),
            (temporary / "remifentanil_rate_microgram_per_min.npy", rates),
        ):
            with path.open("wb") as stream:
                np.save(stream, value, allow_pickle=False)
                stream.flush()
                os.fsync(stream.fileno())
        fingerprint, entries = _payload_tree(temporary)
        atomic_json(temporary / "COMPLETE.json", {
            "bundle_payload_tree_sha256": fingerprint,
            "complete": True,
            "payload_files": entries,
        })
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
    return {"bundle_id": bundle_id, "fingerprint": fingerprint, "metadata": metadata}


@dataclass(frozen=True, slots=True)
class TestRuntimeBundle:
    caseid: str
    subjectid: str
    profile: PatientProfile
    observation_template: object
    remifentanil_schedule: PiecewiseConstantRemifentanilSchedule
    episode_horizon_seconds: float
    bundle_id: str


class TestRuntimeInputStore:
    def __init__(self, root: Path | str, repository_root: Path | str) -> None:
        self.root = Path(root)
        self.repository_root = Path(repository_root)
        self.guard = SplitGuard.from_repository(repository_root)
        self.template_store = TestObservationTemplateStore(
            self.repository_root / TEST_TEMPLATE_ROOT_RELATIVE,
            self.repository_root,
        )
        rows = _csv_rows(self.root / "private_index.csv")
        if len(rows) != EXPECTED_TEST_CASES or len({row.get("caseid") for row in rows}) != EXPECTED_TEST_CASES:
            raise TestRuntimeInputError("test runtime private index accounting mismatch")
        self.rows = sorted(rows, key=lambda row: (int(row["caseid"]), row["caseid"]))
        self._by_case = {row["caseid"]: row for row in self.rows}

    def load_case(self, caseid: object) -> TestRuntimeBundle:
        cid = str(caseid).strip()
        try:
            self.guard.assert_test_cases([cid])
            row = self._by_case[cid]
        except (SplitGuardError, KeyError) as error:
            raise TestRuntimeInputError(f"case absent from test runtime store: {cid}") from error
        relative = PurePosixPath(row["relative_bundle_directory"])
        if relative.is_absolute() or ".." in relative.parts or tuple(relative.parts[:1]) != ("bundles",):
            raise TestRuntimeInputError("unsafe test runtime path")
        directory = self.root.joinpath(*relative.parts)
        fingerprint, metadata = verify_complete_bundle(directory)
        if fingerprint != row["bundle_payload_tree_sha256"] or metadata.get("caseid") != cid:
            raise TestRuntimeInputError("test runtime index/bundle mismatch")
        profile_payload = json.loads((directory / "patient_profile.json").read_text(encoding="utf-8"))
        profile = PatientProfile(
            age_years=profile_payload["age_years"],
            sex=Sex(profile_payload["sex"]),
            height_cm=profile_payload["height_cm"],
            weight_kg=profile_payload["weight_kg"],
        )
        times = np.load(directory / "remifentanil_timestamp_seconds.npy", allow_pickle=False)
        rates = np.load(directory / "remifentanil_rate_microgram_per_min.npy", allow_pickle=False)
        if times.dtype != np.dtype("<f8") or rates.dtype != np.dtype("<f8") or times.shape != rates.shape:
            raise TestRuntimeInputError("test remifentanil schedule array mismatch")
        return TestRuntimeBundle(
            cid,
            row["subjectid"],
            profile,
            self.template_store.load_case(cid),
            PiecewiseConstantRemifentanilSchedule(tuple(zip(times.tolist(), rates.tolist()))),
            float(metadata["episode_horizon_seconds"]),
            directory.name,
        )

    def verify_all(self) -> str:
        fingerprints: list[tuple[str, str]] = []
        for row in self.rows:
            bundle = self.load_case(row["caseid"])
            if bundle.bundle_id != row["bundle_id"]:
                raise TestRuntimeInputError("loaded test runtime identity mismatch")
            fingerprints.append((row["bundle_id"], row["bundle_payload_tree_sha256"]))
        lines = "".join(f"{bundle_id}\t{fingerprint}\n" for bundle_id, fingerprint in sorted(fingerprints))
        return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def verify_train_scalers(root: Path | str) -> tuple[dict[str, StateScaler], str]:
    root = Path(root)
    path = root / SCALER_REGISTRY_RELATIVE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("fit_split") != "train_only" or payload.get("test_case_count_used") != 0:
        raise TestRuntimeInputError("scaler registry is not train-only")
    scalers = load_scaler_registry(path)
    if len(scalers["S0"].fields) != 34 or len(scalers["S1"].fields) != 42:
        raise TestRuntimeInputError("train scaler dimension mismatch")
    return scalers, sha256_path(path)

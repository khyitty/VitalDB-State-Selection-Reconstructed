"""Sealed-test, checksum-pinned Phase 8E observation templates."""

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
from typing import Mapping

import numpy as np

from vitaldb_state_selection.anesthesia.observation import BISEvent, SQIEvent
from vitaldb_state_selection.anesthesia.recorded_observation import RecordedObservationTemplate

from .causal_grid_feasibility import ObservationIndex, parse_observation_index
from .split_guard import SplitGuard, SplitGuardError
from .train_observation_templates import (
    OPERATIONAL_TIMING_RELATIVE,
    OPERATIONAL_TIMING_SHA256,
    PAYLOAD_FILES,
    PHASE8A_SEAL_PAYLOAD_SHA256,
    UPSTREAM_TIMING_RELATIVE,
    UPSTREAM_TIMING_SHA256,
)


EXPECTED_TEST_CASES = 490
ALLOWED_TRACKS = ("BIS/BIS", "BIS/SQI")
RAW_ROOT_RELATIVE = Path("data/raw/phase6a_primary_signals")
PRIVATE_ROOT_RELATIVE = Path("data/processed/phase8e_test_observation_templates_v1")
SCHEMA_VERSION = "phase8e-private-test-template-schema-v1"
TEMPLATE_FORMAT_VERSION = "phase8e-test-template-v1"


class TestTemplateError(RuntimeError):
    """Raised before unsealed access or for unverifiable private test data."""


@dataclass(frozen=True, slots=True)
class TestCase:
    caseid: str
    subjectid: str
    anesthesia_start: float
    anesthesia_end: float
    source_cohort_protocol_version: str
    study_protocol_version: str
    split_manifest_version: str


@dataclass(frozen=True, slots=True)
class LogicalAccess:
    sequence_number: int
    caseid: str
    assigned_split: str
    track_name: str
    expected_source_sha256: str
    observed_source_sha256: str
    access_purpose: str
    status: str


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
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    temporary = Path(name)
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


def atomic_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, stream.getvalue().encode("utf-8"))


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _timing_rows(path: Path, test_ids: set[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in _csv_rows(path):
        caseid = row.get("caseid", "")
        if caseid not in test_ids:
            continue
        if caseid in result:
            raise TestTemplateError(f"duplicate sealed-test timing row: {path.name}: {caseid}")
        result[caseid] = row
    if set(result) != test_ids:
        raise TestTemplateError("timing source misses a sealed-test case")
    return result


def load_test_cases(root: Path | str) -> list[TestCase]:
    root = Path(root)
    operational_path = root / OPERATIONAL_TIMING_RELATIVE
    upstream_path = root / UPSTREAM_TIMING_RELATIVE
    if sha256_path(operational_path) != OPERATIONAL_TIMING_SHA256:
        raise TestTemplateError("operational timing checksum mismatch")
    if sha256_path(upstream_path) != UPSTREAM_TIMING_SHA256:
        raise TestTemplateError("upstream timing checksum mismatch")
    guard = SplitGuard.from_repository(root)
    split_rows = _csv_rows(root / "data/manifests/phase8a_case_split_manifest.csv")
    selected = [row for row in split_rows if row.get("assigned_split") == "test"]
    if len(selected) != EXPECTED_TEST_CASES:
        raise TestTemplateError("sealed-test case accounting mismatch")
    test_ids = {row["caseid"] for row in selected}
    if len(test_ids) != EXPECTED_TEST_CASES:
        raise TestTemplateError("duplicate sealed-test case")
    guard.assert_test_cases(test_ids)
    operational = _timing_rows(operational_path, test_ids)
    upstream = _timing_rows(upstream_path, test_ids)
    result: list[TestCase] = []
    for split_row in selected:
        caseid = split_row["caseid"]
        op, up = operational[caseid], upstream[caseid]
        for field in ("anesthesia_start", "anesthesia_end"):
            if op.get(field) != up.get(field):
                raise TestTemplateError(f"timing lineage string mismatch: {caseid}: {field}")
        try:
            start, end = float(op["anesthesia_start"]), float(op["anesthesia_end"])
            upstream_start, upstream_end = float(up["anesthesia_start"]), float(up["anesthesia_end"])
        except (KeyError, ValueError) as error:
            raise TestTemplateError(f"invalid anesthesia timing: {caseid}") from error
        if not all(math.isfinite(value) for value in (start, end, upstream_start, upstream_end)):
            raise TestTemplateError(f"non-finite anesthesia timing: {caseid}")
        if start != upstream_start or end != upstream_end or end <= start:
            raise TestTemplateError(f"invalid timing lineage: {caseid}")
        result.append(TestCase(
            caseid,
            split_row["subjectid"],
            start,
            end,
            split_row["source_cohort_protocol_version"],
            split_row["study_protocol_version"],
            split_row["split_manifest_version"],
        ))
    return sorted(result, key=lambda row: (int(row.caseid), row.caseid))


class TestRawAccessGuard:
    """Resolve and parse only BIS/BIS and BIS/SQI for sealed-test cases."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.raw_root = (self.root / RAW_ROOT_RELATIVE).resolve()
        self.split_guard = SplitGuard.from_repository(self.root)
        manifests = self.root / "data/manifests"
        eligible = _csv_rows(manifests / "final_eligible_cohort_manifest.csv")
        self.eligible_caseids = {row["caseid"] for row in eligible if row.get("final_eligible") == "true"}
        if len(self.eligible_caseids) != 2460:
            raise TestTemplateError("frozen cohort accounting mismatch")
        self._download = self._index(_csv_rows(manifests / "primary_signal_download_manifest.csv"), "download")
        self._checksum = self._index(_csv_rows(manifests / "primary_signal_checksum_manifest.csv"), "checksum")
        self.logical_accesses: list[LogicalAccess] = []

    @staticmethod
    def _index(rows: list[dict[str, str]], label: str) -> dict[tuple[str, str], dict[str, str]]:
        result: dict[tuple[str, str], dict[str, str]] = {}
        for row in rows:
            key = (row.get("caseid", ""), row.get("track_name", ""))
            if key in result:
                raise TestTemplateError(f"duplicate {label} row: {key}")
            result[key] = row
        return result

    def _authorize(self, caseid: object, track_name: str) -> tuple[str, dict[str, str], dict[str, str]]:
        cid = str(caseid).strip()
        if not cid.isdecimal():
            raise TestTemplateError("caseid must be an exact decimal identifier")
        try:
            self.split_guard.assert_test_cases([cid])
        except SplitGuardError as error:
            raise TestTemplateError(str(error)) from error
        if track_name not in ALLOWED_TRACKS:
            raise TestTemplateError(f"track outside sealed-test template allowlist: {track_name}")
        if cid not in self.eligible_caseids:
            raise TestTemplateError(f"case absent from frozen cohort: {cid}")
        key = (cid, track_name)
        try:
            download, checksum = self._download[key], self._checksum[key]
        except KeyError as error:
            raise TestTemplateError(f"unlisted source: {key}") from error
        if download.get("download_status") != "complete" or checksum.get("checksum_verified") != "true":
            raise TestTemplateError(f"source is not complete and verified: {key}")
        for field in ("raw_relative_path", "raw_byte_count", "raw_sha256"):
            if download.get(field) != checksum.get(field):
                raise TestTemplateError(f"source manifest disagreement: {key}: {field}")
        return cid, download, checksum

    def parse_test_track(
        self,
        caseid: object,
        track_name: str,
        anesthesia_start: float,
        anesthesia_end: float,
        *,
        access_purpose: str = "phase8e_test_template_extraction",
    ) -> ObservationIndex:
        cid, download, checksum = self._authorize(caseid, track_name)
        relative = PurePosixPath(download["raw_relative_path"])
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".signal":
            raise TestTemplateError("unsafe raw relative path")
        path = self.raw_root.joinpath(*relative.parts).resolve(strict=True)
        try:
            path.relative_to(self.raw_root)
        except ValueError as error:
            raise TestTemplateError("raw path escapes approved root") from error
        if path.stat().st_size != int(checksum["raw_byte_count"]):
            raise TestTemplateError(f"source byte-count mismatch: {(cid, track_name)}")
        observed = sha256_path(path)
        expected = checksum["raw_sha256"]
        if observed != expected:
            raise TestTemplateError(f"source checksum mismatch: {(cid, track_name)}")
        try:
            index = parse_observation_index(
                path,
                expected_track_name=track_name,
                anesthesia_start=float(anesthesia_start),
                anesthesia_end=float(anesthesia_end),
            )
        except Exception:
            self._record(cid, track_name, expected, observed, access_purpose, "parse_failed")
            raise
        self._record(cid, track_name, expected, observed, access_purpose, "complete")
        return index

    def _record(self, caseid: str, track: str, expected: str, observed: str, purpose: str, status: str) -> None:
        self.logical_accesses.append(LogicalAccess(
            len(self.logical_accesses) + 1,
            caseid,
            "test",
            track,
            expected,
            observed,
            purpose,
            status,
        ))

    def ledger_rows(self) -> list[dict[str, object]]:
        return [asdict(row) for row in self.logical_accesses]

    def record_verified_resume(self, caseid: object, track_name: str, observed: object) -> None:
        cid, _, checksum = self._authorize(caseid, track_name)
        expected = checksum["raw_sha256"]
        if str(observed) != expected:
            raise TestTemplateError(f"resumed test-template source checksum mismatch: {(cid, track_name)}")
        self._record(cid, track_name, expected, str(observed), "phase8e_verified_complete_template_resume", "complete")


def template_id_for_case(caseid: str) -> str:
    payload = f"{TEMPLATE_FORMAT_VERSION}\0{PHASE8A_SEAL_PAYLOAD_SHA256}\0{caseid}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _npy(path: Path, value: np.ndarray) -> None:
    with path.open("wb") as stream:
        np.save(stream, value, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())


def _payload_tree(directory: Path) -> tuple[str, list[dict[str, object]]]:
    entries = [
        {"relative_filename": name, "bytes": (directory / name).stat().st_size, "sha256": sha256_path(directory / name)}
        for name in sorted(PAYLOAD_FILES)
    ]
    lines = "".join(f"{row['relative_filename']}\t{row['bytes']}\t{row['sha256']}\n" for row in entries)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest(), entries


def verify_complete_template(directory: Path) -> tuple[str, dict[str, object]]:
    complete_path = directory / "COMPLETE.json"
    if not complete_path.is_file():
        raise TestTemplateError("test template COMPLETE marker missing")
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    fingerprint, entries = _payload_tree(directory)
    if complete.get("complete") is not True or complete.get("template_payload_tree_sha256") != fingerprint:
        raise TestTemplateError("test template checksum mismatch")
    if complete.get("payload_files") != entries:
        raise TestTemplateError("test template inventory mismatch")
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("template_id") != directory.name:
        raise TestTemplateError("test template identity mismatch")
    return fingerprint, metadata


def extract_template(case: TestCase, *, access: TestRawAccessGuard, template_root: Path) -> dict[str, object]:
    template_id = template_id_for_case(case.caseid)
    final = template_root / template_id
    if final.exists():
        fingerprint, metadata = verify_complete_template(final)
        if metadata.get("caseid") != case.caseid:
            raise TestTemplateError("complete test template belongs to another case")
        access.record_verified_resume(case.caseid, "BIS/BIS", metadata.get("source_bis_file_sha256"))
        access.record_verified_resume(case.caseid, "BIS/SQI", metadata.get("source_sqi_file_sha256"))
        return {"template_id": template_id, "fingerprint": fingerprint, "metadata": metadata}
    bis = access.parse_test_track(case.caseid, "BIS/BIS", case.anesthesia_start, case.anesthesia_end)
    sqi = access.parse_test_track(case.caseid, "BIS/SQI", case.anesthesia_start, case.anesthesia_end)
    horizon = case.anesthesia_end - case.anesthesia_start
    bis_t = np.asarray([float(value - case.anesthesia_start) for value in bis.timestamps], dtype="<f8")
    bis_available = np.asarray([0.0 <= value <= 100.0 for value in bis.values], dtype=np.bool_)
    by_absolute = {timestamp: relative for timestamp, relative in zip(bis.timestamps, bis_t.tolist())}
    sqi_pairs = [(by_absolute[timestamp], value) for timestamp, value in zip(sqi.timestamps, sqi.values) if timestamp in by_absolute]
    sqi_t = np.asarray([row[0] for row in sqi_pairs], dtype="<f8")
    sqi_v = np.asarray([row[1] for row in sqi_pairs], dtype="<f8")
    if any(value < 0 or value > horizon for value in (*bis_t.tolist(), *sqi_t.tolist())):
        raise TestTemplateError("test event outside episode horizon")
    bis_at = dict(zip(bis_t.tolist(), bis_available.tolist()))
    metadata: dict[str, object] = {
        "assigned_split": "test",
        "bis_available_count": int(bis_available.sum()),
        "bis_event_count": int(bis_t.size),
        "caseid": case.caseid,
        "episode_horizon_seconds": float(horizon),
        "p0_visibility_rule": "no_sqi_gate_bis_stale_30_seconds",
        "p1_event_acceptance_count": sum(bool(bis_at[timestamp]) and value >= 50.0 for timestamp, value in sqi_pairs),
        "p1_visibility_rule": "exact_timestamp_sqi_ge_50_bis_stale_20_seconds",
        "phase8a_seal_payload_sha256": PHASE8A_SEAL_PAYLOAD_SHA256,
        "raw_bis_values_persisted": False,
        "raw_sqi_values_persisted_private": True,
        "same_template_for_p0_p1": True,
        "schema_version": SCHEMA_VERSION,
        "source_bis_file_sha256": access.logical_accesses[-2].observed_source_sha256,
        "source_sqi_file_sha256": access.logical_accesses[-1].observed_source_sha256,
        "source_type": "vitaldb_test",
        "sqi_exact_match_count": int(sqi_t.size),
        "split_manifest_version": case.split_manifest_version,
        "subjectid": case.subjectid,
        "template_format_version": TEMPLATE_FORMAT_VERSION,
        "template_id": template_id,
    }
    template_root.mkdir(parents=True, exist_ok=True)
    temporary = template_root / f".{template_id}.partial"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    try:
        atomic_json(temporary / "metadata.json", metadata)
        _npy(temporary / "bis_timestamp_seconds.npy", bis_t)
        _npy(temporary / "bis_available.npy", bis_available)
        _npy(temporary / "sqi_timestamp_seconds.npy", sqi_t)
        _npy(temporary / "sqi_value.npy", sqi_v)
        fingerprint, entries = _payload_tree(temporary)
        atomic_json(temporary / "COMPLETE.json", {
            "complete": True,
            "payload_files": entries,
            "template_payload_tree_sha256": fingerprint,
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
    return {"template_id": template_id, "fingerprint": fingerprint, "metadata": metadata}


def private_root_sha256(rows: list[Mapping[str, object]]) -> str:
    lines = "".join(
        f"{row['template_id']}\t{row['template_payload_tree_sha256']}\n"
        for row in sorted(rows, key=lambda item: str(item["template_id"]))
    )
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


class TestObservationTemplateStore:
    def __init__(self, root: Path | str, repository_root: Path | str) -> None:
        self.root = Path(root)
        self.guard = SplitGuard.from_repository(repository_root)
        rows = _csv_rows(self.root / "private_index.csv")
        if len(rows) != EXPECTED_TEST_CASES or len({row.get("caseid") for row in rows}) != EXPECTED_TEST_CASES:
            raise TestTemplateError("test private index accounting mismatch")
        self.rows = sorted(rows, key=lambda row: (int(row["caseid"]), row["caseid"]))
        self._by_case = {row["caseid"]: row for row in self.rows}

    def load_case(self, caseid: object) -> RecordedObservationTemplate:
        cid = str(caseid).strip()
        try:
            self.guard.assert_test_cases([cid])
            row = self._by_case[cid]
        except (SplitGuardError, KeyError) as error:
            raise TestTemplateError(f"case absent from sealed-test template store: {cid}") from error
        directory = self.root / row["relative_template_directory"]
        fingerprint, metadata = verify_complete_template(directory)
        if fingerprint != row["template_payload_tree_sha256"] or metadata.get("caseid") != cid:
            raise TestTemplateError("test template/index mismatch")
        required = {
            "assigned_split": "test",
            "source_type": "vitaldb_test",
            "raw_bis_values_persisted": False,
            "same_template_for_p0_p1": True,
        }
        if any(metadata.get(key) != value for key, value in required.items()):
            raise TestTemplateError("test template metadata mismatch")
        bis_t = np.load(directory / "bis_timestamp_seconds.npy", allow_pickle=False)
        bis_a = np.load(directory / "bis_available.npy", allow_pickle=False)
        sqi_t = np.load(directory / "sqi_timestamp_seconds.npy", allow_pickle=False)
        sqi_v = np.load(directory / "sqi_value.npy", allow_pickle=False)
        if bis_t.dtype != np.dtype("<f8") or bis_a.dtype != np.dtype(np.bool_) or sqi_t.dtype != np.dtype("<f8") or sqi_v.dtype != np.dtype("<f8"):
            raise TestTemplateError("test template dtype mismatch")
        template = RecordedObservationTemplate(
            template_id=row["template_id"],
            episode_horizon_seconds=float(metadata["episode_horizon_seconds"]),
            bis_events=tuple(BISEvent(float(timestamp), bool(value)) for timestamp, value in zip(bis_t.tolist(), bis_a.tolist())),
            sqi_events=tuple(SQIEvent(float(timestamp), float(value)) for timestamp, value in zip(sqi_t.tolist(), sqi_v.tolist())),
            source_type="vitaldb_test",
        )
        return template

    def verify_all(self) -> str:
        rows: list[dict[str, object]] = []
        for row in self.rows:
            self.load_case(row["caseid"])
            rows.append({
                "template_id": row["template_id"],
                "template_payload_tree_sha256": row["template_payload_tree_sha256"],
            })
        return private_root_sha256(rows)

"""Deterministic private Phase 8B train observation-template extraction."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .split_guard import SplitGuard
from .train_raw_access import ALLOWED_TRACKS, TrainRawAccessGuard, sha256_path


PHASE = "Phase 8B"
SCHEMA_VERSION = "phase8b-private-template-schema-v1"
TEMPLATE_FORMAT_VERSION = "phase8b-train-template-v1"
EXPECTED_TRAIN_CASES = 1970
OPERATIONAL_TIMING_RELATIVE = "data/manifests/primary_signal_quality_case_manifest.csv"
OPERATIONAL_TIMING_SHA256 = "911e4b44e626cc9f7d4944c825011c8e6b7b5b2be486dd8d7a29af9586913d5d"
UPSTREAM_TIMING_RELATIVE = "data/manifests/volatile_signal_case_manifest.csv"
UPSTREAM_TIMING_SHA256 = "66c65af9fa72467c29544e6d9c84550449370e61781b703461f83508964f30a8"
PHASE8A_SEAL_PAYLOAD_SHA256 = "6083be99567d5d7d4989ef3c9e35fc51255f614098697f289daac756d643f9af"
PRIVATE_ROOT_RELATIVE = Path("data/processed/phase8b_train_observation_templates_v1")
PAYLOAD_FILES = (
    "metadata.json",
    "bis_timestamp_seconds.npy",
    "bis_available.npy",
    "sqi_timestamp_seconds.npy",
    "sqi_value.npy",
)


class TrainTemplateError(RuntimeError):
    """Raised for timing lineage, extraction, or private-store failures."""


@dataclass(frozen=True, slots=True)
class TrainCase:
    caseid: str
    subjectid: str
    anesthesia_start_text: str
    anesthesia_end_text: str
    anesthesia_start: float
    anesthesia_end: float
    source_cohort_protocol_version: str
    study_protocol_version: str
    split_manifest_version: str


@dataclass(frozen=True, slots=True)
class ExtractedTemplate:
    template_id: str
    directory: Path
    payload_tree_sha256: str
    metadata: dict[str, object]
    payload_bytes: int


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_bytes_fsync(path: Path, content: bytes) -> None:
    with path.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def write_json(path: Path, value: object) -> None:
    write_bytes_fsync(path, canonical_json_bytes(value))


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    temporary = path.with_name(path.name + ".partial")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _unique_case_rows(path: Path, train_ids: set[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in _read_csv(path):
        caseid = row.get("caseid", "")
        if caseid not in train_ids:
            continue
        if caseid in result:
            raise TrainTemplateError(f"duplicate train case in timing source: {path.name}: {caseid}")
        result[caseid] = row
    missing = train_ids - set(result)
    if missing:
        raise TrainTemplateError(f"timing source misses sealed train case: {min(missing, key=int)}")
    return result


def load_train_cases(root: Path | str) -> list[TrainCase]:
    """Validate the approved two-source timing lineage and return all train cases."""

    root = Path(root)
    operational_path = root / OPERATIONAL_TIMING_RELATIVE
    upstream_path = root / UPSTREAM_TIMING_RELATIVE
    observed = {
        "operational": sha256_path(operational_path),
        "upstream": sha256_path(upstream_path),
    }
    required = {
        "operational": OPERATIONAL_TIMING_SHA256,
        "upstream": UPSTREAM_TIMING_SHA256,
    }
    if observed != required:
        raise TrainTemplateError(f"anesthesia-window lineage checksum mismatch: {observed}")

    guard = SplitGuard.from_repository(root)
    case_rows = _read_csv(root / "data/manifests/phase8a_case_split_manifest.csv")
    train_rows = [row for row in case_rows if row.get("assigned_split") == "train"]
    if len(train_rows) != EXPECTED_TRAIN_CASES:
        raise TrainTemplateError("sealed train case accounting mismatch")
    train_ids = {row["caseid"] for row in train_rows}
    if len(train_ids) != EXPECTED_TRAIN_CASES:
        raise TrainTemplateError("duplicate sealed train case")
    guard.assert_train_cases(train_ids)
    operational = _unique_case_rows(operational_path, train_ids)
    upstream = _unique_case_rows(upstream_path, train_ids)

    cases: list[TrainCase] = []
    for split_row in train_rows:
        caseid = split_row["caseid"]
        op = operational[caseid]
        up = upstream[caseid]
        for field in ("anesthesia_start", "anesthesia_end"):
            if op.get(field) != up.get(field):
                raise TrainTemplateError(f"timing lineage string mismatch: {caseid}: {field}")
        try:
            start, end = float(op["anesthesia_start"]), float(op["anesthesia_end"])
            upstream_start, upstream_end = float(up["anesthesia_start"]), float(up["anesthesia_end"])
        except (KeyError, ValueError) as error:
            raise TrainTemplateError(f"invalid anesthesia timing text: {caseid}") from error
        if not all(math.isfinite(value) for value in (start, end, upstream_start, upstream_end)):
            raise TrainTemplateError(f"non-finite anesthesia timing: {caseid}")
        if start != upstream_start or end != upstream_end:
            raise TrainTemplateError(f"timing lineage numeric mismatch: {caseid}")
        if end <= start:
            raise TrainTemplateError(f"non-positive anesthesia window: {caseid}")
        cases.append(TrainCase(
            caseid=caseid,
            subjectid=split_row["subjectid"],
            anesthesia_start_text=op["anesthesia_start"],
            anesthesia_end_text=op["anesthesia_end"],
            anesthesia_start=start,
            anesthesia_end=end,
            source_cohort_protocol_version=split_row["source_cohort_protocol_version"],
            study_protocol_version=split_row["study_protocol_version"],
            split_manifest_version=split_row["split_manifest_version"],
        ))
    return sorted(cases, key=lambda case: (int(case.caseid), case.caseid))


def template_id_for_case(caseid: str, seal_payload_sha256: str = PHASE8A_SEAL_PAYLOAD_SHA256) -> str:
    payload = f"{TEMPLATE_FORMAT_VERSION}\0{seal_payload_sha256}\0{caseid}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized_relative(timestamp: float, anesthesia_start: float) -> float:
    value = float(timestamp - anesthesia_start)
    return 0.0 if value == 0.0 else value


def _npy_bytes(path: Path, array: np.ndarray) -> None:
    with path.open("wb") as stream:
        np.save(stream, array, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())


def payload_tree(directory: Path) -> tuple[str, list[dict[str, object]]]:
    entries: list[dict[str, object]] = []
    for filename in sorted(PAYLOAD_FILES):
        path = directory / filename
        entries.append({"relative_filename": filename, "bytes": path.stat().st_size, "sha256": sha256_path(path)})
    lines = "".join(
        f"{entry['relative_filename']}\t{entry['bytes']}\t{entry['sha256']}\n"
        for entry in entries
    )
    return hashlib.sha256(lines.encode("utf-8")).hexdigest(), entries


def verify_complete_template(directory: Path) -> tuple[str, dict[str, object]]:
    complete_path = directory / "COMPLETE.json"
    if not complete_path.is_file():
        raise TrainTemplateError(f"missing COMPLETE marker: {directory.name}")
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    if complete.get("complete") is not True:
        raise TrainTemplateError(f"invalid COMPLETE marker: {directory.name}")
    fingerprint, entries = payload_tree(directory)
    if complete.get("template_payload_tree_sha256") != fingerprint or complete.get("payload_files") != entries:
        raise TrainTemplateError(f"template payload fingerprint mismatch: {directory.name}")
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("template_id") != directory.name:
        raise TrainTemplateError("template directory/metadata identifier mismatch")
    return fingerprint, metadata


def extract_template(
    case: TrainCase,
    *,
    access: TrainRawAccessGuard,
    template_root: Path,
    access_purpose: str = "phase8b_train_template_extraction",
) -> ExtractedTemplate:
    template_id = template_id_for_case(case.caseid)
    final_directory = template_root / template_id
    if final_directory.exists():
        fingerprint, metadata = verify_complete_template(final_directory)
        expected_id = template_id_for_case(str(metadata.get("caseid", "")))
        if expected_id != template_id:
            raise TrainTemplateError("complete template belongs to a different case")
        return ExtractedTemplate(
            template_id, final_directory, fingerprint, metadata,
            sum((final_directory / name).stat().st_size for name in (*PAYLOAD_FILES, "COMPLETE.json")),
        )

    bis = access.parse_train_track(
        case.caseid, ALLOWED_TRACKS[0], case.anesthesia_start, case.anesthesia_end,
        access_purpose=access_purpose,
    )
    sqi = access.parse_train_track(
        case.caseid, ALLOWED_TRACKS[1], case.anesthesia_start, case.anesthesia_end,
        access_purpose=access_purpose,
    )
    horizon = float(case.anesthesia_end - case.anesthesia_start)
    bis_relative = np.asarray(
        [_normalized_relative(timestamp, case.anesthesia_start) for timestamp in bis.timestamps],
        dtype="<f8",
    )
    bis_available = np.asarray([0.0 <= value <= 100.0 for value in bis.values], dtype=np.bool_)
    bis_relative_by_absolute = {
        timestamp: relative for timestamp, relative in zip(bis.timestamps, bis_relative.tolist())
    }
    sqi_pairs = [
        (bis_relative_by_absolute[timestamp], value)
        for timestamp, value in zip(sqi.timestamps, sqi.values)
        if timestamp in bis_relative_by_absolute
    ]
    sqi_relative = np.asarray([pair[0] for pair in sqi_pairs], dtype="<f8")
    sqi_values = np.asarray([pair[1] for pair in sqi_pairs], dtype="<f8")
    if any(value < 0.0 or value > horizon for value in (*bis_relative.tolist(), *sqi_relative.tolist())):
        raise TrainTemplateError(f"relative event timestamp outside horizon: {case.caseid}")
    bis_available_at = dict(zip(bis_relative.tolist(), bis_available.tolist()))
    p1_accepted = sum(
        bool(bis_available_at[timestamp]) and value >= 50.0
        for timestamp, value in sqi_pairs
    )
    metadata: dict[str, object] = {
        "assigned_split": "train",
        "bis_available_count": int(bis_available.sum()),
        "bis_duplicate_timestamp_count": bis.duplicate_timestamp_count,
        "bis_event_count": int(bis_relative.size),
        "bis_negative_interval_count": bis.negative_interval_count,
        "bis_unavailable_finite_out_of_range_count": int((~bis_available).sum()),
        "bis_zero_interval_count": bis.zero_interval_count,
        "caseid": case.caseid,
        "episode_horizon_seconds": horizon,
        "p1_event_acceptance_count": int(p1_accepted),
        "phase8a_seal_payload_sha256": PHASE8A_SEAL_PAYLOAD_SHA256,
        "raw_bis_values_persisted": False,
        "raw_sqi_values_persisted_private": True,
        "same_template_for_p0_p1": True,
        "schema_version": SCHEMA_VERSION,
        "source_bis_file_sha256": access.logical_accesses[-2].observed_source_sha256,
        "source_cohort_protocol_version": case.source_cohort_protocol_version,
        "source_sqi_file_sha256": access.logical_accesses[-1].observed_source_sha256,
        "source_type": "vitaldb_train",
        "sqi_duplicate_timestamp_count": sqi.duplicate_timestamp_count,
        "sqi_exact_match_count": int(sqi_relative.size),
        "sqi_negative_interval_count": sqi.negative_interval_count,
        "sqi_outside_conventional_range_count": int(((sqi_values < 0.0) | (sqi_values > 100.0)).sum()),
        "sqi_zero_interval_count": sqi.zero_interval_count,
        "split_manifest_version": case.split_manifest_version,
        "study_protocol_version": case.study_protocol_version,
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
        write_json(temporary / "metadata.json", metadata)
        _npy_bytes(temporary / "bis_timestamp_seconds.npy", bis_relative)
        _npy_bytes(temporary / "bis_available.npy", bis_available)
        _npy_bytes(temporary / "sqi_timestamp_seconds.npy", sqi_relative)
        _npy_bytes(temporary / "sqi_value.npy", sqi_values)
        fingerprint, entries = payload_tree(temporary)
        write_json(temporary / "COMPLETE.json", {
            "complete": True,
            "payload_files": entries,
            "template_payload_tree_sha256": fingerprint,
        })
        # The destination is required to be absent. Windows scanners can hold a
        # just-fsynced file briefly, so retry only the same atomic directory rename.
        for attempt in range(12):
            try:
                os.rename(temporary, final_directory)
                break
            except PermissionError:
                if final_directory.exists() or attempt == 11:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    payload_bytes = sum((final_directory / name).stat().st_size for name in (*PAYLOAD_FILES, "COMPLETE.json"))
    return ExtractedTemplate(template_id, final_directory, fingerprint, metadata, payload_bytes)


def private_store_root_sha256(rows: list[dict[str, object]]) -> str:
    lines = "".join(
        f"{row['template_id']}\t{row['template_payload_tree_sha256']}\n"
        for row in sorted(rows, key=lambda row: str(row["template_id"]))
    )
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def empirical_quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {key: None for key in ("count", "minimum", "q1", "median", "q3", "maximum", "mean", "sample_sd")}
    mean = sum(values) / len(values)
    sample_sd = None
    if len(values) > 1:
        sample_sd = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
    return {
        "count": len(values), "minimum": min(values), "q1": empirical_quantile(values, 0.25),
        "median": empirical_quantile(values, 0.5), "q3": empirical_quantile(values, 0.75),
        "maximum": max(values), "mean": mean, "sample_sd": sample_sd,
    }

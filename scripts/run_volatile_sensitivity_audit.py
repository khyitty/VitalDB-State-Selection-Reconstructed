"""Run Phase 5D from checksum-verified local Phase 5C artifacts only."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.guards import CohortGuardError  # noqa: E402
from vitaldb_state_selection.cohort.volatile_characterization import (  # noqa: E402
    ALLOWED_TRACK_NAMES,
    atomic_json,
    sha256_path,
)
from vitaldb_state_selection.cohort.volatile_sensitivity import (  # noqa: E402
    EXPECTED_UNIVERSE_COUNT,
    absent_track_evidence,
    analyze_track_payload,
    build_case_record,
    build_sensitivity_summary,
    render_sensitivity_report,
)


MANIFEST_DIR = ROOT / "data" / "manifests"
RAW_ROOT = ROOT / "data" / "raw" / "phase5c_volatile_signals"
PHASE5C_CASE_PATH = MANIFEST_DIR / "volatile_signal_case_manifest.csv"
PHASE5C_TRACK_PATH = MANIFEST_DIR / "volatile_signal_track_manifest.csv"
PHASE5C_SNAPSHOT_PATH = MANIFEST_DIR / "volatile_signal_source_snapshot.json"
PHASE5C_ARTIFACT_CHECKSUM_PATH = (
    MANIFEST_DIR / "volatile_signal_artifact_checksums.json"
)
SUMMARY_PATH = MANIFEST_DIR / "volatile_exposure_rule_sensitivity_summary.json"
REPORT_PATH = ROOT / "docs" / "volatile_exposure_rule_sensitivity_report.md"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _repository_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _raw_tree_inventory() -> tuple[dict[str, tuple[int, str]], str]:
    inventory: dict[str, tuple[int, str]] = {}
    for path in sorted(item for item in RAW_ROOT.rglob("*") if item.is_file()):
        relative = path.relative_to(RAW_ROOT).as_posix()
        inventory[relative] = (path.stat().st_size, sha256_path(path))
    digest = hashlib.sha256()
    for relative, (size, checksum) in sorted(inventory.items()):
        digest.update(f"{relative}\0{size}\0{checksum}\n".encode("utf-8"))
    return inventory, digest.hexdigest()


def _verify_phase5c_artifacts() -> dict[str, str]:
    expected = json.loads(PHASE5C_ARTIFACT_CHECKSUM_PATH.read_text(encoding="utf-8"))
    if not isinstance(expected, dict) or not expected:
        raise CohortGuardError("Phase 5C artifact checksum inventory is missing or empty")
    for relative, checksum in expected.items():
        path = ROOT / relative
        if not path.is_file():
            raise CohortGuardError(f"Phase 5C source artifact is missing: {relative}")
        if sha256_path(path) != checksum:
            raise CohortGuardError(f"Phase 5C source artifact checksum mismatch: {relative}")
    return {str(key): str(value) for key, value in expected.items()}


def _validate_case_rows(rows: list[dict[str, str]]) -> dict[int, dict[str, str]]:
    by_case: dict[int, dict[str, str]] = {}
    for row in rows:
        caseid = int(row["caseid"])
        if caseid in by_case:
            raise CohortGuardError(f"duplicate Phase 5C case row: {caseid}")
        if row["analysis_universe_frozen"] != "false":
            raise CohortGuardError(f"Phase 5C case {caseid} is unexpectedly frozen")
        if row["legacy_overlap"] != "pending_not_evaluated":
            raise CohortGuardError(f"Phase 5C case {caseid} evaluated legacy overlap")
        by_case[caseid] = row
    if len(by_case) != EXPECTED_UNIVERSE_COUNT:
        raise CohortGuardError(
            f"Phase 5D expected {EXPECTED_UNIVERSE_COUNT} cases, got {len(by_case)}"
        )
    return by_case


def _safe_raw_path(relative: str) -> Path:
    path = (RAW_ROOT / relative).resolve()
    if RAW_ROOT.resolve() not in path.parents:
        raise CohortGuardError(f"raw path escaped Phase 5C root: {relative}")
    return path


def main() -> int:
    raw_before, raw_tree_sha_before = _raw_tree_inventory()
    artifact_checksums = _verify_phase5c_artifacts()
    case_rows = _validate_case_rows(_read_csv(PHASE5C_CASE_PATH))
    track_rows = _read_csv(PHASE5C_TRACK_PATH)
    if len(track_rows) != EXPECTED_UNIVERSE_COUNT * len(ALLOWED_TRACK_NAMES):
        raise CohortGuardError("Phase 5C track manifest is not a complete case×track matrix")

    tracks_by_case: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in track_rows:
        caseid = int(row["caseid"])
        if caseid not in case_rows:
            raise CohortGuardError(f"track row is outside the Phase 5C universe: {caseid}")
        if row["track_name"] not in ALLOWED_TRACK_NAMES:
            raise CohortGuardError(f"track row is outside the exact allowlist: {row['track_name']}")
        tracks_by_case[caseid].append(row)

    all_evidence = []
    case_records = []
    raw_signal_count = 0
    raw_signal_bytes = 0
    raw_signal_fingerprint = hashlib.sha256()
    for caseid, case_source in sorted(case_rows.items()):
        source_rows = tracks_by_case.get(caseid, [])
        if len(source_rows) != len(ALLOWED_TRACK_NAMES):
            raise CohortGuardError(f"case {caseid} does not have seven source track rows")
        if {row["track_name"] for row in source_rows} != set(ALLOWED_TRACK_NAMES):
            raise CohortGuardError(f"case {caseid} has a duplicate or missing exact track")
        evidence = []
        for row in sorted(source_rows, key=lambda item: ALLOWED_TRACK_NAMES.index(item["track_name"])):
            track_name = row["track_name"]
            status = row["download_status"]
            if status == "track_absent":
                item = absent_track_evidence(caseid, track_name)
            elif status == "complete":
                relative = row["raw_relative_path"]
                path = _safe_raw_path(relative)
                if not path.is_file():
                    raise CohortGuardError(f"Phase 5C raw signal is missing: {relative}")
                payload = path.read_bytes()
                checksum = hashlib.sha256(payload).hexdigest()
                if checksum != row["raw_sha256"]:
                    raise CohortGuardError(f"Phase 5C raw checksum mismatch: {relative}")
                if len(payload) != int(row["raw_byte_count"]):
                    raise CohortGuardError(f"Phase 5C raw byte count mismatch: {relative}")
                raw_signal_count += 1
                raw_signal_bytes += len(payload)
                raw_signal_fingerprint.update(
                    f"{relative}\0{checksum}\0{len(payload)}\n".encode("utf-8")
                )
                item = analyze_track_payload(
                    payload,
                    caseid=caseid,
                    track_name=track_name,
                    anesthesia_start=float(case_source["anesthesia_start"]),
                    anesthesia_end=float(case_source["anesthesia_end"]),
                )
            else:
                raise CohortGuardError(
                    f"Phase 5D refuses unresolved Phase 5C status {status!r} for "
                    f"case {caseid} {track_name}"
                )
            evidence.append(item)
            all_evidence.append(item)
        case_records.append(build_case_record(case_source, evidence))

    if raw_signal_count != 9059:
        raise CohortGuardError(f"expected 9,059 Phase 5C raw signals, got {raw_signal_count}")

    raw_after, raw_tree_sha_after = _raw_tree_inventory()
    if raw_before != raw_after or raw_tree_sha_before != raw_tree_sha_after:
        raise CohortGuardError("raw tree changed during the read-only Phase 5D audit")

    source_snapshot = json.loads(PHASE5C_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    source_integrity = {
        "phase5c_base_remote_commit": "34b3770c4cfdb1803feb2018c2c861975c547ef9",
        "phase5d_code_base_commit": _repository_commit(),
        "phase5c_artifact_checksums_verified": True,
        "phase5c_artifact_checksums": artifact_checksums,
        "phase5c_source_snapshot_sha256": sha256_path(PHASE5C_SNAPSHOT_PATH),
        "phase5c_source_version": source_snapshot["source_version"],
        "phase5c_case_manifest_sha256": sha256_path(PHASE5C_CASE_PATH),
        "phase5c_track_manifest_sha256": sha256_path(PHASE5C_TRACK_PATH),
        "raw_signal_checksum_verified_count": raw_signal_count,
        "raw_signal_total_bytes": raw_signal_bytes,
        "raw_signal_manifest_fingerprint_sha256": raw_signal_fingerprint.hexdigest(),
        "raw_tree_file_count_before": len(raw_before),
        "raw_tree_file_count_after": len(raw_after),
        "raw_tree_content_fingerprint_before": raw_tree_sha_before,
        "raw_tree_content_fingerprint_after": raw_tree_sha_after,
        "raw_tree_unchanged": True,
        "new_raw_file_count": 0,
        "api_request_count": 0,
    }
    summary = build_sensitivity_summary(
        case_records, all_evidence, source_integrity=source_integrity
    )
    report = render_sensitivity_report(summary)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8", newline="\n")
    summary["generated_at"] = datetime.now(UTC).isoformat()
    summary["report_sha256"] = sha256_path(REPORT_PATH)
    atomic_json(SUMMARY_PATH, summary)
    print(
        json.dumps(
            {
                "case_count": summary["analysis_universe"]["case_count"],
                "definition_summaries": summary["definition_summaries"],
                "protocol_candidates": summary["protocol_candidates"],
                "raw_signal_checksum_verified_count": raw_signal_count,
                "raw_tree_unchanged": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

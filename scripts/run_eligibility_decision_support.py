"""Run Phase 5B: outcome-blind eligibility decision support only."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection import __version__  # noqa: E402
from vitaldb_state_selection.cohort.decision_support import (  # noqa: E402
    OFFICIAL_DATASET_OVERVIEW,
    OFFICIAL_OPEN_DATASET_API,
    RATE_DOCUMENTATION,
    assert_phase5b_boundaries,
    build_relevant_track_presence,
    render_decision_support_report,
    summarize_decision_support,
)
from vitaldb_state_selection.cohort.eligibility import load_audit_config  # noqa: E402
from vitaldb_state_selection.cohort.metadata_audit import (  # noqa: E402
    EXPECTED_ACTIVE_ALIASES,
    prepare_source_rows,
    sha256_path,
)
from vitaldb_state_selection.cohort.track_inventory import AliasRegistry  # noqa: E402
from vitaldb_state_selection.data.vitaldb_api import (  # noqa: E402
    API_BASE,
    API_DOCUMENTATION,
    VitalDBOpenAPI,
)
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    read_csv_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 5B metadata-only eligibility decision support"
    )
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "eligibility_audit.yaml")
    parser.add_argument("--aliases", type=Path, default=ROOT / "configs" / "track_aliases.yaml")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "data" / "manifests" / "all_case_eligibility_manifest.csv",
    )
    parser.add_argument(
        "--phase5a-source-snapshot",
        type=Path,
        default=ROOT / "data" / "manifests" / "metadata_audit_source_snapshot.json",
    )
    parser.add_argument(
        "--presence-output",
        type=Path,
        default=ROOT / "data" / "manifests" / "research_relevant_track_presence.csv",
    )
    parser.add_argument(
        "--track-review-output",
        type=Path,
        default=ROOT / "data" / "manifests" / "research_relevant_unapproved_tracks.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "data" / "manifests" / "eligibility_decision_support_summary.json",
    )
    parser.add_argument(
        "--source-snapshot",
        type=Path,
        default=ROOT / "data" / "manifests" / "eligibility_decision_support_source_snapshot.json",
    )
    parser.add_argument(
        "--failure-log",
        type=Path,
        default=ROOT / "data" / "manifests" / "eligibility_decision_support_failures.jsonl",
    )
    parser.add_argument(
        "--checksums",
        type=Path,
        default=ROOT / "data" / "manifests" / "eligibility_decision_support_artifact_checksums.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "docs" / "decision_support_report.md",
    )
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _write_json(path: Path, value: object) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    _atomic_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _csv_value(value: object) -> object:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return value


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write headerless CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _csv_value(value) for key, value in row.items()})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _repository_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def main() -> int:
    args = parse_args()
    query_started_at = datetime.now(UTC).isoformat()
    config = load_audit_config(args.config)
    registry = AliasRegistry.from_yaml(args.aliases)
    schema = load_schema(ROOT / "schemas" / "eligibility_manifest.schema.json")
    manifest_records = read_csv_manifest(args.manifest, schema)
    phase5a_snapshot = json.loads(args.phase5a_source_snapshot.read_text(encoding="utf-8"))
    assert_phase5b_boundaries(config, registry, manifest_records, phase5a_snapshot)

    failures: list[dict[str, object]] = []
    try:
        track_snapshot = VitalDBOpenAPI(timeout_seconds=args.timeout_seconds).fetch_tracks()
    except Exception as exc:
        failures.append(
            {
                "scope": "endpoint",
                "source": "/trks",
                "timestamp": query_started_at,
                "failure_type": type(exc).__name__,
                "failure_message": str(exc),
                "retryable": True,
            }
        )
        _write_jsonl(args.failure_log, failures)
        return 1

    prepared = prepare_source_rows(track_snapshot.rows, source="tracks")
    for event in prepared.events:
        failures.append({**event, "timestamp": query_started_at})
    expected_track_sha = phase5a_snapshot["endpoints"]["tracks"]["sha256"]
    if track_snapshot.sha256 != expected_track_sha:
        failures.append(
            {
                "scope": "source_snapshot",
                "source": "/trks",
                "timestamp": query_started_at,
                "failure_type": "phase5a_source_drift",
                "failure_message": (
                    f"Phase 5A SHA-256 {expected_track_sha} differs from "
                    f"Phase 5B SHA-256 {track_snapshot.sha256}"
                ),
                "retryable": False,
            }
        )
    _write_jsonl(args.failure_log, failures)
    if failures:
        return 1

    caseids = [row["caseid"] for row in manifest_records]
    presence, relevant_inventory = build_relevant_track_presence(caseids, prepared.rows)
    _write_csv(args.presence_output, presence)
    _write_csv(args.track_review_output, relevant_inventory)

    summary = summarize_decision_support(
        manifest_records, presence, relevant_inventory
    )
    query_completed_at = datetime.now(UTC).isoformat()
    source_version = (
        f"vitaldb_open_api_client={__version__};"
        f"phase5a_manifest_sha256={sha256_path(args.manifest)};"
        f"tracks_sha256={track_snapshot.sha256}"
    )
    summary.update(
        {
            "query_started_at": query_started_at,
            "query_completed_at": query_completed_at,
            "source_version": source_version,
            "source_track_row_count": len(prepared.rows),
            "source_unique_track_name_count": len(
                {str(row["tname"]).strip() for row in prepared.rows}
            ),
            "source_failure_count": len(failures),
        }
    )
    source_snapshot = {
        "schema_version": 1,
        "phase": "5B_eligibility_decision_support_audit",
        "query_started_at": query_started_at,
        "query_completed_at": query_completed_at,
        "audit_code_base_commit": _repository_commit(),
        "source_version": source_version,
        "client": {
            "implementation": "vitaldb_state_selection.data.vitaldb_api.VitalDBOpenAPI",
            "version": __version__,
            "api_base": API_BASE,
            "api_documentation": API_DOCUMENTATION,
        },
        "inputs": {
            "phase5a_manifest": args.manifest.relative_to(ROOT).as_posix(),
            "phase5a_manifest_sha256": sha256_path(args.manifest),
            "phase5a_source_snapshot": args.phase5a_source_snapshot.relative_to(ROOT).as_posix(),
            "phase5a_source_snapshot_sha256": sha256_path(args.phase5a_source_snapshot),
            "phase5a_tracks_sha256": expected_track_sha,
        },
        "endpoint": {
            "path": "/trks",
            "url": track_snapshot.url,
            "fetched_at": track_snapshot.fetched_at,
            "row_count": len(track_snapshot.rows),
            "byte_count": track_snapshot.byte_count,
            "elapsed_seconds": track_snapshot.elapsed_seconds,
            "sha256": track_snapshot.sha256,
            "matches_phase5a_snapshot": True,
            "status": "complete",
        },
        "configuration_checksums": {
            "eligibility_audit_yaml_sha256": sha256_path(args.config),
            "track_aliases_yaml_sha256": sha256_path(args.aliases),
            "eligibility_manifest_schema_sha256": sha256_path(
                ROOT / "schemas" / "eligibility_manifest.schema.json"
            ),
        },
        "active_exact_aliases": {
            concept: list(names) for concept, names in EXPECTED_ACTIVE_ALIASES.items()
        },
        "primary_source_review": {
            "accessed_at": query_completed_at,
            "official_vitaldb_dataset_overview": OFFICIAL_DATASET_OVERVIEW,
            "official_vitaldb_open_dataset_api": OFFICIAL_OPEN_DATASET_API,
            "rate_findings": [dict(item) for item in RATE_DOCUMENTATION],
            "final_review_status": "pending_human_review",
        },
        "scope": {
            "queried_endpoints": ["/trks"],
            "raw_time_series_requests": 0,
            "legacy_98_ids_accessed": False,
            "legacy_overlap_evaluated": False,
            "phase5a_unapproved_name_total": 193,
            "research_relevant_names_reviewed": len(relevant_inventory),
            "all_unapproved_names_semantically_classified": False,
        },
        "prohibited_execution": {
            "raw_signal_download": False,
            "final_alias_approval": False,
            "unit_status_change": False,
            "threshold_finalization": False,
            "cohort_freeze": False,
            "split_creation": False,
            "prediction": False,
            "feature_selection": False,
            "cpce_reconstruction": False,
            "ppo": False,
        },
    }
    _write_json(args.source_snapshot, source_snapshot)
    _write_json(args.summary, summary)
    _atomic_text(args.report, render_decision_support_report(summary))
    artifact_paths = (
        args.presence_output,
        args.track_review_output,
        args.summary,
        args.source_snapshot,
        args.failure_log,
        args.report,
    )
    _write_json(
        args.checksums,
        {
            path.relative_to(ROOT).as_posix(): sha256_path(path)
            for path in artifact_paths
        },
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

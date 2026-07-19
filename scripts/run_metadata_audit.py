"""Run Phase 5A: full 1–6388 metadata and exact-track inventory only."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection import __version__  # noqa: E402
from vitaldb_state_selection.cohort.eligibility import (  # noqa: E402
    build_eligibility_records,
    load_audit_config,
)
from vitaldb_state_selection.cohort.metadata_audit import (  # noqa: E402
    EXPECTED_ACTIVE_ALIASES,
    PENDING_DECISIONS,
    assert_phase5a_boundaries,
    build_unapproved_alias_candidates,
    merge_case_failures,
    prepare_source_rows,
    render_outcome_blind_report,
    sha256_path,
    summarize_full_metadata_audit,
)
from vitaldb_state_selection.cohort.track_inventory import AliasRegistry  # noqa: E402
from vitaldb_state_selection.data.vitaldb_api import (  # noqa: E402
    API_BASE,
    API_DOCUMENTATION,
    CsvSnapshot,
    VitalDBOpenAPI,
)
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    write_csv_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 5A full metadata and exact-track inventory; no signal downloads "
            "or eligibility decisions."
        )
    )
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs" / "eligibility_audit.yaml"
    )
    parser.add_argument(
        "--aliases", type=Path, default=ROOT / "configs" / "track_aliases.yaml"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "manifests" / "all_case_eligibility_manifest.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "data" / "manifests" / "metadata_audit_summary.json",
    )
    parser.add_argument(
        "--source-snapshot",
        type=Path,
        default=ROOT / "data" / "manifests" / "metadata_audit_source_snapshot.json",
    )
    parser.add_argument(
        "--failure-log",
        type=Path,
        default=ROOT / "data" / "manifests" / "metadata_audit_failures.jsonl",
    )
    parser.add_argument(
        "--alias-candidates",
        type=Path,
        default=ROOT / "data" / "manifests" / "unapproved_alias_candidates.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "docs" / "full_metadata_track_inventory_audit_report.md",
    )
    parser.add_argument(
        "--checksums",
        type=Path,
        default=ROOT / "data" / "manifests" / "metadata_audit_artifact_checksums.json",
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
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _write_json(path: Path, payload: object) -> None:
    _atomic_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    _atomic_text(path, text)


def _write_candidate_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = (
        "track_name",
        "row_count",
        "case_count",
        "distinct_tid_count",
        "review_status",
        "auto_approved",
    )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    _atomic_text(path, buffer.getvalue())


def _api_failure(endpoint: str, timestamp: str, error: BaseException) -> dict[str, object]:
    return {
        "scope": "api_query",
        "source": endpoint,
        "row_index": None,
        "caseid": None,
        "timestamp": timestamp,
        "failure_type": type(error).__name__,
        "failure_message": str(error),
        "retryable": True,
        "exception_summary": f"{type(error).__module__}.{type(error).__name__}: {error}",
    }


def _endpoint_snapshot(
    endpoint: str,
    snapshot: CsvSnapshot | None,
    failure: Mapping[str, object] | None,
) -> dict[str, object]:
    if snapshot is None:
        return {
            "endpoint": f"/{endpoint}",
            "status": "failed",
            "url": f"{API_BASE}/{endpoint}",
            "row_count": 0,
            "byte_count": 0,
            "sha256": None,
            "elapsed_seconds": None,
            "fetched_at": None,
            "failure_type": failure["failure_type"] if failure else "unknown",
            "failure_message": failure["failure_message"] if failure else "unknown",
        }
    return {
        "endpoint": f"/{endpoint}",
        "status": "complete",
        "url": snapshot.url,
        "row_count": len(snapshot.rows),
        "byte_count": snapshot.byte_count,
        "sha256": snapshot.sha256,
        "elapsed_seconds": snapshot.elapsed_seconds,
        "fetched_at": snapshot.fetched_at,
        "failure_type": None,
        "failure_message": None,
    }


def _repository_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def main() -> int:
    args = parse_args()
    config = load_audit_config(args.config)
    registry = AliasRegistry.from_yaml(args.aliases)
    assert_phase5a_boundaries(config, registry)
    client = VitalDBOpenAPI(timeout_seconds=args.timeout_seconds)
    query_started_at = datetime.now(UTC).isoformat()
    endpoint_failures: list[dict[str, object]] = []
    cases: CsvSnapshot | None = None
    tracks: CsvSnapshot | None = None

    try:
        cases = client.fetch_cases()
    except Exception as exc:
        endpoint_failures.append(_api_failure("cases", query_started_at, exc))
    try:
        tracks = client.fetch_tracks()
    except Exception as exc:
        endpoint_failures.append(_api_failure("trks", query_started_at, exc))

    cases_prepared = prepare_source_rows(
        cases.rows if cases is not None else [], source="cases"
    )
    tracks_prepared = prepare_source_rows(
        tracks.rows if tracks is not None else [], source="tracks"
    )
    source_row_events = [*cases_prepared.events, *tracks_prepared.events]
    for event in source_row_events:
        event["timestamp"] = query_started_at
    failures_by_case = merge_case_failures(
        cases_prepared.case_failures, tracks_prepared.case_failures
    )
    global_failures = [
        f"{event['source']}_query:{event['failure_type']}:{event['failure_message']}"
        for event in endpoint_failures
    ]
    source_version_parts = [f"vitaldb_open_api_client={__version__}"]
    if cases is not None:
        source_version_parts.append(f"cases_sha256={cases.sha256}")
    if tracks is not None:
        source_version_parts.append(f"tracks_sha256={tracks.sha256}")
    source_version = ";".join(source_version_parts)

    records = build_eligibility_records(
        cases_prepared.rows,
        tracks_prepared.rows,
        config=config,
        registry=registry,
        source_version=source_version,
        query_timestamp=query_started_at,
        clinical_query_available=cases is not None,
        track_query_available=tracks is not None,
        source_failures=global_failures,
        case_failures=failures_by_case,
        legacy_caseids=None,
    )
    schema_path = ROOT / "schemas" / "eligibility_manifest.schema.json"
    schema = load_schema(schema_path)
    write_csv_manifest(args.output, records, schema)

    candidates = build_unapproved_alias_candidates(tracks_prepared.rows, registry)
    _write_candidate_csv(args.alias_candidates, candidates)
    manifest_failures = [
        {
            "scope": "manifest_row",
            "source": "combined_metadata_track_inventory",
            "row_index": None,
            "caseid": int(record["caseid"]),
            "timestamp": query_started_at,
            "failure_type": str(record["failure_type"]),
            "failure_message": str(record["failure_message"]),
            "retryable": False,
        }
        for record in records
        if record["audit_status"] == "failed"
    ]
    all_failures = [*endpoint_failures, *source_row_events, *manifest_failures]
    _write_jsonl(args.failure_log, all_failures)

    query_completed_at = datetime.now(UTC).isoformat()
    endpoints = {
        "cases": _endpoint_snapshot(
            "cases",
            cases,
            next((item for item in endpoint_failures if item["source"] == "cases"), None),
        ),
        "tracks": _endpoint_snapshot(
            "trks",
            tracks,
            next((item for item in endpoint_failures if item["source"] == "trks"), None),
        ),
    }
    source_snapshot = {
        "schema_version": 1,
        "phase": "5A_full_metadata_and_track_inventory",
        "audit_name": config["audit_name"],
        "query_started_at": query_started_at,
        "query_completed_at": query_completed_at,
        "source_version": source_version,
        "audit_code_base_commit": _repository_commit(),
        "client": {
            "implementation": "vitaldb_state_selection.data.vitaldb_api.VitalDBOpenAPI",
            "version": __version__,
            "api_base": API_BASE,
            "api_documentation": API_DOCUMENTATION,
        },
        "endpoints": endpoints,
        "configuration_checksums": {
            "eligibility_audit_yaml_sha256": sha256_path(args.config),
            "track_aliases_yaml_sha256": sha256_path(args.aliases),
            "eligibility_manifest_schema_sha256": sha256_path(schema_path),
        },
        "active_exact_aliases": {
            concept: list(names) for concept, names in EXPECTED_ACTIVE_ALIASES.items()
        },
        "pending_decisions": list(PENDING_DECISIONS),
        "scope": {
            "queried_endpoints": ["/cases", "/trks"],
            "raw_time_series_requests": 0,
            "legacy_98_ids_accessed": False,
            "legacy_overlap_evaluated": False,
        },
        "prohibited_execution": {
            "full_signal_download": False,
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

    summary = summarize_full_metadata_audit(
        records,
        track_rows=tracks_prepared.rows,
        source_events=source_row_events,
        candidates=candidates,
    )
    summary.update(
        {
            "audit_name": config["audit_name"],
            "query_started_at": query_started_at,
            "query_completed_at": query_completed_at,
            "source_version": source_version,
            "api_failure_type_counts": dict(
                sorted(Counter(str(row["failure_type"]) for row in endpoint_failures).items())
            ),
            "failure_log_row_count": len(all_failures),
        }
    )
    _write_json(args.summary, summary)
    _atomic_text(
        args.report,
        render_outcome_blind_report(summary, source_snapshot, candidates),
    )

    artifact_paths = (
        args.output,
        args.summary,
        args.source_snapshot,
        args.failure_log,
        args.alias_candidates,
        args.report,
    )
    checksums = {
        path.relative_to(ROOT).as_posix(): sha256_path(path) for path in artifact_paths
    }
    _write_json(args.checksums, checksums)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 1 if endpoint_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

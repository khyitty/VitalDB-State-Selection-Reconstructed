"""Run Phase 5C targeted volatile-signal preflight or full characterization."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection import __version__  # noqa: E402
from vitaldb_state_selection.cohort.metadata_audit import (  # noqa: E402
    prepare_source_rows,
)
from vitaldb_state_selection.cohort.volatile_characterization import (  # noqa: E402
    ALLOWED_TRACK_NAMES,
    EXPECTED_UNIVERSE_COUNT,
    MAX_ATTEMPTS,
    OFFICIAL_DATASET_OVERVIEW,
    PHASE5C_SEED,
    ProgressLog,
    VolatileTask,
    assert_no_partials,
    atomic_json,
    build_case_manifest,
    build_phase5c_universe,
    build_preflight_summary,
    build_tasks,
    download_one_task,
    load_verified_metadata,
    remove_stale_partials,
    render_preflight_report,
    render_volatile_report,
    sha256_path,
    stratified_preflight_caseids,
    summarize_volatile_characterization,
    track_manifest_row,
)
from vitaldb_state_selection.data.vitaldb_api import (  # noqa: E402
    API_BASE,
    API_DOCUMENTATION,
    VitalDBOpenAPI,
)
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    read_csv_manifest,
)


MANIFEST_DIR = ROOT / "data" / "manifests"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 5C volatile-only engineering characterization"
    )
    parser.add_argument("--stage", choices=("preflight", "full"), required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=ROOT / "data" / "raw" / "phase5c_volatile_signals",
    )
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
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _csv_value(value: object) -> object:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def _atomic_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty CSV: {path}")
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
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _read_presence(path: Path) -> list[dict[str, object]]:
    boolean_fields = {
        "primus_exp_sevo_present",
        "primus_insp_sevo_present",
        "primus_exp_des_present",
        "primus_insp_des_present",
        "solar8000_gas2_expired_present",
        "solar8000_gas2_inspired_present",
        "primus_mac_present",
    }
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    parsed: list[dict[str, object]] = []
    for source in rows:
        row: dict[str, object] = {"caseid": int(source["caseid"])}
        for field in boolean_fields:
            if source[field] not in {"true", "false"}:
                raise ValueError(f"invalid presence boolean {field}={source[field]!r}")
            row[field] = source[field] == "true"
        parsed.append(row)
    return parsed


def _repository_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _load_inputs() -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    schema = load_schema(ROOT / "schemas" / "eligibility_manifest.schema.json")
    manifest = read_csv_manifest(
        MANIFEST_DIR / "all_case_eligibility_manifest.csv", schema
    )
    presence = _read_presence(MANIFEST_DIR / "research_relevant_track_presence.csv")
    phase5b = json.loads(
        (MANIFEST_DIR / "eligibility_decision_support_source_snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    return manifest, presence, phase5b


def _run_downloads(
    tasks: list[VolatileTask],
    *,
    raw_root: Path,
    workers: int,
    timeout_seconds: float,
    source_version: str,
    progress: ProgressLog,
) -> dict[str, dict[str, object]]:
    if workers < 1 or workers > 16:
        raise ValueError("workers must be between 1 and 16")
    thread_state = threading.local()

    def execute(task: VolatileTask) -> dict[str, object]:
        client = getattr(thread_state, "client", None)
        if client is None:
            client = VitalDBOpenAPI(timeout_seconds=timeout_seconds)
            thread_state.client = client
        return download_one_task(
            task,
            raw_root=raw_root,
            client=client,
            progress=progress,
            source_version=source_version,
        )

    results: dict[str, dict[str, object]] = {}
    total = len(tasks)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, task): task for task in tasks}
        for completed, future in enumerate(as_completed(futures), start=1):
            task = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "caseid": task.caseid,
                    "track_name": task.track_name,
                    "tid": task.tids[0],
                    "status": "internal_failed",
                    "attempt_count": progress.attempt_count(task),
                    "raw_relative_path": None,
                    "raw_byte_count": 0,
                    "raw_sha256": None,
                    "source_version": source_version,
                    "response_metadata": None,
                    "parsing": None,
                    "failure_type": type(exc).__name__,
                    "failure_message": str(exc),
                    "retryable": False,
                }
            results[task.key] = result
            if completed % 100 == 0 or completed == total:
                print(f"volatile download progress {completed}/{total}", flush=True)
    return results


def _failure_events(progress_path: Path, track_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            row = json.loads(line)
            if row.get("failure_type"):
                events.append(row)
    for row in track_rows:
        if row["download_status"] == "ambiguous_multiple_tids":
            events.append(
                {
                    "event": "structural_failure",
                    "caseid": row["caseid"],
                    "track_name": row["track_name"],
                    "failure_type": row["failure_type"],
                    "failure_message": row["failure_message"],
                    "retryable": False,
                }
            )
    return events


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    _atomic_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _source_snapshot(
    *,
    stage: str,
    tracks: object,
    source_version: str,
    phase5b: dict[str, object],
    task_count: int,
    preflight: dict[str, object] | None,
    removed_partials: list[str],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "phase": "5C_targeted_volatile_signal_characterization",
        "stage": stage,
        "audit_code_base_commit": _repository_commit(),
        "recorded_at": datetime.now(UTC).isoformat(),
        "source_version": source_version,
        "client": {
            "implementation": "vitaldb_state_selection.data.vitaldb_api.VitalDBOpenAPI",
            "version": __version__,
            "api_base": API_BASE,
            "api_documentation": API_DOCUMENTATION,
        },
        "track_list_endpoint": {
            "path": "/trks",
            "url": tracks.url,
            "fetched_at": tracks.fetched_at,
            "row_count": len(tracks.rows),
            "byte_count": tracks.byte_count,
            "elapsed_seconds": tracks.elapsed_seconds,
            "sha256": tracks.sha256,
            "matches_phase5b_snapshot": tracks.sha256 == phase5b["endpoint"]["sha256"],
        },
        "inputs": {
            "phase5a_manifest_sha256": sha256_path(
                MANIFEST_DIR / "all_case_eligibility_manifest.csv"
            ),
            "phase5b_presence_sha256": sha256_path(
                MANIFEST_DIR / "research_relevant_track_presence.csv"
            ),
            "phase5b_summary_sha256": sha256_path(
                MANIFEST_DIR / "eligibility_decision_support_summary.json"
            ),
        },
        "scope": {
            "analysis_universe_case_count": EXPECTED_UNIVERSE_COUNT,
            "allowed_exact_track_names": list(ALLOWED_TRACK_NAMES),
            "raw_track_request_count": task_count,
            "legacy_98_ids_accessed": False,
            "legacy_overlap_evaluated": False,
            "other_raw_track_requests": 0,
            "stale_partial_files_removed": removed_partials,
        },
        "official_track_documentation": {
            "source_url": OFFICIAL_DATASET_OVERVIEW,
            "approval_status": "pending_human_review",
        },
        "preflight_gate": preflight,
        "prohibited_execution": {
            "final_volatile_exposure_decision": False,
            "final_tiva_decision": False,
            "final_alias_approval": False,
            "final_unit_approval": False,
            "threshold_finalization": False,
            "cohort_freeze": False,
            "split_creation": False,
            "bis_signal_download": False,
            "drug_signal_download": False,
            "prediction_preprocessing": False,
            "prediction": False,
            "feature_selection": False,
            "cpce_reconstruction": False,
            "ppo": False,
        },
    }


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.workers > 16:
        raise ValueError("workers must be between 1 and 16")
    removed_partials = remove_stale_partials(args.raw_root)
    manifest, presence, phase5b = _load_inputs()
    universe = build_phase5c_universe(manifest, presence)
    client = VitalDBOpenAPI(timeout_seconds=args.timeout_seconds)
    tracks = client.fetch_tracks()
    if tracks.sha256 != phase5b["endpoint"]["sha256"]:
        raise RuntimeError("/trks source drifted from the Phase 5B snapshot")
    prepared = prepare_source_rows(tracks.rows, source="tracks")
    if prepared.events:
        raise RuntimeError(f"/trks source-row failures observed: {len(prepared.events)}")
    tasks = build_tasks(universe, prepared.rows)
    source_version = (
        f"vitaldb_open_api_client={__version__};tracks_sha256={tracks.sha256};"
        f"phase5a_manifest_sha256={sha256_path(MANIFEST_DIR / 'all_case_eligibility_manifest.csv')};"
        f"phase5b_presence_sha256={sha256_path(MANIFEST_DIR / 'research_relevant_track_presence.csv')}"
    )
    progress_path = args.raw_root / "download_attempts.jsonl"
    progress = ProgressLog(progress_path)
    preflight_summary_path = MANIFEST_DIR / "volatile_signal_preflight_summary.json"
    preflight_report_path = ROOT / "docs" / "volatile_signal_preflight_report.md"

    if args.stage == "preflight":
        selected_caseids = stratified_preflight_caseids(universe)
        selected = set(selected_caseids)
        selected_tasks = [
            task for task in tasks if task.caseid in selected and len(task.tids) == 1
        ]
        results = _run_downloads(
            selected_tasks,
            raw_root=args.raw_root,
            workers=args.workers,
            timeout_seconds=args.timeout_seconds,
            source_version=source_version,
            progress=progress,
        )
        disk_free = shutil.disk_usage(args.raw_root.parent).free
        preflight = build_preflight_summary(
            universe,
            tasks,
            selected_caseids,
            results,
            raw_root=args.raw_root,
            source_version=source_version,
            disk_free_bytes=disk_free,
            workers=args.workers,
        )
        atomic_json(preflight_summary_path, preflight)
        _atomic_text(preflight_report_path, render_preflight_report(preflight))
        atomic_json(
            MANIFEST_DIR / "volatile_signal_source_snapshot.json",
            _source_snapshot(
                stage="preflight",
                tracks=tracks,
                source_version=source_version,
                phase5b=phase5b,
                task_count=len(selected_tasks),
                preflight=preflight,
                removed_partials=removed_partials,
            ),
        )
        assert_no_partials(args.raw_root)
        print(json.dumps(preflight, ensure_ascii=False, sort_keys=True))
        return 0

    if not preflight_summary_path.is_file():
        raise RuntimeError("full stage requires the committed-in-worktree preflight summary")
    preflight = json.loads(preflight_summary_path.read_text(encoding="utf-8"))
    if preflight.get("source_version") != source_version:
        raise RuntimeError("preflight source version does not match the full-stage source")
    if preflight.get("full_download_authorized_by_gate") is not True:
        raise RuntimeError("preflight gate did not authorize the full download")

    downloadable = [task for task in tasks if len(task.tids) == 1]
    results = _run_downloads(
        downloadable,
        raw_root=args.raw_root,
        workers=args.workers,
        timeout_seconds=args.timeout_seconds,
        source_version=source_version,
        progress=progress,
    )
    track_rows: list[dict[str, object]] = []
    for task in tasks:
        metadata = results.get(task.key)
        if metadata is None and len(task.tids) == 1:
            metadata = load_verified_metadata(args.raw_root, task)
        track_rows.append(
            track_manifest_row(
                task, metadata, raw_root=args.raw_root, source_version=source_version
            )
        )
    case_rows = build_case_manifest(universe, track_rows, source_version=source_version)
    summary = summarize_volatile_characterization(
        case_rows, track_rows, source_version=source_version
    )
    summary.update(
        {
            "query_completed_at": datetime.now(UTC).isoformat(),
            "preflight_summary": preflight,
            "raw_signal_commit_policy": "git_ignored_not_committed",
        }
    )
    case_manifest_path = MANIFEST_DIR / "volatile_signal_case_manifest.csv"
    track_manifest_path = MANIFEST_DIR / "volatile_signal_track_manifest.csv"
    summary_path = MANIFEST_DIR / "volatile_signal_characterization_summary.json"
    source_snapshot_path = MANIFEST_DIR / "volatile_signal_source_snapshot.json"
    failure_log_path = MANIFEST_DIR / "volatile_signal_failures.jsonl"
    report_path = ROOT / "docs" / "volatile_signal_decision_support_report.md"
    _atomic_csv(case_manifest_path, case_rows)
    _atomic_csv(track_manifest_path, track_rows)
    atomic_json(summary_path, summary)
    source_snapshot = _source_snapshot(
        stage="full",
        tracks=tracks,
        source_version=source_version,
        phase5b=phase5b,
        task_count=len(downloadable),
        preflight=preflight,
        removed_partials=removed_partials,
    )
    atomic_json(source_snapshot_path, source_snapshot)
    failures = _failure_events(progress_path, track_rows)
    _write_jsonl(failure_log_path, failures)
    _atomic_text(report_path, render_volatile_report(summary, preflight))
    assert_no_partials(args.raw_root)

    artifact_paths = (
        preflight_summary_path,
        preflight_report_path,
        case_manifest_path,
        track_manifest_path,
        summary_path,
        source_snapshot_path,
        failure_log_path,
        report_path,
    )
    atomic_json(
        MANIFEST_DIR / "volatile_signal_artifact_checksums.json",
        {
            path.relative_to(ROOT).as_posix(): sha256_path(path)
            for path in artifact_paths
        },
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

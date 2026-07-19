"""Run the Protocol v1.1 Phase 6A preflight or full primary acquisition."""

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
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection import __version__  # noqa: E402
from vitaldb_state_selection.cohort.metadata_audit import prepare_source_rows  # noqa: E402
from vitaldb_state_selection.cohort.primary_acquisition import (  # noqa: E402
    EXPECTED_UNIVERSE_COUNT,
    PHASE5D_PRIMARY_DEFINITION,
    PRIMARY_TRACK_NAMES,
    PRIMARY_TRACKS,
    ProgressLog,
    PrimaryTask,
    assert_no_partials,
    atomic_json,
    build_pre_quality_manifest,
    build_preflight_summary,
    build_tasks,
    download_one_task,
    fixed_seed_preflight_caseids,
    load_verified_metadata,
    manifest_row,
    remove_stale_partials,
    sha256_path,
)
from vitaldb_state_selection.data.vitaldb_api import (  # noqa: E402
    API_BASE,
    API_DOCUMENTATION,
    VitalDBOpenAPI,
)


MANIFEST_DIR = ROOT / "data" / "manifests"
LEGACY_ROOT = ROOT.parent / "VitalDB-Feature-Selection"
LEGACY_COMMIT = "9501b16a5c4db27f06fa0d0b252a3a75f633967f"
LEGACY_TREE = "60917f0b61ec1e6a195b9a648faa6466406aeda1"
LEGACY_ID_FILES = (
    "data/modeling/full/splits/train_cases.csv",
    "data/modeling/full/splits/val_cases.csv",
    "data/modeling/full/splits/test_cases.csv",
)
EXPECTED_TRACKS_SHA256 = "82b31333be20ca912ded93f46bf3ae42db281da40515a9945acc57749da9ffd0"
OFFICIAL_DATASET_OVERVIEW = (
    "https://vitaldb.net/dataset/?documentId="
    "13qqajnNZzkN7NZ9aXnaQ-47NWy7kx-a6gbrcEsi-gak"
    "&query=overview&sectionId=h.vcpgs1yemdb5"
)
OFFICIAL_SOURCE_SHA256 = "06c1779012389cd80d2a621abf38ad564b1446315ff79264bb1470fbf82db394"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 6A primary-signal acquisition")
    parser.add_argument("--stage", choices=("preflight", "full"), required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--raw-root", type=Path,
        default=ROOT / "data" / "raw" / "phase6a_primary_signals",
    )
    return parser.parse_args()


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(value)
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
        raise ValueError(f"refusing empty CSV {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _git_legacy(*args: str) -> str:
    safe = LEGACY_ROOT.resolve().as_posix()
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={safe}", "-C", str(LEGACY_ROOT), *args],
        text=True, stderr=subprocess.STDOUT,
    ).strip()


def _legacy_ids_and_provenance() -> tuple[set[int], dict[str, object], dict[str, object]]:
    before = {
        "head": _git_legacy("rev-parse", "HEAD"),
        "tree": _git_legacy("rev-parse", "HEAD^{tree}"),
        "status_short": _git_legacy("status", "--short").splitlines(),
    }
    if before["head"] != LEGACY_COMMIT or before["tree"] != LEGACY_TREE:
        raise RuntimeError("legacy repository HEAD or tree differs from approved read-only source")
    ids: list[int] = []
    files: list[dict[str, object]] = []
    for relative in LEGACY_ID_FILES:
        path = LEGACY_ROOT / relative
        rows = _read_csv(path)
        if not rows or set(rows[0]) != {"caseid"}:
            raise RuntimeError(f"legacy ID artifact has unexpected schema: {relative}")
        file_ids = [int(row["caseid"]) for row in rows]
        ids.extend(file_ids)
        files.append({"source_path": relative, "row_count": len(file_ids), "sha256": sha256_path(path)})
    unique = set(ids)
    if len(ids) != 98 or len(unique) != 98:
        raise RuntimeError(f"legacy actual-use artifact is not exactly 98 unique IDs: rows={len(ids)} unique={len(unique)}")
    combined = hashlib.sha256(("\n".join(map(str, sorted(unique))) + "\n").encode()).hexdigest()
    provenance = {
        "source_repository": "../VitalDB-Feature-Selection", "source_commit": LEGACY_COMMIT,
        "source_tree": LEGACY_TREE, "source_paths": files,
        "accessed_columns": ["caseid"], "total_rows": len(ids), "unique_caseids": len(unique),
        "combined_sorted_caseid_sha256": combined,
        "split_labels_copied_to_new_cohort": False, "results_or_metrics_accessed": False,
        "first_100_recomputed": False,
    }
    return unique, provenance, before


def _assert_legacy_unchanged(before: dict[str, object]) -> dict[str, object]:
    after = {
        "head": _git_legacy("rev-parse", "HEAD"),
        "tree": _git_legacy("rev-parse", "HEAD^{tree}"),
        "status_short": _git_legacy("status", "--short").splitlines(),
    }
    if after != before:
        raise RuntimeError("legacy repository changed during Phase 6A")
    return after


def _load_protocol_inputs() -> tuple[list[dict[str, object]], dict[str, object]]:
    phase5c = _read_csv(MANIFEST_DIR / "volatile_signal_case_manifest.csv")
    phase5d = json.loads((MANIFEST_DIR / "volatile_exposure_rule_sensitivity_summary.json").read_text(encoding="utf-8"))
    if phase5d.get("selected_exposure_definition") is not None:
        raise RuntimeError("Phase 5D sensitivity audit unexpectedly selected a definition")
    return phase5c, phase5d


def _run_downloads(
    tasks: list[PrimaryTask], *, raw_root: Path, workers: int, timeout_seconds: float,
    source_version: str, progress: ProgressLog,
) -> dict[str, dict[str, object]]:
    if workers < 1 or workers > 16:
        raise ValueError("workers must be between 1 and 16")
    state = threading.local()

    def execute(task: PrimaryTask) -> dict[str, object]:
        client = getattr(state, "client", None)
        if client is None:
            client = VitalDBOpenAPI(timeout_seconds=timeout_seconds)
            state.client = client
        return download_one_task(task, raw_root=raw_root, client=client, progress=progress, source_version=source_version)

    results: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(execute, task): task for task in tasks}
        total = len(futures)
        for completed, future in enumerate(as_completed(futures), start=1):
            task = futures[future]
            try:
                results[task.key] = future.result()
            except Exception as exc:
                results[task.key] = {
                    "caseid": task.caseid, "track_name": task.track_name, "tid": task.tids[0],
                    "status": "internal_failed", "attempt_count": int(progress.attempts[task.key]),
                    "raw_relative_path": None, "raw_byte_count": 0, "raw_sha256": None,
                    "source_version": source_version, "parsing": None,
                    "failure_type": type(exc).__name__, "failure_message": str(exc),
                }
            if completed % 100 == 0 or completed == total:
                print(f"primary acquisition progress {completed}/{total}", flush=True)
    return results


def _render_preflight(summary: dict[str, object]) -> str:
    return "\n".join([
        "# Phase 6A Primary-Signal Preflight", "",
        "This fixed-seed 25-case run is engineering evidence, not a scientific result.",
        "It selects no quality threshold and does not freeze a cohort.", "",
        f"- Seed: `{summary['seed']}`", f"- Selected cases: `{summary['selected_case_count']}`",
        f"- Present requests: `{summary['sample_present_request_count']}`",
        f"- Status counts: `{json.dumps(summary['sample_status_counts'], sort_keys=True)}`",
        f"- Estimated full bytes: `{summary['estimated_full_bytes']}`",
        f"- Free disk bytes: `{summary['disk_free_bytes']}`",
        f"- Required two-times bytes: `{summary['required_two_x_estimated_bytes']}`",
        f"- Disk gate: `{summary['disk_gate_passed']}`",
        f"- Operational gate: `{summary['operational_gate_passed']}`",
        f"- Full acquisition authorized: `{summary['full_download_authorized_by_gate']}`", "",
    ])


def _render_acquisition(summary: dict[str, object]) -> str:
    lines = [
        "# Phase 6A Primary Signal Acquisition Report", "",
        "This is a pre-quality acquisition cohort, not final eligibility or a frozen cohort.",
        "No signal-quality cutoff, interpolation, resampling, model, split, or downstream analysis was performed.", "",
        "## Accounting", "",
        f"- Protocol universe: `{summary['universe_case_count']}`",
        f"- Included for acquisition: `{summary['included_case_count']}`",
        f"- Excluded by the approved 10-second volatile rule: `{summary['volatile_excluded_count']}`",
        f"- Invalid anesthesia window: `{summary['invalid_window_count']}`",
        f"- Legacy-98 overlap: `{summary['legacy_overlap_count']}`",
        f"- Case×track rows: `{summary['case_track_row_count']}`", "",
        "## Download status", "",
    ]
    for name, counts in summary["track_status_counts"].items():
        lines.append(f"- `{name}`: `{json.dumps(counts, sort_keys=True)}`")
    lines.extend(["", "BIS/SQI is QC-only and is prohibited as a prediction feature or PPO state.", ""])
    return "\n".join(lines)


def _source_snapshot(
    *, stage: str, tracks: object, source_version: str, legacy: dict[str, object],
    legacy_before: dict[str, object], legacy_after: dict[str, object], removed: list[str],
    preflight: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "schema_version": 1, "phase": "6A_protocol_v1_1_primary_signal_acquisition",
        "stage": stage, "recorded_at": datetime.now(UTC).isoformat(),
        "client": {"implementation": "VitalDBOpenAPI", "version": __version__,
                   "api_base": API_BASE, "api_documentation": API_DOCUMENTATION},
        "track_list_endpoint": {"url": tracks.url, "fetched_at": tracks.fetched_at,
                                "row_count": len(tracks.rows), "byte_count": tracks.byte_count,
                                "elapsed_seconds": tracks.elapsed_seconds, "sha256": tracks.sha256},
        "source_version": source_version,
        "official_unit_source": {"url": OFFICIAL_DATASET_OVERVIEW,
                                 "document_name": "Dataset : VitalDB",
                                 "review_date": "2026-07-20", "sha256": OFFICIAL_SOURCE_SHA256},
        "legacy_overlap_provenance": legacy,
        "legacy_read_only_state_before": legacy_before,
        "legacy_read_only_state_after": legacy_after,
        "legacy_read_only_unchanged": legacy_before == legacy_after,
        "allowed_exact_tracks": list(PRIMARY_TRACK_NAMES),
        "bis_sqi_role": "qc_only_prohibited_prediction_feature_and_ppo_state",
        "rftn20_rftn50_merged": False, "rftn50_used": False,
        "removed_stale_partials": removed, "preflight_gate": preflight,
        "prohibited_execution": {
            "quality_threshold_selection": False, "coverage_or_gap_cutoff": False,
            "resampling": False, "interpolation": False, "smoothing": False, "clipping": False,
            "final_cohort_freeze": False, "split_creation": False, "cpce_reconstruction": False,
            "dose_calculation": False, "prediction": False, "feature_selection": False, "ppo": False,
        },
    }


def main() -> int:
    args = parse_args()
    raw_root = args.raw_root.resolve()
    removed = remove_stale_partials(raw_root)
    legacy_ids, legacy, legacy_before = _legacy_ids_and_provenance()
    phase5c_rows, phase5d = _load_protocol_inputs()
    cohort_rows = build_pre_quality_manifest(phase5c_rows, phase5d["case_records"], legacy_ids)
    cohort_path = MANIFEST_DIR / "pre_quality_acquisition_cohort.csv"
    _atomic_csv(cohort_path, cohort_rows)
    included = [int(row["caseid"]) for row in cohort_rows if row["included_for_primary_signal_acquisition"]]

    client = VitalDBOpenAPI(timeout_seconds=args.timeout_seconds)
    tracks = client.fetch_tracks()
    if tracks.sha256 != EXPECTED_TRACKS_SHA256:
        raise RuntimeError("/trks source drifted from Phase 5A/5B snapshot")
    prepared = prepare_source_rows(tracks.rows, source="tracks")
    if prepared.events:
        raise RuntimeError(f"/trks structural events observed: {len(prepared.events)}")
    tasks = build_tasks(included, prepared.rows)
    source_version = (
        f"vitaldb_open_api_client={__version__};tracks_sha256={tracks.sha256};"
        f"phase5d_summary_sha256={sha256_path(MANIFEST_DIR / 'volatile_exposure_rule_sensitivity_summary.json')};"
        f"legacy_caseid_sha256={legacy['combined_sorted_caseid_sha256']}"
    )
    progress_path = raw_root / "download_attempts.jsonl"
    progress = ProgressLog(progress_path)
    preflight_path = MANIFEST_DIR / "primary_signal_preflight_summary.json"
    preflight_report = ROOT / "docs" / "primary_signal_preflight_report.md"
    source_path = MANIFEST_DIR / "primary_signal_source_snapshot.json"

    if args.stage == "preflight":
        selected = fixed_seed_preflight_caseids(included)
        selected_set = set(selected)
        selected_tasks = [task for task in tasks if task.caseid in selected_set and len(task.tids) == 1]
        started = time.perf_counter()
        results = _run_downloads(selected_tasks, raw_root=raw_root, workers=args.workers,
                                 timeout_seconds=args.timeout_seconds, source_version=source_version,
                                 progress=progress)
        elapsed = time.perf_counter() - started
        preflight = build_preflight_summary(
            selected, tasks, results, disk_free_bytes=shutil.disk_usage(raw_root.parent).free,
            elapsed_seconds=elapsed, source_version=source_version,
        )
        atomic_json(preflight_path, preflight)
        _atomic_text(preflight_report, _render_preflight(preflight))
        legacy_after = _assert_legacy_unchanged(legacy_before)
        atomic_json(source_path, _source_snapshot(
            stage="preflight", tracks=tracks, source_version=source_version, legacy=legacy,
            legacy_before=legacy_before, legacy_after=legacy_after, removed=removed, preflight=preflight,
        ))
        assert_no_partials(raw_root)
        print(json.dumps(preflight, ensure_ascii=False, sort_keys=True))
        return 0

    if not preflight_path.is_file():
        raise RuntimeError("full stage requires preflight summary")
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if preflight.get("source_version") != source_version:
        raise RuntimeError("preflight source version does not match full-stage inputs")
    if preflight.get("full_download_authorized_by_gate") is not True:
        raise RuntimeError("preflight gate did not authorize full acquisition")
    downloadable = [task for task in tasks if len(task.tids) == 1]
    results = _run_downloads(downloadable, raw_root=raw_root, workers=args.workers,
                             timeout_seconds=args.timeout_seconds, source_version=source_version,
                             progress=progress)
    rows: list[dict[str, object]] = []
    for task in tasks:
        metadata = results.get(task.key)
        if metadata is None and len(task.tids) == 1:
            metadata = load_verified_metadata(raw_root, task)
        rows.append(manifest_row(task, metadata, source_version=source_version))
    expected_rows = len(included) * len(PRIMARY_TRACKS)
    if len(rows) != expected_rows or len({(row["caseid"], row["track_name"]) for row in rows}) != expected_rows:
        raise RuntimeError("primary case×track manifest has duplicates or omissions")
    manifest_path = MANIFEST_DIR / "primary_signal_download_manifest.csv"
    _atomic_csv(manifest_path, rows)
    failures = [row for row in rows if row["download_status"] not in {"complete", "track_absent"}]
    failure_path = MANIFEST_DIR / "primary_signal_failures.jsonl"
    _atomic_text(failure_path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in failures))
    checksum_rows = [
        {"caseid": row["caseid"], "track_name": row["track_name"],
         "raw_relative_path": row["raw_relative_path"], "raw_byte_count": row["raw_byte_count"],
         "raw_sha256": row["raw_sha256"], "checksum_verified": True}
        for row in rows if row["download_status"] == "complete"
    ]
    checksum_path = MANIFEST_DIR / "primary_signal_checksum_manifest.csv"
    _atomic_csv(checksum_path, checksum_rows)
    track_status: dict[str, dict[str, int]] = {}
    for name in PRIMARY_TRACK_NAMES:
        track_status[name] = dict(sorted(Counter(str(row["download_status"]) for row in rows if row["track_name"] == name).items()))
    summary = {
        "phase": "6A_protocol_v1_1_primary_signal_acquisition",
        "generated_at": datetime.now(UTC).isoformat(), "universe_case_count": EXPECTED_UNIVERSE_COUNT,
        "included_case_count": len(included),
        "volatile_excluded_count": sum(bool(row["volatile_positive_run_ge_10s"]) for row in cohort_rows),
        "invalid_window_count": sum(bool(row["invalid_anesthesia_window"]) for row in cohort_rows),
        "legacy_overlap_count": sum(bool(row["legacy_98_overlap"]) for row in cohort_rows),
        "case_track_row_count": len(rows), "track_status_counts": track_status,
        "failure_row_count": len(failures), "checksum_verified_raw_file_count": len(checksum_rows),
        "checksum_verified_raw_bytes": sum(int(row["raw_byte_count"]) for row in checksum_rows),
        "primary_volatile_definition": PHASE5D_PRIMARY_DEFINITION,
        "pre_quality_only": True, "final_cohort_frozen": False, "quality_threshold_selected": False,
        "bis_sqi_prediction_feature_allowed": False, "bis_sqi_ppo_state_allowed": False,
        "source_version": source_version, "preflight": preflight,
    }
    summary_path = MANIFEST_DIR / "primary_signal_acquisition_summary.json"
    report_path = ROOT / "docs" / "primary_signal_acquisition_report.md"
    atomic_json(summary_path, summary)
    _atomic_text(report_path, _render_acquisition(summary))
    legacy_after = _assert_legacy_unchanged(legacy_before)
    atomic_json(source_path, _source_snapshot(
        stage="full", tracks=tracks, source_version=source_version, legacy=legacy,
        legacy_before=legacy_before, legacy_after=legacy_after, removed=removed, preflight=preflight,
    ))
    assert_no_partials(raw_root)
    artifact_paths = (cohort_path, preflight_path, preflight_report, manifest_path, failure_path,
                      checksum_path, summary_path, source_path, report_path)
    atomic_json(MANIFEST_DIR / "primary_signal_artifact_checksums.json", {
        path.relative_to(ROOT).as_posix(): sha256_path(path) for path in artifact_paths
    })
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

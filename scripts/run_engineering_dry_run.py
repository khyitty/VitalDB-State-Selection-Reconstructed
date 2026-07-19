"""Run the fixed seed, random 25-case engineering dry run only."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.dry_run import (  # noqa: E402
    DRY_RUN_SAMPLE_SIZE,
    DRY_RUN_SEED,
    REQUIRED_CONCEPTS,
    apply_signal_results,
    build_dry_run_metadata_records,
)
from vitaldb_state_selection.cohort.guards import (  # noqa: E402
    assert_manifest_complete,
    fixed_seed_random_sample,
    normalize_caseid,
)
from vitaldb_state_selection.cohort.track_inventory import AliasRegistry  # noqa: E402
from vitaldb_state_selection.data.downloader import (  # noqa: E402
    DownloadManifestStore,
    DownloadOrchestrator,
    TrackRequest,
)
from vitaldb_state_selection.data.vitaldb_api import VitalDBOpenAPI  # noqa: E402
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    write_csv_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fixed seed random 25-case engineering dry run; not a scientific analysis."
    )
    parser.add_argument("--with-signals", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "manifests" / f"engineering_dry_run_seed_{DRY_RUN_SEED}",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=ROOT / "data" / "raw" / f"engineering_dry_run_seed_{DRY_RUN_SEED}",
    )
    return parser.parse_args()


def _percentile_90(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(0.9 * (len(ordered) - 1))))
    return float(ordered[index])


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    client = VitalDBOpenAPI(timeout_seconds=args.timeout_seconds)
    started = time.perf_counter()
    cases = client.fetch_cases()
    tracks = client.fetch_tracks()
    metadata_fetch_seconds = time.perf_counter() - started
    source_caseids = [normalize_caseid(row.get("caseid")) for row in cases.rows]
    assert_manifest_complete(source_caseids)
    sample_caseids = fixed_seed_random_sample(
        source_caseids, seed=DRY_RUN_SEED, sample_size=DRY_RUN_SAMPLE_SIZE
    )
    registry = AliasRegistry.from_yaml(ROOT / "configs" / "track_aliases.yaml")
    source_version = f"vitaldb_open_api;cases_sha256={cases.sha256};tracks_sha256={tracks.sha256}"
    records, tracks_by_case = build_dry_run_metadata_records(
        sample_caseids,
        cases.rows,
        tracks.rows,
        registry=registry,
        source_version=source_version,
    )
    signal_seconds = 0.0
    download_rows: list[dict[str, object]] = []
    failure_log = args.output_dir / "download_failures.jsonl"
    failure_log.touch(exist_ok=True)
    if args.with_signals:
        requests_: list[TrackRequest] = []
        clinical_by_case = {
            normalize_caseid(row.get("caseid")): row
            for row in cases.rows
            if normalize_caseid(row.get("caseid")) in set(sample_caseids)
        }
        for caseid in sample_caseids:
            exact_tracks = {
                concept: items[0]
                for concept, items in tracks_by_case.get(caseid, {}).items()
                if concept in REQUIRED_CONCEPTS and len(items) == 1
            }
            requests_.append(TrackRequest(caseid, clinical_by_case.get(caseid, {}), exact_tracks))
        download_schema = load_schema(ROOT / "schemas" / "download_manifest.schema.json")
        store = DownloadManifestStore(args.output_dir / "download_manifest.csv", download_schema)
        orchestrator = DownloadOrchestrator(
            client=client,
            raw_root=args.raw_root,
            manifest=store,
            failure_log=failure_log,
            source_version=source_version,
        )
        signal_started = time.perf_counter()
        download_rows = orchestrator.run(requests_)
        signal_seconds = time.perf_counter() - signal_started
        records = apply_signal_results(records, download_rows)
    dry_run_schema = load_schema(ROOT / "schemas" / "engineering_dry_run.schema.json")
    manifest_path = args.output_dir / "dry_run_manifest.csv"
    write_csv_manifest(manifest_path, records, dry_run_schema)
    complete = [row for row in download_rows if row["status"] == "complete"]
    failed = [row for row in download_rows if row["status"] != "complete"]
    completed_byte_counts = [float(row["bytes_downloaded"]) for row in complete]
    completed_durations = [
        (
            datetime.fromisoformat(str(row["completed_at"]))
            - datetime.fromisoformat(str(row["started_at"]))
        ).total_seconds()
        for row in complete
    ]
    attempt_timestamps = [
        datetime.fromisoformat(str(row[field]))
        for row in download_rows
        for field in ("started_at", "completed_at")
        if row[field]
    ]
    attempt_span_seconds = (
        (max(attempt_timestamps) - min(attempt_timestamps)).total_seconds()
        if attempt_timestamps
        else None
    )
    failure_types = Counter(str(row["failure_type"]) for row in failed)
    summary = {
        "dry_run_label": "engineering_only_not_a_scientific_result",
        "scientific_result": False,
        "sample_seed": DRY_RUN_SEED,
        "sample_size": DRY_RUN_SAMPLE_SIZE,
        "sampling_method": "fixed_seed_random_without_replacement",
        "sample_caseids": sample_caseids,
        "is_first_25": sample_caseids == list(range(1, 26)),
        "source_case_count": len(source_caseids),
        "source_case_min": min(source_caseids),
        "source_case_max": max(source_caseids),
        "cases_snapshot": {
            "sha256": cases.sha256,
            "bytes": cases.byte_count,
            "elapsed_seconds": cases.elapsed_seconds,
        },
        "tracks_snapshot": {
            "sha256": tracks.sha256,
            "bytes": tracks.byte_count,
            "elapsed_seconds": tracks.elapsed_seconds,
        },
        "metadata_fetch_seconds": metadata_fetch_seconds,
        "metadata_failed_count": sum(record["metadata_status"] == "failed" for record in records),
        "signal_requested": bool(args.with_signals),
        "signal_complete_count": len(complete),
        "signal_failed_count": len(failed),
        "signal_runtime_seconds": signal_seconds,
        "signal_recorded_attempt_span_seconds": attempt_span_seconds,
        "signal_total_bytes": sum(int(row["bytes_downloaded"]) for row in download_rows),
        "signal_median_bytes_per_completed_case": (
            statistics.median(completed_byte_counts) if completed_byte_counts else None
        ),
        "signal_p90_bytes_per_completed_case": _percentile_90(completed_byte_counts),
        "signal_median_seconds_per_completed_case": (
            statistics.median(completed_durations) if completed_durations else None
        ),
        "signal_p90_seconds_per_completed_case": _percentile_90(completed_durations),
        "signal_failure_rate": len(failed) / len(download_rows) if download_rows else None,
        "signal_failure_type_counts": dict(sorted(failure_types.items())),
        "signal_retry_case_count": sum(
            int(row["attempt_count"]) > 1 for row in download_rows
        ),
        "signal_checksum_case_count": sum(bool(row["checksums"]) for row in complete),
        "production_estimate_status": "not_calculated_candidate_count_and_units_pending",
        "quality_thresholds_finalized": False,
        "cohort_frozen": False,
        "split_created": False,
        "prediction_run": False,
        "feature_selection_run": False,
        "cpce_reconstruction_run": False,
        "ppo_run": False,
        "commands": [
            "python -m unittest discover -s tests -v",
            "python scripts/run_engineering_dry_run.py",
            "python scripts/run_engineering_dry_run.py --with-signals",
        ],
    }
    summary_path = args.output_dir / "dry_run_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    inventory = {
        "dry_run_manifest.csv": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "dry_run_summary.json": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "download_failures.jsonl": hashlib.sha256(failure_log.read_bytes()).hexdigest(),
    }
    download_manifest = args.output_dir / "download_manifest.csv"
    if download_manifest.exists():
        inventory["download_manifest.csv"] = hashlib.sha256(
            download_manifest.read_bytes()
        ).hexdigest()
    (args.output_dir / "artifact_checksums.json").write_text(
        json.dumps(inventory, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    # Case-level failures are an expected dry-run observation and remain in manifests.
    # Reaching this point means the 25-case accounting and artifact writes completed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

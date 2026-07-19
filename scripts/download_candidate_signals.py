"""Download every authorized metadata-stage candidate with no case limit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.guards import assert_manifest_complete  # noqa: E402
from vitaldb_state_selection.cohort.track_inventory import (  # noqa: E402
    AliasRegistry,
    index_track_rows,
)
from vitaldb_state_selection.data.downloader import (  # noqa: E402
    DownloadManifestStore,
    DownloadOrchestrator,
    TrackRequest,
)
from vitaldb_state_selection.data.vitaldb_api import VitalDBOpenAPI  # noqa: E402
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    read_csv_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download all authorized candidates; partial/first-N execution is forbidden."
    )
    parser.add_argument("--eligibility-manifest", type=Path, required=True)
    parser.add_argument("--authorization-file", type=Path, required=True)
    parser.add_argument(
        "--aliases", type=Path, default=ROOT / "configs" / "track_aliases.yaml"
    )
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument(
        "--download-manifest",
        type=Path,
        default=ROOT / "data" / "manifests" / "download_manifest.csv",
    )
    parser.add_argument(
        "--failure-log",
        type=Path,
        default=ROOT / "data" / "manifests" / "download_failures.jsonl",
    )
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def _validate_authorization(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "scope": "full_candidate_signal_download",
        "approved": True,
        "quality_thresholds_finalized": True,
        "track_units_reviewed": True,
    }
    if any(payload.get(key) != value for key, value in required.items()):
        raise PermissionError(
            "full signal download requires explicit post-audit human authorization"
        )


def main() -> int:
    args = parse_args()
    _validate_authorization(args.authorization_file)
    eligibility_schema = load_schema(ROOT / "schemas" / "eligibility_manifest.schema.json")
    records = read_csv_manifest(args.eligibility_manifest, eligibility_schema)
    assert_manifest_complete([record["caseid"] for record in records])
    candidates = [record for record in records if record["candidate_at_metadata_stage"] is True]
    if not candidates:
        raise RuntimeError("no human-authorized metadata-stage candidates are present")
    registry = AliasRegistry.from_yaml(args.aliases)
    if not registry.units_validated(("propofol_rate", "remifentanil_rate")):
        raise PermissionError("drug-rate units remain pending human review in track_aliases.yaml")
    client = VitalDBOpenAPI(timeout_seconds=args.timeout_seconds)
    track_snapshot = client.fetch_tracks()
    indexed = index_track_rows(track_snapshot.rows, registry)
    requests_: list[TrackRequest] = []
    for record in candidates:
        caseid = int(record["caseid"])
        exact_tracks = {
            concept: items[0]
            for concept, items in indexed.get(caseid, {}).items()
            if len(items) == 1
        }
        requests_.append(TrackRequest(caseid, record, exact_tracks))
    download_schema = load_schema(ROOT / "schemas" / "download_manifest.schema.json")
    store = DownloadManifestStore(args.download_manifest, download_schema)
    orchestrator = DownloadOrchestrator(
        client=client,
        raw_root=args.raw_root,
        manifest=store,
        failure_log=args.failure_log,
        source_version=f"vitaldb_open_api;tracks_sha256={track_snapshot.sha256}",
    )
    results = orchestrator.run(requests_)
    failures = [row for row in results if row["status"] != "complete"]
    print(json.dumps({"requested": len(results), "failed": len(failures)}, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

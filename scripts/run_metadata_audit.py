"""Run the full 1–6388 metadata and exact-track inventory audit."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.eligibility import (  # noqa: E402
    build_eligibility_records,
    load_audit_config,
    summarize_records,
)
from vitaldb_state_selection.cohort.track_inventory import AliasRegistry  # noqa: E402
from vitaldb_state_selection.data.vitaldb_api import VitalDBOpenAPI  # noqa: E402
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    write_csv_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Account for every VitalDB case in an outcome-blind metadata manifest."
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
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_audit_config(args.config)
    registry = AliasRegistry.from_yaml(args.aliases)
    client = VitalDBOpenAPI(timeout_seconds=args.timeout_seconds)
    query_timestamp = datetime.now(UTC).isoformat()
    failures: list[str] = []
    cases = None
    tracks = None
    try:
        cases = client.fetch_cases()
    except Exception as exc:  # failure becomes 6388 explicit manifest records
        failures.append(f"cases_query:{type(exc).__name__}:{exc}")
    try:
        tracks = client.fetch_tracks()
    except Exception as exc:  # failure becomes 6388 explicit manifest records
        failures.append(f"tracks_query:{type(exc).__name__}:{exc}")
    version_parts = ["vitaldb_open_api"]
    if cases is not None:
        version_parts.append(f"cases_sha256={cases.sha256}")
    if tracks is not None:
        version_parts.append(f"tracks_sha256={tracks.sha256}")
    records = build_eligibility_records(
        cases.rows if cases is not None else [],
        tracks.rows if tracks is not None else [],
        config=config,
        registry=registry,
        source_version=";".join(version_parts),
        query_timestamp=query_timestamp,
        clinical_query_available=cases is not None,
        track_query_available=tracks is not None,
        source_failures=failures,
        legacy_caseids=None,
    )
    schema = load_schema(ROOT / "schemas" / "eligibility_manifest.schema.json")
    write_csv_manifest(args.output, records, schema)
    summary = summarize_records(records)
    summary.update(
        {
            "audit_name": config["audit_name"],
            "query_timestamp": query_timestamp,
            "source_failures": failures,
            "legacy_overlap_evaluated": False,
            "tiva_classification_finalized": False,
            "volatile_aliases_finalized": False,
        }
    )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

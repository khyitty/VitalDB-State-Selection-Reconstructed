"""Freeze public-safe Phase 8E aggregate and statistical result artifacts."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.publication.final_results import (  # noqa: E402
    BOOTSTRAP_REPLICATES,
    MODEL_SHA256,
    PERMUTATION_REPLICATES,
    build_aggregate,
    canonical_json_bytes,
    read_private_rows,
    sha256_bytes,
    verify_model_files,
)
from vitaldb_state_selection.publication.phase8f_renderer import validate_aggregate  # noqa: E402


def atomic_write(path: Path, payload: bytes) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-case-results", type=Path, required=True)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--aggregate-output", type=Path, required=True)
    parser.add_argument("--statistics-output", type=Path, required=True)
    parser.add_argument("--integrity-output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    observed_models = verify_model_files(args.models_root)
    rows, private_sha = read_private_rows(args.private_case_results)
    aggregate, statistics = build_aggregate(rows)
    schema = json.loads((ROOT / "schemas/phase8f_aggregate_results.schema.json").read_text(encoding="utf-8"))
    validate_aggregate(aggregate, schema)
    aggregate_bytes = canonical_json_bytes(aggregate)
    statistics_bytes = canonical_json_bytes(statistics)
    integrity = {
        "schema_version": "phase8e-final-results-integrity-v1",
        "private_case_results_sha256": private_sha,
        "private_case_results_published": False,
        "aggregate_sha256": sha256_bytes(aggregate_bytes),
        "statistics_sha256": sha256_bytes(statistics_bytes),
        "model_sha256": observed_models,
        "case_condition_rows": 1960,
        "completed_per_condition": 490,
        "failed_per_condition": 0,
        "silent_exclusion_count": 0,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "permutation_replicates": PERMUTATION_REPLICATES,
        "public_case_level_row_count": 0,
        "public_event_level_row_count": 0,
        "results_interpreted": False,
        "best_condition_selected": False,
    }
    integrity_bytes = canonical_json_bytes(integrity)
    outputs = {
        args.aggregate_output: aggregate_bytes,
        args.statistics_output: statistics_bytes,
        args.integrity_output: integrity_bytes,
    }
    if args.verify_only:
        mismatched = [str(path) for path, payload in outputs.items() if not path.is_file() or path.read_bytes() != payload]
        if mismatched:
            raise RuntimeError(f"frozen final-result artifact mismatch: {mismatched}")
        print(json.dumps({"verified": True, "writes_performed": 0, **integrity}, sort_keys=True))
        return 0
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"final-result output already exists; overwrite refused: {existing}")
    for path, payload in outputs.items():
        atomic_write(path, payload)
    print(json.dumps({"verified": True, "writes_performed": len(outputs), **integrity}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

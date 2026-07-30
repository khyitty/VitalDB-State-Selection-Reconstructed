"""Freeze public-safe 12-model summaries from canonical Phase 8E/8G results.

Scope notice: this produces a Phase 8G seed-43/44 replication-extension
artifact. It is outside the confirmatory ICTC 2026 manuscript, which reports
seed 42 only (see README.md#ictc-2026-paper-scope). Write outputs under
data/manifests/, not paper/generated/, so the manuscript-facing directory
never mixes seeds.
"""

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
    build_multiseed_summary,
    canonical_json_bytes,
    read_private_rows,
    sha256_bytes,
)
from vitaldb_state_selection.rl_integration.final_evaluation import (  # noqa: E402
    CONDITIONS,
    evaluation_unit_paths,
    verify_four_models,
)


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".partial", dir=path.parent
    )
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


def read_seed_rows(seed: int, source: Path) -> tuple[list[dict[str, object]], list[str]]:
    if seed == 42:
        rows, digest = read_private_rows(source)
        return rows, [digest]
    rows: list[dict[str, object]] = []
    digests: list[str] = []
    for condition in CONDITIONS:
        path = evaluation_unit_paths(source, condition, seed)["result"]
        condition_rows, digest = read_private_rows(path)
        rows.extend(condition_rows)
        digests.append(digest)
    return rows, digests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--seed42-results", type=Path, required=True)
    parser.add_argument("--seed43-root", type=Path, required=True)
    parser.add_argument("--seed44-root", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--integrity-output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    sources = {
        42: args.seed42_results,
        43: args.seed43_root,
        44: args.seed44_root,
    }
    rows_by_seed: dict[int, list[dict[str, object]]] = {}
    source_sha256: dict[str, list[str]] = {}
    model_sha256_by_seed: dict[int, dict[str, str]] = {}
    output_root_sha256_by_seed: dict[str, dict[str, str]] = {}
    for seed in (42, 43, 44):
        rows, digests = read_seed_rows(seed, sources[seed])
        rows_by_seed[seed] = rows
        source_sha256[str(seed)] = digests
        models = verify_four_models(args.models_root, seed=seed)
        model_sha256_by_seed[seed] = {
            model.condition_id: model.final_model_sha256 for model in models
        }
        output_root_sha256_by_seed[str(seed)] = {
            model.condition_id: model.output_root_sha256 for model in models
        }
    summary = build_multiseed_summary(
        rows_by_seed,
        model_sha256_by_seed=model_sha256_by_seed,
    )
    summary_bytes = canonical_json_bytes(summary)
    integrity = {
        "all_prespecified_seeds_included": True,
        "case_condition_seed_rows": 490 * 4 * 3,
        "evaluation_seed": 42,
        "model_seeds": [42, 43, 44],
        "output_root_sha256_by_seed": output_root_sha256_by_seed,
        "private_case_results_published": False,
        "private_result_sha256_by_seed": source_sha256,
        "public_case_level_row_count": 0,
        "public_event_level_row_count": 0,
        "schema_version": "phase8g-multiseed-results-integrity-v1",
        "summary_sha256": sha256_bytes(summary_bytes),
    }
    integrity_bytes = canonical_json_bytes(integrity)
    outputs = {
        args.summary_output: summary_bytes,
        args.integrity_output: integrity_bytes,
    }
    if args.verify_only:
        mismatched = [
            str(path)
            for path, payload in outputs.items()
            if not path.is_file() or path.read_bytes() != payload
        ]
        if mismatched:
            raise RuntimeError(f"multi-seed result artifact mismatch: {mismatched}")
        print(json.dumps({"verified": True, "writes_performed": 0, **integrity}))
        return 0
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"multi-seed output already exists; overwrite refused: {existing}")
    for path, payload in outputs.items():
        atomic_write(path, payload)
    print(json.dumps({"verified": True, "writes_performed": len(outputs), **integrity}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

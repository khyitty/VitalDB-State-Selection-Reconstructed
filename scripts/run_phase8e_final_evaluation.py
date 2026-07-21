"""Verify Phase 8E final-evaluation prerequisites; execute only with --execute."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.rl_integration.final_evaluation import (  # noqa: E402
    SEED,
    TRAINING_IMPLEMENTATION_SHA,
    execute_evaluation,
    verify_evaluation_inputs,
    verify_four_models,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--test-runtime-root", type=Path, required=True)
    parser.add_argument("--expected-training-sha", default=TRAINING_IMPLEMENTATION_SHA)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--verify-only", action="store_true", help="Explicit alias for the safe default")
    parser.add_argument("--execute", action="store_true", help="Explicitly authorize deterministic policy episodes")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if args.verify_only and args.execute:
        parser.error("--verify-only and --execute are mutually exclusive")
    if args.seed != SEED:
        parser.error("Phase 8E evaluation seed must be 42")
    inputs = verify_evaluation_inputs(ROOT, args.test_runtime_root)
    if not args.execute:
        models = verify_four_models(args.models_root, expected_training_sha=args.expected_training_sha)
        print(json.dumps({
            **inputs,
            "actual_model_episode_count": 0,
            "models_loaded": False,
            "verified_final_conditions": [row.condition_id for row in models],
            "verify_only": True,
        }, indent=2, sort_keys=True))
        return 0
    if args.output_root is None:
        parser.error("--execute requires --output-root")
    result = execute_evaluation(
        repository_root=ROOT,
        models_root=args.models_root,
        test_runtime_root=args.test_runtime_root,
        output_root=args.output_root,
        expected_training_sha=args.expected_training_sha,
        seed=args.seed,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

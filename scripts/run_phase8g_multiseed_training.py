"""Run, preflight, or verify the Phase 8G seed-43/44 training extension."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.train_runtime_inputs import (  # noqa: E402
    PRIVATE_ROOT_RELATIVE as PHASE8C_PRIVATE_ROOT_RELATIVE,
    TrainRuntimeInputStore,
    load_scaler_registry,
)
from vitaldb_state_selection.rl_integration.multiseed_training import (  # noqa: E402
    ALLOWED_SEEDS,
    DEFAULT_OUTPUT_ROOT_RELATIVE,
    FINAL_TOTAL_TIMESTEPS,
    SCALER_REGISTRY_RELATIVE,
    SHARDS,
    MultiSeedTrainingError,
    run_condition_preflight,
    train_condition,
    validate_output_root,
    verify_legacy_seed42_outputs,
    verify_private_outputs,
    verify_repository_gate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument(
        "--condition", choices=tuple(item for rows in SHARDS.values() for item in rows)
    )
    selector.add_argument("--shard", choices=tuple(SHARDS))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--total-timesteps", type=int, required=True)
    parser.add_argument("--expected-git-sha", required=True)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT_RELATIVE.as_posix())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--legacy-verify-seed42", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def selected_conditions(args: argparse.Namespace) -> tuple[str, ...]:
    return (args.condition,) if args.condition is not None else SHARDS[args.shard]


def main() -> int:
    args = parse_args()
    if args.seed not in ALLOWED_SEEDS:
        raise MultiSeedTrainingError("Phase 8G accepts exactly seeds 43 and 44")
    if args.total_timesteps != FINAL_TOTAL_TIMESTEPS:
        raise MultiSeedTrainingError(
            "Phase 8G accepts exactly 1,000,000 timesteps"
        )
    output = Path(args.output_root)
    if not output.is_absolute():
        output = ROOT / output
    output = validate_output_root(ROOT, output)
    gate = verify_repository_gate(
        ROOT, expected_git_sha=args.expected_git_sha, output_root=output
    )
    conditions = selected_conditions(args)
    if args.legacy_verify_seed42:
        result = verify_legacy_seed42_outputs(
            repository_root=ROOT, output_root=output, conditions=conditions
        )
    elif args.verify_only:
        result = verify_private_outputs(
            repository_root=ROOT,
            output_root=output,
            expected_git_sha=args.expected_git_sha,
            conditions=conditions,
            seed=args.seed,
        )
    else:
        store = TrainRuntimeInputStore(ROOT / PHASE8C_PRIVATE_ROOT_RELATIVE, ROOT)
        scalers = load_scaler_registry(ROOT / SCALER_REGISTRY_RELATIVE)
        if args.preflight:
            result = {
                "conditions": [
                    run_condition_preflight(
                        condition_id=condition,
                        store=store,
                        scaler=scalers["S0" if condition.endswith("S0") else "S1"],
                        seed=args.seed,
                    )
                    for condition in conditions
                ],
                "model_or_checkpoint_persisted": False,
            }
        else:
            result = {
                "conditions": [
                    train_condition(
                        output_root=output,
                        expected_git_sha=args.expected_git_sha,
                        condition_id=condition,
                        store=store,
                        scaler=scalers["S0" if condition.endswith("S0") else "S1"],
                        resume=args.resume,
                        seed=args.seed,
                        total_timesteps=args.total_timesteps,
                    )
                    for condition in conditions
                ]
            }
    print(json.dumps({"gate": gate, "result": result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

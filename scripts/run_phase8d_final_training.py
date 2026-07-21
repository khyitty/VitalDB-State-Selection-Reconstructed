"""Run or verify the private Phase 8D final PPO training shards."""

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
from vitaldb_state_selection.rl_integration.final_training import (  # noqa: E402
    CANONICAL_PPO_SEED,
    DEFAULT_OUTPUT_ROOT_RELATIVE,
    FINAL_TOTAL_TIMESTEPS,
    SCALER_REGISTRY_RELATIVE,
    SHARDS,
    FinalTrainingError,
    train_condition,
    validate_output_root,
    verify_private_outputs,
    verify_repository_gate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--condition", choices=tuple(item for rows in SHARDS.values() for item in rows))
    selector.add_argument("--shard", choices=tuple(SHARDS))
    parser.add_argument("--total-timesteps", type=int, default=FINAL_TOTAL_TIMESTEPS)
    parser.add_argument("--seed", type=int, default=CANONICAL_PPO_SEED)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--expected-git-sha", required=True)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT_RELATIVE.as_posix())
    return parser.parse_args()


def selected_conditions(args: argparse.Namespace) -> tuple[str, ...]:
    if args.condition is not None:
        return (args.condition,)
    return SHARDS[args.shard]


def main() -> int:
    args = parse_args()
    if args.seed != CANONICAL_PPO_SEED:
        raise FinalTrainingError("Phase 8D rejects every seed except 42")
    if args.total_timesteps != FINAL_TOTAL_TIMESTEPS:
        raise FinalTrainingError("Phase 8D rejects every budget except 1,000,000 timesteps")
    output = Path(args.output_root)
    if not output.is_absolute():
        output = ROOT / output
    output = validate_output_root(ROOT, output)
    gate = verify_repository_gate(ROOT, expected_git_sha=args.expected_git_sha, output_root=output)
    conditions = selected_conditions(args)
    if args.condition is not None:
        containing = [shard for shard, rows in SHARDS.items() if args.condition in rows]
        if len(containing) != 1:
            raise FinalTrainingError("condition has no unique shard assignment")
    if args.verify_only:
        result = verify_private_outputs(
            repository_root=ROOT,
            output_root=output,
            expected_git_sha=args.expected_git_sha,
            conditions=conditions,
        )
        print(json.dumps({"gate": gate, "verification": result}, indent=2, sort_keys=True))
        return 0
    store = TrainRuntimeInputStore(ROOT / PHASE8C_PRIVATE_ROOT_RELATIVE, ROOT)
    scalers = load_scaler_registry(ROOT / SCALER_REGISTRY_RELATIVE)
    results = []
    for condition in conditions:
        state_id = "S0" if condition.endswith("S0") else "S1"
        results.append(train_condition(
            repository_root=ROOT,
            output_root=output,
            expected_git_sha=args.expected_git_sha,
            condition_id=condition,
            store=store,
            scaler=scalers[state_id],
            resume=args.resume,
            total_timesteps=args.total_timesteps,
            seed=args.seed,
        ))
    print(json.dumps({"conditions": conditions, "results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

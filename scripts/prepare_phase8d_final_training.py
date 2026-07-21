"""Generate aggregate-only Phase 8D protocol, sampling, and 1,024-step preflight artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MANIFESTS = ROOT / "data/manifests"

from vitaldb_state_selection.cohort.train_runtime_inputs import (  # noqa: E402
    PHASE8B_EXPECTED_ROOT_SHA256,
    PRIVATE_ROOT_RELATIVE as PHASE8C_PRIVATE_ROOT_RELATIVE,
    TrainRuntimeInputStore,
    atomic_json,
    load_scaler_registry,
    sha256_path,
)
from vitaldb_state_selection.rl_integration.final_training import (  # noqa: E402
    CANONICAL_PPO_SEED,
    CHECKPOINT_INTERVAL,
    FINAL_CONFIG_RELATIVE,
    FINAL_TOTAL_TIMESTEPS,
    PHASE8C_EXPECTED_ROOT_SHA256,
    SCALER_REGISTRY_RELATIVE,
    SEQUENCE_CHECKSUM_EPISODES,
    SHARDS,
    episode_sequence_sha256,
    resolved_final_configuration,
    run_condition_preflight,
    train_universe_sha256,
)


PUBLIC_OUTPUTS = (
    MANIFESTS / "phase8d_final_ppo_config.json",
    MANIFESTS / "phase8d_training_protocol.json",
    MANIFESTS / "phase8d_shard_definition.json",
    MANIFESTS / "phase8d_sampling_summary.json",
    MANIFESTS / "phase8d_preflight_summary.json",
    MANIFESTS / "phase8d_source_snapshot.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def legacy_state() -> dict[str, object]:
    legacy = (ROOT / "../VitalDB-Feature-Selection").resolve()
    safe = f"safe.directory={legacy.as_posix()}"
    return {
        "head": subprocess.check_output(["git", "-c", safe, "-C", str(legacy), "rev-parse", "HEAD"], text=True).strip(),
        "tree": subprocess.check_output(["git", "-c", safe, "-C", str(legacy), "rev-parse", "HEAD^{tree}"], text=True).strip(),
        "status": subprocess.check_output(["git", "-c", safe, "-C", str(legacy), "status", "--short"], text=True).splitlines(),
    }


def build_outputs(*, run_preflight: bool) -> dict[Path, object]:
    store = TrainRuntimeInputStore(ROOT / PHASE8C_PRIVATE_ROOT_RELATIVE, ROOT)
    scalers = load_scaler_registry(ROOT / SCALER_REGISTRY_RELATIVE)
    caseids = tuple(row["caseid"] for row in store.rows)
    universe_sha = train_universe_sha256(caseids)
    sequence_sha = episode_sequence_sha256(caseids)
    configuration = resolved_final_configuration()
    protocol = {
        "phase": "Phase 8D",
        "status": "training_infrastructure_only_until_all_four_final_checkpoints_exist",
        "conditions": [item for rows in SHARDS.values() for item in rows],
        "seed": CANONICAL_PPO_SEED,
        "total_environment_timesteps_per_condition": FINAL_TOTAL_TIMESTEPS,
        "checkpoint_timesteps": list(range(CHECKPOINT_INTERVAL, FINAL_TOTAL_TIMESTEPS + 1, CHECKPOINT_INTERVAL)),
        "same_hyperparameters_all_conditions": True,
        "same_train_case_sequence_all_conditions": True,
        "same_patient_remifentanil_universe_all_conditions": True,
        "state_dimension_difference_only": {"S0": 34, "S1": 42},
        "early_stopping": False,
        "best_checkpoint_selection": False,
        "hyperparameter_search": False,
        "test_evaluation_started": False,
        "condition_comparison_performed": False,
        "paper_training_epoch_report": "10^6",
        "reconstructed_equal_compute_budget": "1,000,000 SB3 environment timesteps per condition",
        "exact_epoch_or_optimizer_update_equivalence_claimed": False,
        "resume_equivalence_scope": "model optimizer RNG and next-episode sequence; partial rollout buffer is not restored",
    }
    shard = {
        "phase": "Phase 8D",
        "assignments": {
            "A": {"execution_site": "Laptop A", "conditions": list(SHARDS["A"])},
            "B": {"execution_site": "Laptop B", "conditions": list(SHARDS["B"])},
        },
        "all_conditions_covered_exactly_once": True,
        "condition_overlap_count": 0,
        "seed": CANONICAL_PPO_SEED,
        "total_timesteps_per_condition": FINAL_TOTAL_TIMESTEPS,
        "sequential_within_shard": True,
    }
    sampling = {
        "phase": "Phase 8D",
        "algorithm": "numpy_PCG64_uniform_integer_index_v1",
        "master_seed": CANONICAL_PPO_SEED,
        "train_case_count": len(caseids),
        "train_case_universe_sha256": universe_sha,
        "ordered_episode_sequence_checksum_count": SEQUENCE_CHECKSUM_EPISODES,
        "ordered_episode_sequence_sha256": sequence_sha,
        "same_sequence_all_conditions": True,
        "case_sequence_published": False,
        "test_case_count_used": 0,
    }
    if run_preflight:
        results = []
        for condition in ("P0S0", "P1S0", "P0S1", "P1S1"):
            state_id = "S0" if condition.endswith("S0") else "S1"
            results.append(run_condition_preflight(
                repository_root=ROOT,
                condition_id=condition,
                store=store,
                scaler=scalers[state_id],
            ))
        preflight = {
            "phase": "Phase 8D",
            "correctness_only": True,
            "final_training_timesteps_consumed": 0,
            "model_or_checkpoint_persisted": False,
            "results": results,
            "seed": CANONICAL_PPO_SEED,
            "test_access_count": 0,
            "timesteps_per_condition": 1024,
        }
    else:
        preflight = json.loads((MANIFESTS / "phase8d_preflight_summary.json").read_text(encoding="utf-8"))
    existing_source_path = MANIFESTS / "phase8d_source_snapshot.json"
    existing_source = (
        json.loads(existing_source_path.read_text(encoding="utf-8"))
        if not run_preflight and existing_source_path.is_file()
        else None
    )
    legacy_before = legacy_state() if existing_source is None else existing_source["legacy_state_before"]
    input_paths = (
        "data/manifests/phase8a_case_split_manifest.csv",
        "data/manifests/phase8a_test_seal.json",
        "data/manifests/phase8b_private_tree_summary.json",
        "data/manifests/phase8c_runtime_input_summary.json",
        "data/manifests/phase8c_scaler_registry.json",
    )
    source = {
        "phase": "Phase 8D",
        "source_head_before_publication": (
            git("rev-parse", "HEAD")
            if existing_source is None
            else existing_source["source_head_before_publication"]
        ),
        "input_artifact_sha256": {path: sha256_path(ROOT / path) for path in input_paths},
        "final_ppo_config_sha256": sha256_path(ROOT / FINAL_CONFIG_RELATIVE) if (ROOT / FINAL_CONFIG_RELATIVE).is_file() else None,
        "phase8b_private_root_sha256": PHASE8B_EXPECTED_ROOT_SHA256,
        "phase8c_private_root_sha256": PHASE8C_EXPECTED_ROOT_SHA256,
        "train_case_universe_sha256": universe_sha,
        "ordered_episode_sequence_sha256": sequence_sha,
        "legacy_state_before": legacy_before,
        "legacy_state_after": legacy_state(),
        "execution_flags": {
            "final_training_started_before_publication": False,
            "test_evaluation_started": False,
            "condition_comparison_performed": False,
            "best_checkpoint_selected": False,
            "model_or_checkpoint_publicly_persisted": False,
            "test_access_count": 0,
        },
    }
    return {
        MANIFESTS / "phase8d_final_ppo_config.json": configuration,
        MANIFESTS / "phase8d_training_protocol.json": protocol,
        MANIFESTS / "phase8d_shard_definition.json": shard,
        MANIFESTS / "phase8d_sampling_summary.json": sampling,
        MANIFESTS / "phase8d_preflight_summary.json": preflight,
        MANIFESTS / "phase8d_source_snapshot.json": source,
    }


def main() -> int:
    args = parse_args()
    if args.verify_only:
        if any(not path.is_file() for path in PUBLIC_OUTPUTS):
            raise RuntimeError("Phase 8D public artifact is missing")
        expected = build_outputs(run_preflight=False)
        for path, payload in expected.items():
            if json.loads(path.read_text(encoding="utf-8")) != payload:
                raise RuntimeError(f"Phase 8D public artifact verification failed: {path.name}")
        print("Phase 8D public artifacts verified without rerunning preflight")
        return 0
    if any(path.exists() for path in PUBLIC_OUTPUTS):
        raise RuntimeError("Phase 8D public artifacts already exist; generation refused")
    # The config must exist before source-snapshot hashing and preflight.
    atomic_json(MANIFESTS / "phase8d_final_ppo_config.json", resolved_final_configuration())
    outputs = build_outputs(run_preflight=True)
    for path, payload in outputs.items():
        atomic_json(path, payload)
    print(json.dumps({"generated": [path.relative_to(ROOT).as_posix() for path in outputs]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

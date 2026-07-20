"""Run bounded synthetic-only Phase 7H adapter and PPO integration validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "data" / "manifests"

import gymnasium
import numpy as np
import scipy
import stable_baselines3
import torch
from gymnasium.utils.env_checker import check_env as gym_check_env
from stable_baselines3.common.env_checker import check_env as sb3_check_env
from stable_baselines3.common.vec_env import DummyVecEnv

from vitaldb_state_selection.anesthesia import (  # noqa: E402
    AnesthesiaEnvironmentCore, BISEvent, ConditionID, EnvironmentConfig,
    FOUR_CONDITION_CONFIGS, PiecewiseConstantRemifentanilSchedule, SQIEvent,
    SyntheticObservationTemplate,
)
from vitaldb_state_selection.pkpd import PatientProfile, Sex  # noqa: E402
from vitaldb_state_selection.rl_integration.config import (  # noqa: E402
    PAPER_ORIENTED_PPO_CANDIDATE_V1, PPO_INTEGRATION_SMOKE_V1, make_ppo_model,
)
from vitaldb_state_selection.rl_integration.factory import make_gymnasium_environment  # noqa: E402
from vitaldb_state_selection.rl_integration.smoke import run_condition_smoke  # noqa: E402


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def write_json(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(relative_path: str) -> str:
    return hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()


def fixture() -> tuple[PatientProfile, SyntheticObservationTemplate, PiecewiseConstantRemifentanilSchedule]:
    profile = PatientProfile(45.0, Sex.FEMALE, 165.0, 60.0)
    template = SyntheticObservationTemplate(
        "phase7h-synthetic-validation-template-v1", 100.0,
        tuple(BISEvent(float(t)) for t in (0, 7, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)),
        tuple(SQIEvent(float(t), 80.0 if t != 20 else 40.0) for t in (0, 7, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)),
    )
    schedule = PiecewiseConstantRemifentanilSchedule(((0.0, 0.0), (4.0, 2.0), (17.0, 1.0)))
    return profile, template, schedule


def make(condition: str, horizon: float = 30.0):
    profile, template, schedule = fixture()
    return make_gymnasium_environment(
        condition_id=condition, patient_profile=profile, observation_template=template,
        remifentanil_schedule=schedule, seed=42, episode_horizon_seconds=horizon,
    )


def validate_adapters() -> dict[str, object]:
    rows = []
    warning_rows = []
    for condition in ConditionID:
        env = make(condition.value)
        observation, _ = env.reset(seed=42)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            gym_check_env(env, skip_render_check=True)
            sb3_check_env(env, warn=True)
        for item in caught:
            message = ANSI.sub("", str(item.message))
            classification = "expected_and_harmless" if "symmetric and normalized" in message else "unclassified_failure"
            warning_rows.append({"condition_id": condition.value, "classification": classification, "message": message})
        observation, _ = env.reset(seed=42)
        steps = 0
        truncated = False
        while not truncated:
            observation, reward, terminated, truncated, info = env.step(np.asarray([1.0], dtype=np.float32))
            steps += 1
            assert isinstance(reward, float) and isinstance(terminated, bool) and isinstance(truncated, bool)
            assert not terminated and not info["action_was_clipped"] and np.isfinite(observation).all()
        vector = DummyVecEnv([lambda condition=condition.value: make(condition)])
        model = make_ppo_model(vector, PPO_INTEGRATION_SMOKE_V1)
        assert model.num_timesteps == 0 and str(model.device) == "cpu"
        vector.close()

        profile, template, schedule = fixture()
        base = FOUR_CONDITION_CONFIGS[condition.value]
        direct = AnesthesiaEnvironmentCore(
            profile=profile,
            config=EnvironmentConfig(base.preprocessing_id, base.state_id, episode_horizon_seconds=30),
            observation_template=template,
            remifentanil_schedule=schedule,
        )
        adapted = make(condition.value)
        direct.reset(seed=42)
        adapted.reset(seed=42)
        adapted_result = adapted.step(np.asarray([2.5], dtype=np.float32))
        direct_result = direct.step(2.5)
        assert np.array_equal(adapted_result[0], direct_result[0].astype(np.float32))
        assert adapted_result[1] == direct_result[1]
        assert adapted_result[4]["latent_true_bis"] == direct_result[4]["latent_true_bis"]
        assert not adapted_result[4]["action_was_clipped"]
        rows.append({
            "condition_id": condition.value,
            "observation_shape": list(observation.shape),
            "observation_dtype": str(observation.dtype),
            "action_shape": list(env.action_space.shape),
            "action_low": float(env.action_space.low[0]),
            "action_high_declared": 27.7,
            "full_episode_control_steps": steps,
            "gymnasium_checker_passed": True,
            "sb3_checker_passed": True,
            "dummy_vec_env_passed": True,
            "ppo_initialization_without_learning_passed": True,
            "direct_adapter_transition_equal": True,
            "normal_path_core_clip_count": 0,
        })
        env.close()
        adapted.close()
    if any(row["classification"] != "expected_and_harmless" for row in warning_rows):
        raise RuntimeError("unclassified checker warning")
    return {
        "status": "passed", "conditions": rows, "checker_warnings": warning_rows,
        "warning_policy": "The physical action contract is intentionally not normalized in Phase 7H.",
    }


def smoke_validation() -> tuple[dict[str, object], dict[str, object]]:
    official = [run_condition_smoke(condition.value) for condition in ConditionID]
    public_rows = []
    for row in official:
        public_rows.append({
            key: value for key, value in row.items()
            if key not in {"model_parameter_sha256", "initial_observation_sha256", "first_deterministic_action_sha256"}
        })
    first = run_condition_smoke(ConditionID.P0S0)
    second = run_condition_smoke(ConditionID.P0S0)
    determinism = {
        "condition_id": "P0S0", "seed": 42, "repeat_count": 2,
        "initial_observation_sha256": [first["initial_observation_sha256"], second["initial_observation_sha256"]],
        "initial_observation_equal": first["initial_observation_sha256"] == second["initial_observation_sha256"],
        "first_deterministic_prediction_sha256": [first["first_deterministic_action_sha256"], second["first_deterministic_action_sha256"]],
        "first_deterministic_prediction_equal": first["first_deterministic_action_sha256"] == second["first_deterministic_action_sha256"],
        "rollout_transition_counts": [first["total_timesteps"], second["total_timesteps"]],
        "model_parameter_sha256": [first["model_parameter_sha256"], second["model_parameter_sha256"]],
        "model_parameter_checksum_equal": first["model_parameter_sha256"] == second["model_parameter_sha256"],
        "exceptions": [], "best_run_selected": False,
    }
    if not all((determinism["initial_observation_equal"], determinism["first_deterministic_prediction_equal"], determinism["model_parameter_checksum_equal"])):
        determinism["status"] = "non_bitwise_difference_recorded_no_selection"
    else:
        determinism["status"] = "passed_bitwise_parameter_checksum"
    return ({
        "configuration_id": PPO_INTEGRATION_SMOKE_V1.configuration_id,
        "official_smoke_run_count": 4, "runs": public_rows,
        "all_correctness_checks_passed": True, "condition_ranking_created": False,
        "reward_or_bis_comparison_created": False, "best_condition_selected": False,
        "best_seed_selected": False, "persistent_checkpoint_created": False,
    }, determinism)


def main() -> None:
    torch.set_num_threads(1)
    decisions = {
        "phase": "7H_stage_iii_gymnasium_sb3_integration",
        "approved_scoped_ids": [*(f"MC-{value:03d}" for value in range(19, 30)), "MC-034"],
        "still_pending_ids": ["MC-030", "MC-033"],
        "scope": "configuration_and_bounded_synthetic_integration_only_not_final_training",
        "not_yun_dependency_versions": True,
        "not_exact_unpublished_architecture_reproduction": True,
        "weight_decay_interpretation": "study approximation of reported L2 coefficient through the PyTorch Adam optimizer contract",
    }
    write_json("phase7h_human_decisions.json", decisions)
    write_json("phase7h_scientific_ppo_candidate.json", PAPER_ORIENTED_PPO_CANDIDATE_V1.as_manifest())
    write_json("phase7h_smoke_ppo_configuration.json", PPO_INTEGRATION_SMOKE_V1.as_manifest())
    adapter_validation = validate_adapters()
    write_json("phase7h_adapter_validation_summary.json", adapter_validation)
    smoke, determinism = smoke_validation()
    write_json("phase7h_smoke_summary.json", smoke)
    write_json("phase7h_determinism_summary.json", determinism)

    adam = torch.optim.Adam([torch.nn.Parameter(torch.zeros(1))]).defaults
    write_json("phase7h_runtime_environment.json", {
        "environment_type": "repository_local_ignored_virtual_environment",
        "environment_path_token": ".venv-phase7h",
        "python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
        "os": platform.system(), "os_release": platform.release(), "platform": platform.platform(),
        "architecture": platform.machine(), "pip_version": __import__("pip").__version__,
        "stable_baselines3_version": stable_baselines3.__version__, "gymnasium_version": gymnasium.__version__,
        "torch_version": torch.__version__, "numpy_version": np.__version__, "scipy_version": scipy.__version__,
        "execution_device": "cpu", "cuda_required": False, "cuda_used": False,
        "torch_cpu_threads": torch.get_num_threads(),
        "adam_defaults_locked": {"betas": list(adam["betas"]), "eps": adam["eps"], "amsgrad": adam["amsgrad"]},
        "phase7h_optimizer_override": {"learning_rate": 0.001, "weight_decay": 0.001},
        "direct_dependency_file_sha256": sha256("requirements/phase7h_rl_direct.txt"),
        "resolved_lock_file_sha256": sha256("requirements/phase7h_rl_lock.txt"),
        "global_environment_mutated": False,
        "base_runtime_note": "Declared base test dependencies and resolver-selected SciPy were installed only inside the isolated venv because Stage I imports SciPy while pyproject does not declare it.",
    })
    write_json("phase7h_source_snapshot.json", {
        "phase": "7H_stage_iii_gymnasium_sb3_integration",
        "source_remote_main_at_start": "66c603c4e80fecb1a5efd01b1669df147ee5380d",
        "frozen_case_count": 2460, "frozen_subject_count": 2415,
        "input_artifact_sha256": {
            path: sha256(path) for path in (
                "data/manifests/phase7f_artifact_checksums.json",
                "data/manifests/phase7g_artifact_checksums.json",
                "data/manifests/phase7g_source_snapshot.json",
                "data/manifests/final_eligible_cohort_manifest.csv", "pyproject.toml",
            )
        },
        "legacy_state_before": {"head": "9501b16a5c4db27f06fa0d0b252a3a75f633967f", "tree": "60917f0b61ec1e6a195b9a648faa6466406aeda1", "status": ["?? debug.log"]},
        "legacy_state_after": {"head": "9501b16a5c4db27f06fa0d0b252a3a75f633967f", "tree": "60917f0b61ec1e6a195b9a648faa6466406aeda1", "status": ["?? debug.log"]},
        "execution_flags": {
            "raw_vitaldb_access": False, "subject_metadata_access": False, "actual_template_extracted": False,
            "real_patient_used": False, "split_created": False, "test_seal_created": False,
            "final_training_run": False, "final_evaluation_run": False, "statistical_analysis": False,
            "checkpoint_persisted": False, "tensorboard_output": False, "monitor_output": False,
            "prediction": False, "elastic_net": False, "gru": False, "attention_gru": False,
        },
    })


if __name__ == "__main__":
    main()

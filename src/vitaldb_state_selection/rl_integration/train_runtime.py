"""Optional Gymnasium/SB3 integration for ignored Phase 8C train runtime bundles."""

from __future__ import annotations

import hashlib
import math
import random
import time
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.vec_env import DummyVecEnv

from vitaldb_state_selection.anesthesia import ConditionID, StateID
from vitaldb_state_selection.cohort.train_runtime_inputs import (
    StateScaler,
    TrainRuntimeInputStore,
)

from .config import PPO_INTEGRATION_SMOKE_V1, make_ppo_model
from .factory import make_gymnasium_environment


CANONICAL_PPO_SEED = 42
SMOKE_TIMESTEPS = 128


class ScaledTrainRuntimeEnv(gym.Env[np.ndarray, np.ndarray]):
    """Apply one S-specific train-only scaler without changing core dynamics."""

    metadata = {"render_modes": []}

    def __init__(self, environment: gym.Env[np.ndarray, np.ndarray], scaler: StateScaler):
        self.environment = environment
        self.scaler = scaler
        self.action_space = environment.action_space
        dimension = len(scaler.fields)
        limit = np.finfo(np.float32).max
        low = np.full(dimension, -limit, dtype=np.float32)
        high = np.full(dimension, limit, dtype=np.float32)
        for index, field in enumerate(scaler.fields):
            if field.binary_unchanged:
                low[index], high[index] = 0.0, 1.0
        self.observation_space = gym.spaces.Box(low=low, high=high, dtype=np.float32)
        self.render_mode = None

    @property
    def core(self) -> Any:
        return self.environment.core

    def _scaled(self, observation: np.ndarray) -> np.ndarray:
        result = np.asarray(self.scaler.transform(observation), dtype=np.float32)
        if result.shape != self.observation_space.shape or not np.isfinite(result).all():
            raise RuntimeError("scaled train observation invariant failed")
        if not self.observation_space.contains(result):
            raise RuntimeError("scaled train observation is outside its declared space")
        return result

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        observation, info = self.environment.reset(seed=seed, options=options)
        return self._scaled(observation), info

    def step(self, action: np.ndarray):
        observation, reward, terminated, truncated, info = self.environment.step(action)
        return self._scaled(observation), reward, terminated, truncated, info

    def render(self) -> None:
        return None

    def close(self) -> None:
        self.environment.close()


def make_train_runtime_environment(
    *,
    store: TrainRuntimeInputStore,
    caseid: object,
    condition_id: ConditionID | str,
    scaler: StateScaler,
    seed: int = CANONICAL_PPO_SEED,
) -> ScaledTrainRuntimeEnv:
    if seed != CANONICAL_PPO_SEED:
        raise ValueError("Phase 8C actual-runtime environments require canonical seed 42")
    condition = condition_id if isinstance(condition_id, ConditionID) else ConditionID(condition_id)
    expected_state = StateID.S0.value if condition.value.endswith("S0") else StateID.S1.value
    if scaler.state_id != expected_state:
        raise ValueError("condition/scaler state-profile mismatch")
    bundle = store.load_case(caseid)
    # Preserve the 10-second Stage II interval and use only complete intervals inside anesthesia.
    horizon = math.floor(bundle.episode_horizon_seconds / 10.0) * 10.0
    if horizon < 10.0:
        raise ValueError("actual train episode has no complete control interval")
    environment = make_gymnasium_environment(
        condition_id=condition,
        patient_profile=bundle.profile,
        observation_template=bundle.observation_template,
        remifentanil_schedule=bundle.remifentanil_schedule,
        seed=seed,
        episode_horizon_seconds=horizon,
    )
    return ScaledTrainRuntimeEnv(environment, scaler)


def _parameter_checksum(model: Any) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.policy.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def run_train_condition_smoke(
    *,
    repository_root: Path | str,
    private_root: Path | str,
    caseid: object,
    condition_id: ConditionID | str,
    scaler: StateScaler,
) -> dict[str, object]:
    """Run exactly 128 CPU timesteps; return diagnostics without persisting a model."""

    root = Path(repository_root)
    condition = condition_id if isinstance(condition_id, ConditionID) else ConditionID(condition_id)
    random.seed(CANONICAL_PPO_SEED)
    np.random.seed(CANONICAL_PPO_SEED)
    torch.manual_seed(CANONICAL_PPO_SEED)
    torch.set_num_threads(1)

    checker_store = TrainRuntimeInputStore(private_root, root)
    checker_env = make_train_runtime_environment(
        store=checker_store,
        caseid=caseid,
        condition_id=condition,
        scaler=scaler,
    )
    check_env(checker_env, warn=True, skip_render_check=True)
    observation, _ = checker_env.reset(seed=CANONICAL_PPO_SEED)
    checker_env.close()

    def environment_factory() -> ScaledTrainRuntimeEnv:
        store = TrainRuntimeInputStore(private_root, root)
        return make_train_runtime_environment(
            store=store,
            caseid=caseid,
            condition_id=condition,
            scaler=scaler,
        )

    vector_environment = DummyVecEnv([environment_factory])
    model = make_ppo_model(vector_environment, PPO_INTEGRATION_SMOKE_V1)
    first_action, _ = model.predict(observation, deterministic=True)
    if np.asarray(first_action).shape != (1,) or not np.isfinite(first_action).all():
        raise RuntimeError("actual-runtime smoke prediction is not finite shape-(1,)")
    started = time.perf_counter()
    model.learn(total_timesteps=SMOKE_TIMESTEPS, reset_num_timesteps=True, progress_bar=False)
    runtime_seconds = time.perf_counter() - started
    if model.num_timesteps != SMOKE_TIMESTEPS:
        raise RuntimeError("actual-runtime smoke timestep budget mismatch")
    parameters_finite = all(torch.isfinite(parameter).all().item() for parameter in model.policy.parameters())
    gradients = [parameter.grad for parameter in model.policy.parameters() if parameter.grad is not None]
    gradients_finite = all(torch.isfinite(gradient).all().item() for gradient in gradients)
    losses = [
        float(value)
        for key, value in model.logger.name_to_value.items()
        if key.startswith("train/") and "loss" in key and isinstance(value, (int, float, np.floating))
    ]
    losses_finite = bool(losses) and all(math.isfinite(value) for value in losses)
    result = {
        "action_bounds_unchanged": True,
        "checkpoint_created": False,
        "condition_id": condition.value,
        "device": str(model.device),
        "env_checker_passed": True,
        "final_performance_claimed": False,
        "finite_logged_loss_count": len(losses),
        "gradients_finite_where_present": bool(gradients_finite),
        "initial_observation_sha256": hashlib.sha256(observation.tobytes()).hexdigest(),
        "learn_completed": True,
        "logged_losses_finite": bool(losses_finite),
        "model_parameter_sha256_in_memory_only": _parameter_checksum(model),
        "model_persisted": False,
        "observation_shape": list(observation.shape),
        "parameters_finite": bool(parameters_finite),
        "performance_ranking_computed": False,
        "runtime_seconds": runtime_seconds,
        "seed": CANONICAL_PPO_SEED,
        "status": "passed",
        "test_access_count": 0,
        "total_timesteps": int(model.num_timesteps),
        "vec_env_created": True,
    }
    vector_environment.close()
    del model
    if not all((parameters_finite, gradients_finite, losses_finite)):
        raise RuntimeError("nonfinite actual-runtime PPO smoke diagnostic")
    return result

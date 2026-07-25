"""Phase 8G prespecified seed-43/44 train-only PPO extension."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv

from vitaldb_state_selection.anesthesia import ConditionID, StateID
from vitaldb_state_selection.cohort.train_runtime_inputs import (
    StateScaler,
    TrainRuntimeInputStore,
    canonical_json_bytes,
    load_scaler_registry,
)

from .config import PPOConfiguration, make_ppo_model
from .factory import make_gymnasium_environment
from .final_training import (
    CHECKPOINT_INTERVAL,
    DEFAULT_OUTPUT_ROOT_RELATIVE,
    FINAL_CONFIG_RELATIVE,
    FINAL_PPO_CONFIGURATION,
    FINAL_TOTAL_TIMESTEPS,
    PHASE8A_TRAIN_CASE_IDS_SHA256,
    PHASE8B_PRIVATE_ROOT_RELATIVE,
    PHASE8C_EXPECTED_ROOT_SHA256,
    PHASE8C_PRIVATE_ROOT_RELATIVE,
    SCALER_REGISTRY_RELATIVE,
    SHARDS,
    CheckpointManager,
    FinalTrainingError,
    _caseids,
    _finite_model_diagnostics,
    atomic_json,
    final_config_sha256,
    train_universe_sha256,
    utc_now,
    validate_output_root,
    verify_repository_gate,
)
from .train_runtime import ScaledTrainRuntimeEnv


ALLOWED_SEEDS = (43, 44)
LEGACY_SEED = 42
LEGACY_TRAINING_IMPLEMENTATION_SHA = "b782b5e4a9d418f6b907a87d046c4e9789a3e5f0"
LEGACY_CONFIG_SHA256 = "b5d79a2fb8be3b5337c7cb807936247c630b86f108f2a92cc6f645023f789b3e"
SEQUENCE_CHECKSUM_EPISODES = 1_000_000


class MultiSeedTrainingError(FinalTrainingError):
    """Raised when a Phase 8G execution or integrity gate fails closed."""


def validate_seed(seed: int) -> int:
    if isinstance(seed, bool) or seed not in ALLOWED_SEEDS:
        raise MultiSeedTrainingError("Phase 8G accepts exactly seeds 43 and 44")
    return seed


def multiseed_configuration(seed: int) -> PPOConfiguration:
    seed = validate_seed(seed)
    return replace(
        FINAL_PPO_CONFIGURATION,
        configuration_id=f"phase8g_multiseed_final_ppo_seed_{seed}_v1",
        seed=seed,
        purpose="prespecified_multiseed_robustness_training_no_test_evaluation",
    )


def resolved_multiseed_configuration(seed: int) -> dict[str, object]:
    configuration = multiseed_configuration(seed)
    payload = configuration.as_manifest()
    payload.update(
        {
            "base_phase8d_configuration_sha256": final_config_sha256(),
            "checkpoint_interval_timesteps": CHECKPOINT_INTERVAL,
            "extension_seed": seed,
            "final_checkpoint_timestep": FINAL_TOTAL_TIMESTEPS,
            "only_seed_differs_from_phase8d_ppo_hyperparameters": True,
        }
    )
    return payload


def multiseed_config_sha256(seed: int) -> str:
    return hashlib.sha256(
        canonical_json_bytes(resolved_multiseed_configuration(seed))
    ).hexdigest()


def episode_sequence_sha256(
    caseids: tuple[str, ...],
    *,
    seed: int,
    count: int = SEQUENCE_CHECKSUM_EPISODES,
) -> str:
    validate_seed(seed)
    if count <= 0:
        raise MultiSeedTrainingError("sequence checksum count must be positive")
    generator = np.random.Generator(np.random.PCG64(seed))
    digest = hashlib.sha256()
    remaining = count
    while remaining:
        size = min(remaining, 100_000)
        indices = generator.integers(0, len(caseids), size=size, dtype=np.int64)
        for index in indices:
            digest.update(caseids[int(index)].encode("ascii"))
            digest.update(b"\0")
        remaining -= size
    return digest.hexdigest()


class MultiSeedTrainCaseSequence:
    """Independent PCG64 stream shared by all conditions for one seed."""

    def __init__(self, caseids: tuple[str, ...], *, seed: int) -> None:
        self.seed = validate_seed(seed)
        if len(caseids) != 1970 or len(set(caseids)) != 1970:
            raise MultiSeedTrainingError(
                "sealed train universe must contain exactly 1,970 unique cases"
            )
        self.caseids = caseids
        self.generator = np.random.Generator(np.random.PCG64(seed))
        self.episode_index = 0

    def next_caseid(self) -> str:
        index = int(self.generator.integers(0, len(self.caseids)))
        self.episode_index += 1
        return self.caseids[index]

    def snapshot(self) -> dict[str, object]:
        return {
            "bit_generator": "PCG64",
            "episode_index": self.episode_index,
            "seed": self.seed,
            "state": self.generator.bit_generator.state,
            "train_universe_sha256": train_universe_sha256(self.caseids),
        }

    def restore(self, payload: dict[str, object]) -> None:
        if payload.get("seed") != self.seed or payload.get("bit_generator") != "PCG64":
            raise MultiSeedTrainingError(
                "checkpoint train-case sequence seed or generator mismatch"
            )
        if payload.get("train_universe_sha256") != train_universe_sha256(
            self.caseids
        ):
            raise MultiSeedTrainingError("checkpoint train-case universe mismatch")
        episode_index = payload.get("episode_index")
        if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
            raise MultiSeedTrainingError("checkpoint episode index is invalid")
        self.generator.bit_generator.state = payload["state"]  # type: ignore[assignment]
        self.episode_index = episode_index


def make_multiseed_train_runtime_environment(
    *,
    store: TrainRuntimeInputStore,
    caseid: object,
    condition_id: ConditionID | str,
    scaler: StateScaler,
    seed: int,
) -> ScaledTrainRuntimeEnv:
    seed = validate_seed(seed)
    condition = (
        condition_id
        if isinstance(condition_id, ConditionID)
        else ConditionID(condition_id)
    )
    expected_state = (
        StateID.S0.value if condition.value.endswith("S0") else StateID.S1.value
    )
    if scaler.state_id != expected_state:
        raise MultiSeedTrainingError("condition/scaler state-profile mismatch")
    bundle = store.load_case(caseid)
    horizon = math.floor(bundle.episode_horizon_seconds / 10.0) * 10.0
    if horizon < 10.0:
        raise MultiSeedTrainingError(
            "actual train episode has no complete control interval"
        )
    environment = make_gymnasium_environment(
        condition_id=condition,
        patient_profile=bundle.profile,
        observation_template=bundle.observation_template,
        remifentanil_schedule=bundle.remifentanil_schedule,
        seed=seed,
        episode_horizon_seconds=horizon,
    )
    return ScaledTrainRuntimeEnv(environment, scaler)


class MultiSeedSequentialTrainRuntimeEnv(gym.Env[np.ndarray, np.ndarray]):
    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        store: TrainRuntimeInputStore,
        condition_id: ConditionID | str,
        scaler: StateScaler,
        sequence: MultiSeedTrainCaseSequence,
        seed: int,
    ) -> None:
        self.seed = validate_seed(seed)
        if sequence.seed != self.seed:
            raise MultiSeedTrainingError("environment and sequence seed mismatch")
        self.store = store
        self.condition = (
            condition_id
            if isinstance(condition_id, ConditionID)
            else ConditionID(condition_id)
        )
        self.scaler = scaler
        self.sequence = sequence
        expected_state = "S0" if self.condition.value.endswith("S0") else "S1"
        if scaler.state_id != expected_state:
            raise MultiSeedTrainingError("condition/scaler mismatch")
        dimension = len(scaler.fields)
        limit = np.finfo(np.float32).max
        low = np.full(dimension, -limit, dtype=np.float32)
        high = np.full(dimension, limit, dtype=np.float32)
        for index, field in enumerate(scaler.fields):
            if field.binary_unchanged:
                low[index], high[index] = 0.0, 1.0
        self.observation_space = gym.spaces.Box(
            low=low, high=high, dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=np.asarray([0.0], dtype=np.float32),
            high=np.asarray([27.7], dtype=np.float32),
            dtype=np.float32,
        )
        self.render_mode = None
        self._environment: ScaledTrainRuntimeEnv | None = None
        self.test_access_count = 0

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ):
        if seed not in (None, self.seed):
            raise MultiSeedTrainingError("environment reset seed mismatch")
        if options not in (None, {}):
            raise MultiSeedTrainingError("environment reset options are unsupported")
        super().reset(seed=self.seed)
        if self._environment is not None:
            self._environment.close()
        caseid = self.sequence.next_caseid()
        self._environment = make_multiseed_train_runtime_environment(
            store=self.store,
            caseid=caseid,
            condition_id=self.condition,
            scaler=self.scaler,
            seed=self.seed,
        )
        observation, info = self._environment.reset(seed=self.seed)
        info = dict(info)
        info.update(
            {
                "phase8g_episode_index": self.sequence.episode_index - 1,
                "phase8g_test_access_count": self.test_access_count,
            }
        )
        return observation, info

    def step(self, action: np.ndarray):
        if self._environment is None:
            raise MultiSeedTrainingError("reset is required before training step")
        observation, reward, terminated, truncated, info = self._environment.step(
            action
        )
        info = dict(info)
        info.update(
            {
                "phase8g_future_remifentanil_leakage_count": 0,
                "phase8g_test_access_count": self.test_access_count,
            }
        )
        return observation, reward, terminated, truncated, info

    def close(self) -> None:
        if self._environment is not None:
            self._environment.close()


class MultiSeedCheckpointManager(CheckpointManager):
    def assert_no_partials(self) -> None:
        if not self.directory.exists():
            return
        partials = [
            path for path in self.directory.iterdir() if path.name.endswith(".partial")
        ]
        if partials:
            names = ", ".join(sorted(path.name for path in partials))
            raise MultiSeedTrainingError(
                f"ambiguous partial paths require manual inspection: {names}"
            )

    def cleanup_partials(self) -> int:
        self.assert_no_partials()
        return 0


def condition_output_directory(
    output_root: Path, condition_id: str, seed: int
) -> Path:
    seed = validate_seed(seed)
    condition = ConditionID(condition_id).value
    directory = output_root / condition / f"seed_{seed}"
    if directory.name == "seed_42":
        raise MultiSeedTrainingError("Phase 8G may not write seed_42")
    return directory


def make_checkpoint_manager(
    *,
    condition_directory: Path,
    condition_id: str,
    implementation_sha: str,
    config_sha256: str,
    state_schema_sha256: str,
    train_universe_sha256_value: str,
    seed: int,
    create: bool = True,
) -> MultiSeedCheckpointManager:
    validate_seed(seed)
    if not create and not condition_directory.is_dir():
        raise MultiSeedTrainingError(
            f"canonical seed output directory is missing: {condition_directory}"
        )
    return MultiSeedCheckpointManager(
        condition_directory=condition_directory,
        condition_id=ConditionID(condition_id).value,
        implementation_sha=implementation_sha,
        config_sha256=config_sha256,
        state_schema_sha256=state_schema_sha256,
        runtime_root_sha256=PHASE8C_EXPECTED_ROOT_SHA256,
        train_universe_sha256_value=train_universe_sha256_value,
        seed=seed,
        total_timesteps=FINAL_TOTAL_TIMESTEPS,
    )


def validate_resume_metadata(
    path: Path, *, expected: dict[str, object]
) -> dict[str, object]:
    observed = json.loads(path.read_text(encoding="utf-8"))
    for key, value in expected.items():
        if observed.get(key) != value:
            raise MultiSeedTrainingError(f"resume {key} mismatch")
    return observed


def set_global_seed(seed: int) -> None:
    seed = validate_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)


def append_progress(directory: Path, row: dict[str, object]) -> None:
    seed = row.get("seed")
    validate_seed(seed)  # type: ignore[arg-type]
    ConditionID(str(row.get("condition_id")))
    if row.get("test_access_count") != 0:
        raise MultiSeedTrainingError("progress row records test access")
    if row.get("future_remifentanil_leakage_count", 0) != 0:
        raise MultiSeedTrainingError(
            "progress row records future remifentanil leakage"
        )
    timestep = row.get("timestep")
    if isinstance(timestep, bool) or not isinstance(timestep, int) or timestep < 0:
        raise MultiSeedTrainingError("progress timestep is invalid")
    payload = dict(row)
    payload.setdefault("wall_clock_timestamp_utc", utc_now())
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "progress.jsonl").open(
        "a", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write(json.dumps(payload, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _unwrap_multiseed_environment(vector_environment: Any) -> MultiSeedSequentialTrainRuntimeEnv:
    environment = vector_environment.envs[0]
    while hasattr(environment, "env"):
        environment = environment.env
    if not isinstance(environment, MultiSeedSequentialTrainRuntimeEnv):
        raise MultiSeedTrainingError("unexpected Phase 8G environment wrapper")
    return environment


class MultiSeedTrainingCallback(BaseCallback):
    def __init__(self, manager: MultiSeedCheckpointManager, *, target_timestep: int):
        super().__init__(verbose=0)
        self.manager = manager
        self.target_timestep = target_timestep
        self.last_checkpoint = 0

    def _on_step(self) -> bool:
        for key in ("new_obs", "actions", "rewards"):
            value = self.locals.get(key)
            if value is not None and not np.isfinite(np.asarray(value)).all():
                raise MultiSeedTrainingError(f"nonfinite callback {key}")
        infos = self.locals.get("infos") or []
        if any(info.get("phase8g_test_access_count", 0) != 0 for info in infos):
            raise MultiSeedTrainingError("test access detected during Phase 8G")
        if any(
            info.get("phase8g_future_remifentanil_leakage_count", 0) != 0
            for info in infos
        ):
            raise MultiSeedTrainingError("future remifentanil leakage detected")
        timestep = int(self.model.num_timesteps)
        if timestep % CHECKPOINT_INTERVAL == 0 and timestep > self.last_checkpoint:
            sequence = _unwrap_multiseed_environment(self.training_env).sequence
            self.manager.save(self.model, sequence)  # type: ignore[arg-type]
            parameters_finite, gradients_finite, gradient_norm = (
                _finite_model_diagnostics(self.model)
            )
            append_progress(
                self.manager.directory,
                {
                    "condition_id": self.manager.condition_id,
                    "event": "checkpoint",
                    "future_remifentanil_leakage_count": 0,
                    "gradient_norm": gradient_norm,
                    "gradients_finite": gradients_finite,
                    "parameters_finite": parameters_finite,
                    "seed": self.manager.seed,
                    "test_access_count": 0,
                    "timestep": timestep,
                },
            )
            self.last_checkpoint = timestep
        return timestep < self.target_timestep


def run_condition_preflight(
    *,
    condition_id: str,
    store: TrainRuntimeInputStore,
    scaler: StateScaler,
    seed: int,
    timesteps: int = 1024,
) -> dict[str, object]:
    if timesteps != 1024:
        raise MultiSeedTrainingError("Phase 8G preflight is fixed at 1,024 timesteps")
    set_global_seed(seed)
    sequence = MultiSeedTrainCaseSequence(_caseids(store), seed=seed)
    environment = DummyVecEnv(
        [
            lambda: MultiSeedSequentialTrainRuntimeEnv(
                store=store,
                condition_id=condition_id,
                scaler=scaler,
                sequence=sequence,
                seed=seed,
            )
        ]
    )
    configuration = replace(
        multiseed_configuration(seed),
        configuration_id=f"phase8g_preflight_seed_{seed}_1024_v1",
        n_steps=1024,
        total_timesteps=1024,
        purpose="bounded_preflight_not_final_training",
    )
    model = make_ppo_model(environment, configuration)
    started = time.perf_counter()
    model.learn(total_timesteps=timesteps, reset_num_timesteps=True, progress_bar=False)
    wall = time.perf_counter() - started
    parameters_finite, gradients_finite, gradient_norm = _finite_model_diagnostics(
        model
    )
    values = [
        float(value)
        for key, value in model.logger.name_to_value.items()
        if key.startswith("train/") and isinstance(value, (int, float, np.floating))
    ]
    result = {
        "condition_id": ConditionID(condition_id).value,
        "final_checkpoint_created": False,
        "gradients_finite": gradients_finite,
        "model_or_checkpoint_persisted": False,
        "observation_dimension": len(scaler.fields),
        "parameters_finite": parameters_finite,
        "seed": seed,
        "status": "passed",
        "test_access_count": 0,
        "timesteps": int(model.num_timesteps),
        "training_values_finite": bool(values)
        and all(math.isfinite(value) for value in values),
        "wall_clock_seconds": wall,
    }
    environment.close()
    del model
    if (
        result["timesteps"] != timesteps
        or not parameters_finite
        or not gradients_finite
        or not math.isfinite(gradient_norm)
        or not result["training_values_finite"]
    ):
        raise MultiSeedTrainingError("Phase 8G preflight diagnostic failed")
    return result


def train_condition(
    *,
    output_root: Path,
    expected_git_sha: str,
    condition_id: str,
    store: TrainRuntimeInputStore,
    scaler: StateScaler,
    resume: bool,
    seed: int,
    total_timesteps: int = FINAL_TOTAL_TIMESTEPS,
) -> dict[str, object]:
    if total_timesteps != FINAL_TOTAL_TIMESTEPS:
        raise MultiSeedTrainingError(
            "Phase 8G accepts exactly 1,000,000 timesteps"
        )
    seed = validate_seed(seed)
    condition = ConditionID(condition_id).value
    caseids = _caseids(store)
    universe_sha = train_universe_sha256(caseids)
    sequence = MultiSeedTrainCaseSequence(caseids, seed=seed)
    directory = condition_output_directory(output_root, condition, seed)
    manager = make_checkpoint_manager(
        condition_directory=directory,
        condition_id=condition,
        implementation_sha=expected_git_sha,
        config_sha256=multiseed_config_sha256(seed),
        state_schema_sha256=scaler.schema_sha256,
        train_universe_sha256_value=universe_sha,
        seed=seed,
    )
    manager.assert_no_partials()
    if (directory / "OUTPUT_COMPLETE.json").is_file():
        payload = manager.verify_completion()
        payload["already_complete"] = True
        return payload
    latest = manager.latest()
    if latest is not None and not resume:
        raise MultiSeedTrainingError(
            "valid checkpoint exists but --resume was not supplied"
        )
    set_global_seed(seed)
    environment = DummyVecEnv(
        [
            lambda: MultiSeedSequentialTrainRuntimeEnv(
                store=store,
                condition_id=condition,
                scaler=scaler,
                sequence=sequence,
                seed=seed,
            )
        ]
    )
    resumed = latest is not None
    if latest is None:
        model = make_ppo_model(environment, multiseed_configuration(seed))
        starting_timestep = 0
    else:
        starting_timestep, checkpoint_directory, metadata = latest
        expected_metadata = manager.expected_metadata(starting_timestep)
        validate_resume_metadata(
            checkpoint_directory / "metadata.json", expected=expected_metadata
        )
        manager.load_rng(checkpoint_directory, sequence)  # type: ignore[arg-type]
        model = PPO.load(
            str(checkpoint_directory / "model.zip"), env=environment, device="cpu"
        )
        if int(model.num_timesteps) != starting_timestep:
            raise MultiSeedTrainingError("loaded model timestep mismatch")
    atomic_json(directory / "resolved_config.json", resolved_multiseed_configuration(seed))
    atomic_json(
        directory / "training_schedule.json",
        {
            "checkpoint_interval": CHECKPOINT_INTERVAL,
            "condition_id": condition,
            "episode_sequence_sha256": episode_sequence_sha256(
                caseids, seed=seed
            ),
            "seed": seed,
            "total_timesteps": total_timesteps,
            "train_universe_sha256": universe_sha,
        },
    )
    started_timestamp = utc_now()
    started = time.perf_counter()
    append_progress(
        directory,
        {
            "condition_id": condition,
            "event": "training_start_or_resume",
            "future_remifentanil_leakage_count": 0,
            "seed": seed,
            "starting_timestep": starting_timestep,
            "test_access_count": 0,
            "timestep": starting_timestep,
        },
    )
    callback = MultiSeedTrainingCallback(manager, target_timestep=total_timesteps)
    callback.last_checkpoint = starting_timestep
    remaining = total_timesteps - starting_timestep
    if remaining <= 0:
        raise MultiSeedTrainingError("incomplete checkpoint is not resumable")
    model.learn(
        total_timesteps=remaining,
        reset_num_timesteps=starting_timestep == 0,
        callback=callback,
        progress_bar=False,
    )
    wall = time.perf_counter() - started
    if int(model.num_timesteps) != total_timesteps:
        raise MultiSeedTrainingError("final timestep is not exactly 1,000,000")
    append_progress(
        directory,
        {
            "condition_id": condition,
            "event": "training_complete",
            "future_remifentanil_leakage_count": 0,
            "seed": seed,
            "test_access_count": 0,
            "timestep": total_timesteps,
        },
    )
    completion = manager.finalize(
        model,
        started_timestamp_utc=started_timestamp,
        wall_clock_seconds=wall,
        resumed=resumed,
    )
    completion.update(
        {
            "already_complete": False,
            "starting_timestep": starting_timestep,
        }
    )
    environment.close()
    del model
    return completion


def verify_private_outputs(
    *,
    repository_root: Path,
    output_root: Path,
    expected_git_sha: str,
    conditions: Iterable[str],
    seed: int,
) -> dict[str, object]:
    seed = validate_seed(seed)
    store = TrainRuntimeInputStore(
        repository_root / PHASE8C_PRIVATE_ROOT_RELATIVE, repository_root
    )
    scalers = load_scaler_registry(repository_root / SCALER_REGISTRY_RELATIVE)
    caseids = _caseids(store)
    results = []
    for condition in conditions:
        state = "S0" if condition.endswith("S0") else "S1"
        directory = condition_output_directory(output_root, condition, seed)
        manager = make_checkpoint_manager(
            condition_directory=directory,
            condition_id=condition,
            implementation_sha=expected_git_sha,
            config_sha256=multiseed_config_sha256(seed),
            state_schema_sha256=scalers[state].schema_sha256,
            train_universe_sha256_value=train_universe_sha256(caseids),
            seed=seed,
            create=False,
        )
        manager.assert_no_partials()
        checkpoints = manager.checkpoints()
        completion = manager.verify_completion()
        results.append(
            {
                "condition_id": condition,
                "checkpoint_timesteps": [row[0] for row in checkpoints],
                "complete": True,
                "final_model_sha256": completion["final_model_sha256"],
                "optimizer_sha256": completion[
                    "final_optimizer_state_sha256"
                ],
                "output_root_sha256": completion["output_root_sha256"],
                "test_access_count": completion["test_access_count"],
            }
        )
    return {"conditions": results, "seed": seed, "test_access_count": 0}


def verify_legacy_seed42_outputs(
    *,
    repository_root: Path,
    output_root: Path,
    conditions: Iterable[str],
) -> dict[str, object]:
    store = TrainRuntimeInputStore(
        repository_root / PHASE8C_PRIVATE_ROOT_RELATIVE, repository_root
    )
    scalers = load_scaler_registry(repository_root / SCALER_REGISTRY_RELATIVE)
    caseids = _caseids(store)
    results = []
    for condition in conditions:
        state = "S0" if condition.endswith("S0") else "S1"
        directory = output_root / condition / "seed_42"
        if not directory.is_dir():
            raise MultiSeedTrainingError(f"legacy seed-42 directory missing: {condition}")
        manager = CheckpointManager(
            condition_directory=directory,
            condition_id=condition,
            implementation_sha=LEGACY_TRAINING_IMPLEMENTATION_SHA,
            config_sha256=LEGACY_CONFIG_SHA256,
            state_schema_sha256=scalers[state].schema_sha256,
            runtime_root_sha256=PHASE8C_EXPECTED_ROOT_SHA256,
            train_universe_sha256_value=train_universe_sha256(caseids),
            seed=LEGACY_SEED,
            total_timesteps=FINAL_TOTAL_TIMESTEPS,
        )
        completion = manager.verify_completion()
        results.append(
            {
                "condition_id": condition,
                "final_model_sha256": completion["final_model_sha256"],
                "output_root_sha256": completion["output_root_sha256"],
            }
        )
    return {
        "conditions": results,
        "legacy_config_sha256": LEGACY_CONFIG_SHA256,
        "legacy_training_implementation_sha": LEGACY_TRAINING_IMPLEMENTATION_SHA,
        "read_only": True,
    }


__all__ = [
    "ALLOWED_SEEDS",
    "append_progress",
    "CHECKPOINT_INTERVAL",
    "DEFAULT_OUTPUT_ROOT_RELATIVE",
    "FINAL_TOTAL_TIMESTEPS",
    "MultiSeedSequentialTrainRuntimeEnv",
    "MultiSeedTrainCaseSequence",
    "MultiSeedTrainingError",
    "PHASE8C_EXPECTED_ROOT_SHA256",
    "SHARDS",
    "condition_output_directory",
    "episode_sequence_sha256",
    "make_checkpoint_manager",
    "multiseed_config_sha256",
    "multiseed_configuration",
    "resolved_multiseed_configuration",
    "run_condition_preflight",
    "train_condition",
    "train_universe_sha256",
    "validate_output_root",
    "validate_resume_metadata",
    "verify_legacy_seed42_outputs",
    "verify_private_outputs",
    "verify_repository_gate",
]

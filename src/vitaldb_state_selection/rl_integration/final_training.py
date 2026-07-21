"""Phase 8D deterministic, resumable, train-only final PPO execution."""

from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv

from vitaldb_state_selection.anesthesia import ConditionID
from vitaldb_state_selection.cohort.train_runtime_inputs import (
    PHASE8B_EXPECTED_ROOT_SHA256,
    PRIVATE_ROOT_RELATIVE as PHASE8C_PRIVATE_ROOT_RELATIVE,
    StateScaler,
    TrainRuntimeInputStore,
    canonical_json_bytes,
    load_scaler_registry,
    sha256_path,
)

from .config import PAPER_ORIENTED_PPO_CANDIDATE_V1, make_ppo_model
from .train_runtime import CANONICAL_PPO_SEED, make_train_runtime_environment


FINAL_TOTAL_TIMESTEPS = 1_000_000
CHECKPOINT_INTERVAL = 100_000
SEQUENCE_CHECKSUM_EPISODES = 1_000_000
PHASE8C_EXPECTED_ROOT_SHA256 = "25ad8a860f6c9b0b45febec7ff7d0d0edf88c0f1953229c8d95e207508d3a606"
PHASE8A_TRAIN_CASE_IDS_SHA256 = "b29464c8318ed1a82181a85c47aeb8d1bf1d6581564f4fdcdb7dd9288003b6a8"
PHASE8A_SEAL_PAYLOAD_SHA256 = "6083be99567d5d7d4989ef3c9e35fc51255f614098697f289daac756d643f9af"
DEFAULT_OUTPUT_ROOT_RELATIVE = Path("data/processed/phase8d_final_training_v1")
SCALER_REGISTRY_RELATIVE = Path("data/manifests/phase8c_scaler_registry.json")
FINAL_CONFIG_RELATIVE = Path("data/manifests/phase8d_final_ppo_config.json")
SOURCE_SNAPSHOT_RELATIVE = Path("data/manifests/phase8d_source_snapshot.json")
PHASE8B_PRIVATE_ROOT_RELATIVE = Path("data/processed/phase8b_train_observation_templates_v1")
SHARDS = {
    "A": ("P0S0", "P1S0"),
    "B": ("P0S1", "P1S1"),
}

FINAL_PPO_CONFIGURATION = replace(
    PAPER_ORIENTED_PPO_CANDIDATE_V1,
    configuration_id="phase8d_final_ppo_v1",
    seed=CANONICAL_PPO_SEED,
    total_timesteps=FINAL_TOTAL_TIMESTEPS,
    purpose="prespecified_final_training_equal_compute_no_test_evaluation",
)


class FinalTrainingError(RuntimeError):
    """Raised when a Phase 8D execution or integrity gate fails closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
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


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(path, canonical_json_bytes(value))


def resolved_final_configuration() -> dict[str, object]:
    payload = FINAL_PPO_CONFIGURATION.as_manifest()
    payload.update({
        "action_distribution": "DiagGaussianDistribution_for_continuous_Box_action",
        "checkpoint_interval_timesteps": CHECKPOINT_INTERVAL,
        "final_checkpoint_timestep": FINAL_TOTAL_TIMESTEPS,
        "optimizer_resolved": {
            "class": "torch.optim.Adam",
            "betas": [0.9, 0.999],
            "eps": 1e-8,
            "amsgrad": False,
            "weight_decay": FINAL_PPO_CONFIGURATION.optimizer_weight_decay,
        },
        "paper_alignment": {
            "primary_paper_report": "training epoch count of 10^6",
            "reconstruction_budget": "1,000,000 environment timesteps per condition",
            "exact_optimizer_update_equivalence_claimed": False,
        },
        "early_stopping_available": False,
        "best_checkpoint_selection_available": False,
        "hyperparameter_search_performed": False,
        "single_seed_only": True,
    })
    return payload


def final_config_sha256() -> str:
    return sha256_bytes(canonical_json_bytes(resolved_final_configuration()))


def _caseids(store: TrainRuntimeInputStore) -> tuple[str, ...]:
    caseids = tuple(row["caseid"] for row in store.rows)
    if len(caseids) != 1970 or len(set(caseids)) != 1970:
        raise FinalTrainingError("sealed train universe must contain exactly 1,970 unique cases")
    return caseids


def train_universe_sha256(caseids: Iterable[str]) -> str:
    return sha256_bytes("".join(f"{caseid}\n" for caseid in caseids).encode("ascii"))


def episode_sequence_sha256(caseids: tuple[str, ...], *, count: int = SEQUENCE_CHECKSUM_EPISODES) -> str:
    if count <= 0:
        raise FinalTrainingError("sequence checksum count must be positive")
    generator = np.random.Generator(np.random.PCG64(CANONICAL_PPO_SEED))
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


class DeterministicTrainCaseSequence:
    """An independent PCG64 stream shared by all four condition definitions."""

    def __init__(self, caseids: tuple[str, ...], *, seed: int = CANONICAL_PPO_SEED) -> None:
        if seed != CANONICAL_PPO_SEED:
            raise FinalTrainingError("final train-case sequence seed must be 42")
        if len(caseids) != 1970 or len(set(caseids)) != len(caseids):
            raise FinalTrainingError("invalid train-case sequence universe")
        self.caseids = caseids
        self.seed = seed
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
            raise FinalTrainingError("checkpoint train-case sequence seed or generator mismatch")
        if payload.get("train_universe_sha256") != train_universe_sha256(self.caseids):
            raise FinalTrainingError("checkpoint train-case universe mismatch")
        episode_index = payload.get("episode_index")
        if isinstance(episode_index, bool) or not isinstance(episode_index, int) or episode_index < 0:
            raise FinalTrainingError("checkpoint episode index is invalid")
        self.generator.bit_generator.state = payload["state"]  # type: ignore[assignment]
        self.episode_index = episode_index


class SequentialTrainRuntimeEnv(gym.Env[np.ndarray, np.ndarray]):
    """Select one sealed-train case per reset from the common deterministic stream."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        store: TrainRuntimeInputStore,
        condition_id: ConditionID | str,
        scaler: StateScaler,
        sequence: DeterministicTrainCaseSequence,
    ) -> None:
        self.store = store
        self.condition = condition_id if isinstance(condition_id, ConditionID) else ConditionID(condition_id)
        self.scaler = scaler
        self.sequence = sequence
        expected_state = "S0" if self.condition.value.endswith("S0") else "S1"
        if scaler.state_id != expected_state:
            raise FinalTrainingError("condition/scaler mismatch")
        dimension = len(scaler.fields)
        limit = np.finfo(np.float32).max
        low = np.full(dimension, -limit, dtype=np.float32)
        high = np.full(dimension, limit, dtype=np.float32)
        for index, field in enumerate(scaler.fields):
            if field.binary_unchanged:
                low[index], high[index] = 0.0, 1.0
        self.observation_space = gym.spaces.Box(low=low, high=high, dtype=np.float32)
        self.action_space = gym.spaces.Box(
            low=np.asarray([0.0], dtype=np.float32),
            high=np.asarray([27.7], dtype=np.float32),
            dtype=np.float32,
        )
        self.render_mode = None
        self._environment: gym.Env[np.ndarray, np.ndarray] | None = None
        self.test_access_count = 0

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        if seed not in (None, CANONICAL_PPO_SEED):
            raise FinalTrainingError("final environments accept seed 42 only")
        if options not in (None, {}):
            raise FinalTrainingError("final environment reset options are not supported")
        super().reset(seed=CANONICAL_PPO_SEED)
        if self._environment is not None:
            self._environment.close()
        caseid = self.sequence.next_caseid()
        self._environment = make_train_runtime_environment(
            store=self.store,
            caseid=caseid,
            condition_id=self.condition,
            scaler=self.scaler,
            seed=CANONICAL_PPO_SEED,
        )
        observation, info = self._environment.reset(seed=CANONICAL_PPO_SEED)
        info = dict(info)
        info.update({
            "phase8d_episode_index": self.sequence.episode_index - 1,
            "phase8d_test_access_count": self.test_access_count,
        })
        return observation, info

    def step(self, action: np.ndarray):
        if self._environment is None:
            raise FinalTrainingError("reset is required before final training step")
        observation, reward, terminated, truncated, info = self._environment.step(action)
        if not np.isfinite(observation).all() or not math.isfinite(float(reward)):
            raise FinalTrainingError("nonfinite environment transition")
        if not self.action_space.contains(np.asarray(action, dtype=np.float32)):
            raise FinalTrainingError("training action escaped the approved bounds")
        info = dict(info)
        info["phase8d_test_access_count"] = self.test_access_count
        info["phase8d_future_remifentanil_leakage_count"] = 0
        return observation, reward, terminated, truncated, info

    def close(self) -> None:
        if self._environment is not None:
            self._environment.close()
            self._environment = None


def _unwrap_sequence_environment(vector_environment: Any) -> SequentialTrainRuntimeEnv:
    environment = vector_environment.envs[0]
    while hasattr(environment, "env"):
        environment = environment.env
    if not isinstance(environment, SequentialTrainRuntimeEnv):
        raise FinalTrainingError("unexpected final training environment wrapper")
    return environment


def _tree_inventory(directory: Path, *, exclude: tuple[str, ...] = ()) -> tuple[str, list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix()
        if relative in exclude:
            continue
        rows.append({"relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256_path(path)})
    lines = "".join(f"{row['relative_path']}\t{row['bytes']}\t{row['sha256']}\n" for row in rows)
    return sha256_bytes(lines.encode("utf-8")), rows


def _package_versions() -> dict[str, str]:
    import gymnasium
    import stable_baselines3

    return {
        "gymnasium": gymnasium.__version__,
        "numpy": np.__version__,
        "python": platform.python_version(),
        "stable_baselines3": stable_baselines3.__version__,
        "torch": torch.__version__,
    }


class CheckpointManager:
    def __init__(
        self,
        *,
        condition_directory: Path,
        condition_id: str,
        implementation_sha: str,
        config_sha256: str,
        state_schema_sha256: str,
        runtime_root_sha256: str,
        train_universe_sha256_value: str,
        seed: int,
        total_timesteps: int,
    ) -> None:
        self.directory = condition_directory
        self.condition_id = condition_id
        self.implementation_sha = implementation_sha
        self.config_sha256 = config_sha256
        self.state_schema_sha256 = state_schema_sha256
        self.runtime_root_sha256 = runtime_root_sha256
        self.train_universe_sha256 = train_universe_sha256_value
        self.seed = seed
        self.total_timesteps = total_timesteps
        self.directory.mkdir(parents=True, exist_ok=True)

    def cleanup_partials(self) -> int:
        partials = [path for path in self.directory.iterdir() if path.name.endswith(".partial")]
        for path in partials:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        return len(partials)

    def expected_metadata(self, timestep: int) -> dict[str, object]:
        return {
            "condition_id": self.condition_id,
            "config_sha256": self.config_sha256,
            "git_implementation_sha": self.implementation_sha,
            "phase8b_private_root_sha256": PHASE8B_EXPECTED_ROOT_SHA256,
            "phase8c_private_root_sha256": self.runtime_root_sha256,
            "seed": self.seed,
            "state_schema_sha256": self.state_schema_sha256,
            "timestep": timestep,
            "total_timestep_budget": self.total_timesteps,
            "train_universe_sha256": self.train_universe_sha256,
        }

    def _checkpoint_directory(self, timestep: int) -> Path:
        return self.directory / f"checkpoint_{timestep:010d}"

    def save(self, model: PPO, sequence: DeterministicTrainCaseSequence) -> dict[str, object]:
        timestep = int(model.num_timesteps)
        if timestep <= 0 or timestep % CHECKPOINT_INTERVAL or timestep > self.total_timesteps:
            raise FinalTrainingError("checkpoint timestep is outside the exact 100,000-step schedule")
        final = self._checkpoint_directory(timestep)
        if final.exists():
            metadata = self.verify(final)
            if metadata["timestep"] != timestep:
                raise FinalTrainingError("existing checkpoint timestep mismatch")
            return metadata
        temporary = self.directory / f".{final.name}.partial"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir()
        try:
            model.save(str(temporary / "model"))
            rng_payload = {
                "numpy_global": np.random.get_state(),
                "python_random": random.getstate(),
                "torch_cpu": torch.get_rng_state(),
                "train_case_sequence": sequence.snapshot(),
            }
            atomic_bytes(temporary / "rng_state.pkl", pickle.dumps(rng_payload, protocol=5))
            metadata = self.expected_metadata(timestep)
            metadata.update({
                "checkpoint_created_timestamp_utc": utc_now(),
                "model_archive_includes_optimizer_state": True,
                "package_versions": _package_versions(),
                "resume_equivalence_boundary": "model_optimizer_rng_and_next_episode_sequence_best_effort; partial_rollout_buffer_not_restored",
            })
            atomic_json(temporary / "metadata.json", metadata)
            fingerprint, rows = _tree_inventory(temporary)
            atomic_json(temporary / "COMPLETE.json", {
                "checkpoint_root_sha256": fingerprint,
                "complete": True,
                "files": rows,
            })
            os.replace(temporary, final)
        except BaseException:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
        self._write_manifest()
        return metadata

    def verify(self, directory: Path) -> dict[str, object]:
        complete_path = directory / "COMPLETE.json"
        if not complete_path.is_file():
            raise FinalTrainingError(f"incomplete checkpoint: {directory.name}")
        complete = json.loads(complete_path.read_text(encoding="utf-8"))
        fingerprint, rows = _tree_inventory(directory, exclude=("COMPLETE.json",))
        if complete.get("complete") is not True or complete.get("checkpoint_root_sha256") != fingerprint:
            raise FinalTrainingError(f"corrupt checkpoint: {directory.name}")
        if complete.get("files") != rows:
            raise FinalTrainingError(f"checkpoint inventory mismatch: {directory.name}")
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        timestep = metadata.get("timestep")
        if isinstance(timestep, bool) or not isinstance(timestep, int):
            raise FinalTrainingError("checkpoint timestep is invalid")
        expected = self.expected_metadata(timestep)
        for key, value in expected.items():
            if metadata.get(key) != value:
                raise FinalTrainingError(f"checkpoint {key} mismatch")
        if timestep % CHECKPOINT_INTERVAL or timestep > self.total_timesteps:
            raise FinalTrainingError("checkpoint is outside the requested schedule")
        return metadata

    def checkpoints(self) -> list[tuple[int, Path, dict[str, object]]]:
        result = []
        for path in sorted(self.directory.glob("checkpoint_*")):
            if path.name == "checkpoint_manifest.json":
                continue
            if not path.is_dir():
                raise FinalTrainingError("checkpoint path is not a directory")
            metadata = self.verify(path)
            result.append((int(metadata["timestep"]), path, metadata))
        return result

    def latest(self) -> tuple[int, Path, dict[str, object]] | None:
        rows = self.checkpoints()
        return rows[-1] if rows else None

    def _write_manifest(self) -> None:
        rows = []
        for timestep, path, metadata in self.checkpoints():
            rows.append({
                "checkpoint_directory": path.name,
                "checkpoint_root_sha256": json.loads((path / "COMPLETE.json").read_text(encoding="utf-8"))["checkpoint_root_sha256"],
                "model_sha256": sha256_path(path / "model.zip"),
                "timestep": timestep,
                "created_timestamp_utc": metadata["checkpoint_created_timestamp_utc"],
            })
        atomic_json(self.directory / "checkpoint_manifest.json", {"checkpoints": rows})

    def load_rng(self, checkpoint_directory: Path, sequence: DeterministicTrainCaseSequence) -> None:
        with (checkpoint_directory / "rng_state.pkl").open("rb") as stream:
            payload = pickle.load(stream)
        random.setstate(payload["python_random"])
        np.random.set_state(payload["numpy_global"])
        torch.set_rng_state(payload["torch_cpu"])
        sequence.restore(payload["train_case_sequence"])

    def finalize(self, model: PPO, *, started_timestamp_utc: str, wall_clock_seconds: float, resumed: bool) -> dict[str, object]:
        if int(model.num_timesteps) != self.total_timesteps:
            raise FinalTrainingError("final model timestep is not exactly 1,000,000")
        checkpoint = self._checkpoint_directory(self.total_timesteps)
        self.verify(checkpoint)
        model_source = checkpoint / "model.zip"
        atomic_bytes(self.directory / "final_model.zip", model_source.read_bytes())
        optimizer_temporary = self.directory / ".final_optimizer_state.pt.partial"
        torch.save(model.policy.optimizer.state_dict(), optimizer_temporary)
        os.replace(optimizer_temporary, self.directory / "final_optimizer_state.pt")
        completion = {
            **self.expected_metadata(self.total_timesteps),
            "completed": True,
            "end_timestamp_utc": utc_now(),
            "final_model_sha256": sha256_path(self.directory / "final_model.zip"),
            "final_optimizer_state_sha256": sha256_path(self.directory / "final_optimizer_state.pt"),
            "package_versions": _package_versions(),
            "resume_occurred": resumed,
            "start_timestamp_utc": started_timestamp_utc,
            "test_access_count": 0,
            "wall_clock_seconds": wall_clock_seconds,
        }
        fingerprint, rows = _tree_inventory(self.directory, exclude=("OUTPUT_COMPLETE.json",))
        completion["output_root_sha256"] = fingerprint
        completion["output_files"] = rows
        atomic_json(self.directory / "OUTPUT_COMPLETE.json", completion)
        return completion

    def verify_completion(self) -> dict[str, object]:
        path = self.directory / "OUTPUT_COMPLETE.json"
        if not path.is_file():
            raise FinalTrainingError("final completion marker is missing")
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected = self.expected_metadata(self.total_timesteps)
        for key, value in expected.items():
            if payload.get(key) != value:
                raise FinalTrainingError(f"final output {key} mismatch")
        fingerprint, rows = _tree_inventory(self.directory, exclude=("OUTPUT_COMPLETE.json",))
        if payload.get("output_root_sha256") != fingerprint or payload.get("output_files") != rows:
            raise FinalTrainingError("final output root checksum mismatch")
        if payload.get("final_model_sha256") != sha256_path(self.directory / "final_model.zip"):
            raise FinalTrainingError("final model checksum mismatch")
        if payload.get("test_access_count") != 0:
            raise FinalTrainingError("test access was recorded in final output")
        return payload


def _finite_model_diagnostics(model: PPO) -> tuple[bool, bool, float]:
    parameters_finite = all(torch.isfinite(parameter).all().item() for parameter in model.policy.parameters())
    gradients = [parameter.grad for parameter in model.policy.parameters() if parameter.grad is not None]
    gradients_finite = all(torch.isfinite(gradient).all().item() for gradient in gradients)
    gradient_norm = math.sqrt(sum(float(torch.sum(gradient.detach() ** 2).item()) for gradient in gradients)) if gradients else 0.0
    return bool(parameters_finite), bool(gradients_finite), gradient_norm


class FinalTrainingCallback(BaseCallback):
    """Fail closed on nonfinite transitions and save exact private checkpoints."""

    def __init__(self, manager: CheckpointManager, *, target_timestep: int) -> None:
        super().__init__(verbose=0)
        self.manager = manager
        self.target_timestep = target_timestep
        self.episode_count = 0
        self.episode_returns: list[float] = []
        self.episode_lengths: list[int] = []
        self._current_return = 0.0
        self._current_length = 0
        self.last_checkpoint = 0

    def _progress(self, event: str) -> None:
        parameters_finite, gradients_finite, gradient_norm = _finite_model_diagnostics(self.model)
        values = self.model.logger.name_to_value
        numeric = {
            key: float(value)
            for key, value in values.items()
            if isinstance(value, (int, float, np.floating)) and key.startswith(("train/", "rollout/"))
        }
        if not all(math.isfinite(value) for value in numeric.values()):
            raise FinalTrainingError("nonfinite PPO logger diagnostic")
        if not parameters_finite or not gradients_finite or not math.isfinite(gradient_norm):
            raise FinalTrainingError("nonfinite PPO parameter or gradient diagnostic")
        row = {
            "approx_kl": numeric.get("train/approx_kl"),
            "clip_fraction": numeric.get("train/clip_fraction"),
            "entropy_loss": numeric.get("train/entropy_loss"),
            "episode_count": self.episode_count,
            "episode_length_mean": None if not self.episode_lengths else float(np.mean(self.episode_lengths[-100:])),
            "event": event,
            "explained_variance": numeric.get("train/explained_variance"),
            "gradient_norm": gradient_norm,
            "learning_rate": numeric.get("train/learning_rate", FINAL_PPO_CONFIGURATION.learning_rate),
            "parameters_finite": parameters_finite,
            "policy_gradient_loss": numeric.get("train/policy_gradient_loss"),
            "rollout_return_mean": None if not self.episode_returns else float(np.mean(self.episode_returns[-100:])),
            "timestep": int(self.model.num_timesteps),
            "value_loss": numeric.get("train/value_loss"),
            "wall_clock_timestamp_utc": utc_now(),
        }
        progress = self.manager.directory / "progress.jsonl"
        with progress.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _on_rollout_start(self) -> None:
        if self.model.num_timesteps:
            self._progress("rollout_start_after_update")

    def _on_step(self) -> bool:
        for key in ("new_obs", "actions", "rewards"):
            value = self.locals.get(key)
            if value is not None and not np.isfinite(np.asarray(value)).all():
                raise FinalTrainingError(f"nonfinite callback {key}")
        infos = self.locals.get("infos") or []
        if any(info.get("phase8d_test_access_count", 0) != 0 for info in infos):
            raise FinalTrainingError("test access detected during final training")
        if any(info.get("phase8d_future_remifentanil_leakage_count", 0) != 0 for info in infos):
            raise FinalTrainingError("future remifentanil leakage detected")
        rewards = np.asarray(self.locals.get("rewards", [0.0]), dtype=float)
        self._current_return += float(rewards[0])
        self._current_length += 1
        dones = np.asarray(self.locals.get("dones", [False]), dtype=bool)
        if bool(dones[0]):
            self.episode_count += 1
            self.episode_returns.append(self._current_return)
            self.episode_lengths.append(self._current_length)
            self._current_return = 0.0
            self._current_length = 0
        timestep = int(self.model.num_timesteps)
        if timestep % CHECKPOINT_INTERVAL == 0 and timestep > self.last_checkpoint:
            sequence = _unwrap_sequence_environment(self.training_env).sequence
            self.manager.save(self.model, sequence)
            self._progress("checkpoint")
            self.last_checkpoint = timestep
        return timestep < self.target_timestep


def _set_global_seed(seed: int) -> None:
    if seed != CANONICAL_PPO_SEED:
        raise FinalTrainingError("final PPO seed must be 42")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)


def validate_output_root(repository_root: Path, output_root: Path) -> Path:
    root = repository_root.resolve()
    resolved = output_root.resolve()
    processed = (root / "data/processed").resolve()
    try:
        resolved.relative_to(processed)
    except ValueError as error:
        raise FinalTrainingError("Phase 8D output root must be inside repository data/processed") from error
    relative = resolved.relative_to(root).as_posix()
    ignored = subprocess.run(["git", "check-ignore", "-q", relative], cwd=root, check=False)
    if ignored.returncode != 0:
        raise FinalTrainingError("Phase 8D output root is not Git-ignored")
    tracked = subprocess.check_output(["git", "ls-files", relative], cwd=root, text=True).splitlines()
    if tracked:
        raise FinalTrainingError("Phase 8D output root contains Git-tracked files")
    return resolved


def verify_repository_gate(repository_root: Path, *, expected_git_sha: str, output_root: Path) -> dict[str, object]:
    root = repository_root.resolve()
    current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if current_commit != expected_git_sha:
        raise FinalTrainingError("current HEAD differs from the expected implementation SHA")
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, text=True).splitlines()
    if status:
        raise FinalTrainingError("repository source worktree or index is not clean")
    validate_output_root(root, output_root)
    phase8b = json.loads((root / PHASE8B_PRIVATE_ROOT_RELATIVE / "STORE_COMPLETE.json").read_text(encoding="utf-8"))
    phase8c = json.loads((root / PHASE8C_PRIVATE_ROOT_RELATIVE / "STORE_COMPLETE.json").read_text(encoding="utf-8"))
    if phase8b.get("private_template_store_root_sha256") != PHASE8B_EXPECTED_ROOT_SHA256:
        raise FinalTrainingError("Phase 8B private root mismatch")
    if phase8c.get("private_runtime_root_sha256") != PHASE8C_EXPECTED_ROOT_SHA256:
        raise FinalTrainingError("Phase 8C private root mismatch")
    if phase8b.get("test_template_count") != 0 or phase8c.get("test_bundle_count") != 0:
        raise FinalTrainingError("test private artifact detected")
    seal = json.loads((root / "data/manifests/phase8a_test_seal.json").read_text(encoding="utf-8"))
    if seal.get("seal_payload_sha256") != PHASE8A_SEAL_PAYLOAD_SHA256:
        raise FinalTrainingError("Phase 8A seal mismatch")
    if sha256_path(root / "data/manifests/phase8a_train_case_ids.csv") != PHASE8A_TRAIN_CASE_IDS_SHA256:
        raise FinalTrainingError("Phase 8A train-case manifest mismatch")
    config_path = root / FINAL_CONFIG_RELATIVE
    if not config_path.is_file() or sha256_path(config_path) != sha256_bytes(canonical_json_bytes(resolved_final_configuration())):
        raise FinalTrainingError("resolved Phase 8D PPO config checksum mismatch")
    return {
        "git_implementation_sha": current_commit,
        "phase8b_private_root_sha256": PHASE8B_EXPECTED_ROOT_SHA256,
        "phase8c_private_root_sha256": PHASE8C_EXPECTED_ROOT_SHA256,
        "test_access_count": 0,
    }


def make_sequence_environment(
    *,
    store: TrainRuntimeInputStore,
    condition_id: str,
    scaler: StateScaler,
    sequence: DeterministicTrainCaseSequence,
) -> SequentialTrainRuntimeEnv:
    return SequentialTrainRuntimeEnv(store=store, condition_id=condition_id, scaler=scaler, sequence=sequence)


def run_condition_preflight(
    *,
    repository_root: Path,
    condition_id: str,
    store: TrainRuntimeInputStore,
    scaler: StateScaler,
    timesteps: int = 1024,
) -> dict[str, object]:
    """Run a bounded real-train preflight with no persistence."""

    if timesteps != 1024:
        raise FinalTrainingError("Phase 8D preflight is fixed at 1,024 timesteps")
    _set_global_seed(CANONICAL_PPO_SEED)
    caseids = _caseids(store)
    sequence = DeterministicTrainCaseSequence(caseids)
    environment = DummyVecEnv([
        lambda: make_sequence_environment(
            store=store,
            condition_id=condition_id,
            scaler=scaler,
            sequence=sequence,
        )
    ])
    # The bounded preflight uses a one-rollout 1,024-step buffer so that it
    # executes one real optimizer update while all scientific hyperparameters
    # and network settings remain identical to the final configuration.
    preflight_configuration = replace(
        FINAL_PPO_CONFIGURATION,
        configuration_id="phase8d_preflight_1024_v1",
        n_steps=1024,
        total_timesteps=1024,
        purpose="bounded_preflight_not_final_training",
    )
    model = make_ppo_model(environment, preflight_configuration)
    started = time.perf_counter()
    model.learn(total_timesteps=timesteps, reset_num_timesteps=True, progress_bar=False)
    wall = time.perf_counter() - started
    if int(model.num_timesteps) != timesteps:
        raise FinalTrainingError("Phase 8D preflight timestep mismatch")
    parameters_finite, gradients_finite, gradient_norm = _finite_model_diagnostics(model)
    losses = {
        key: float(value)
        for key, value in model.logger.name_to_value.items()
        if key.startswith("train/") and isinstance(value, (int, float, np.floating))
    }
    losses_finite = bool(losses) and all(math.isfinite(value) for value in losses.values())
    result = {
        "condition_id": condition_id,
        "episode_sequence_prefix_sha256": sha256_bytes(canonical_json_bytes(sequence.snapshot()["state"])),
        "final_checkpoint_created": False,
        "gradient_norm_finite": math.isfinite(gradient_norm),
        "gradients_finite": gradients_finite,
        "learn_completed": True,
        "logged_training_values_finite": losses_finite,
        "model_or_checkpoint_persisted": False,
        "observation_dimension": len(scaler.fields),
        "parameters_finite": parameters_finite,
        "preflight_rollout_length_override": 1024,
        "seed": CANONICAL_PPO_SEED,
        "status": "passed",
        "test_access_count": 0,
        "timesteps": int(model.num_timesteps),
        "wall_clock_seconds": wall,
    }
    environment.close()
    del model
    if not all((parameters_finite, gradients_finite, losses_finite, math.isfinite(gradient_norm))):
        raise FinalTrainingError("nonfinite Phase 8D preflight diagnostic")
    return result


def train_condition(
    *,
    repository_root: Path,
    output_root: Path,
    expected_git_sha: str,
    condition_id: str,
    store: TrainRuntimeInputStore,
    scaler: StateScaler,
    resume: bool,
    total_timesteps: int = FINAL_TOTAL_TIMESTEPS,
    seed: int = CANONICAL_PPO_SEED,
) -> dict[str, object]:
    if total_timesteps != FINAL_TOTAL_TIMESTEPS or seed != CANONICAL_PPO_SEED:
        raise FinalTrainingError("final budget and seed are fixed at 1,000,000 and 42")
    condition = ConditionID(condition_id).value
    caseids = _caseids(store)
    universe_sha = train_universe_sha256(caseids)
    sequence = DeterministicTrainCaseSequence(caseids, seed=seed)
    condition_directory = output_root / condition / f"seed_{seed}"
    manager = CheckpointManager(
        condition_directory=condition_directory,
        condition_id=condition,
        implementation_sha=expected_git_sha,
        config_sha256=final_config_sha256(),
        state_schema_sha256=scaler.schema_sha256,
        runtime_root_sha256=PHASE8C_EXPECTED_ROOT_SHA256,
        train_universe_sha256_value=universe_sha,
        seed=seed,
        total_timesteps=total_timesteps,
    )
    partials_removed = manager.cleanup_partials()
    if (condition_directory / "OUTPUT_COMPLETE.json").is_file():
        payload = manager.verify_completion()
        payload["already_complete"] = True
        payload["partials_removed_before_verify"] = partials_removed
        return payload
    latest = manager.latest()
    if latest is not None and not resume:
        raise FinalTrainingError("valid checkpoint exists but --resume was not supplied")
    _set_global_seed(seed)
    vector_environment = DummyVecEnv([
        lambda: make_sequence_environment(
            store=store,
            condition_id=condition,
            scaler=scaler,
            sequence=sequence,
        )
    ])
    resumed = latest is not None
    if latest is None:
        model = make_ppo_model(vector_environment, FINAL_PPO_CONFIGURATION)
        starting_timestep = 0
    else:
        starting_timestep, checkpoint_directory, _ = latest
        manager.load_rng(checkpoint_directory, sequence)
        model = PPO.load(str(checkpoint_directory / "model.zip"), env=vector_environment, device="cpu")
        if int(model.num_timesteps) != starting_timestep:
            raise FinalTrainingError("loaded model timestep differs from checkpoint metadata")
    atomic_json(condition_directory / "resolved_config.json", resolved_final_configuration())
    atomic_json(condition_directory / "training_schedule.json", {
        "checkpoint_interval": CHECKPOINT_INTERVAL,
        "condition_id": condition,
        "episode_sequence_sha256": episode_sequence_sha256(caseids),
        "seed": seed,
        "total_timesteps": total_timesteps,
        "train_universe_sha256": universe_sha,
    })
    started_timestamp = utc_now()
    started = time.perf_counter()
    callback = FinalTrainingCallback(manager, target_timestep=total_timesteps)
    callback.last_checkpoint = starting_timestep
    remaining = total_timesteps - starting_timestep
    if remaining <= 0:
        raise FinalTrainingError("latest checkpoint is not below an incomplete requested budget")
    model.learn(
        total_timesteps=remaining,
        reset_num_timesteps=starting_timestep == 0,
        callback=callback,
        progress_bar=False,
    )
    wall = time.perf_counter() - started
    if int(model.num_timesteps) != total_timesteps:
        raise FinalTrainingError("final callback did not stop at exactly 1,000,000 timesteps")
    completion = manager.finalize(model, started_timestamp_utc=started_timestamp, wall_clock_seconds=wall, resumed=resumed)
    completion.update({
        "already_complete": False,
        "partials_removed_before_training": partials_removed,
        "starting_timestep": starting_timestep,
    })
    vector_environment.close()
    del model
    return completion


def verify_private_outputs(
    *,
    repository_root: Path,
    output_root: Path,
    expected_git_sha: str,
    conditions: Iterable[str],
) -> dict[str, object]:
    store = TrainRuntimeInputStore(repository_root / PHASE8C_PRIVATE_ROOT_RELATIVE, repository_root)
    scalers = load_scaler_registry(repository_root / SCALER_REGISTRY_RELATIVE)
    caseids = _caseids(store)
    results = []
    for condition in conditions:
        state = "S0" if condition.endswith("S0") else "S1"
        manager = CheckpointManager(
            condition_directory=output_root / condition / f"seed_{CANONICAL_PPO_SEED}",
            condition_id=condition,
            implementation_sha=expected_git_sha,
            config_sha256=final_config_sha256(),
            state_schema_sha256=scalers[state].schema_sha256,
            runtime_root_sha256=PHASE8C_EXPECTED_ROOT_SHA256,
            train_universe_sha256_value=train_universe_sha256(caseids),
            seed=CANONICAL_PPO_SEED,
            total_timesteps=FINAL_TOTAL_TIMESTEPS,
        )
        checkpoints = manager.checkpoints() if manager.directory.exists() else []
        completion = manager.verify_completion() if (manager.directory / "OUTPUT_COMPLETE.json").is_file() else None
        results.append({
            "condition_id": condition,
            "checkpoint_timesteps": [row[0] for row in checkpoints],
            "complete": completion is not None,
            "final_model_sha256": None if completion is None else completion["final_model_sha256"],
            "output_root_sha256": None if completion is None else completion["output_root_sha256"],
        })
    return {"conditions": results, "test_access_count": 0}

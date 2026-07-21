"""Fail-closed Phase 8E final-policy evaluation infrastructure."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from vitaldb_state_selection.cohort.test_runtime_inputs import (
    EXPECTED_TEST_CASES,
    TestRuntimeInputStore,
    load_scaler_registry,
    sha256_path,
)


CONDITIONS = ("P0S0", "P1S0", "P0S1", "P1S1")
TRAINING_IMPLEMENTATION_SHA = "b782b5e4a9d418f6b907a87d046c4e9789a3e5f0"
FINAL_CONFIG_SHA256 = "b5d79a2fb8be3b5337c7cb807936247c630b86f108f2a92cc6f645023f789b3e"
FINAL_TIMESTEP = 1_000_000
SEED = 42
METRIC_VERSION = "phase8e-control-metrics-v1"
METRIC_NAMES = (
    "mean_absolute_bis_deviation",
    "root_mean_squared_bis_deviation",
    "time_in_bis_40_60_seconds",
    "time_below_bis_40_seconds",
    "time_above_bis_60_seconds",
    "integrated_absolute_bis_error_bis_seconds",
    "maximum_absolute_bis_deviation",
    "cumulative_propofol_amount_mg",
    "mean_propofol_infusion_rate_mg_per_min",
    "action_change_magnitude_mg_per_min",
    "cumulative_episode_reward",
)


class FinalEvaluationError(RuntimeError):
    """Raised before policy loading when evaluation prerequisites are incomplete."""


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


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


def metric_manifest() -> dict[str, object]:
    return {
        "action_change_definition": "mean_absolute_difference_between_consecutive_propofol_rates",
        "action_interval_seconds": 10.0,
        "bis_source_for_control_metrics": "simulator_latent_true_bis",
        "bis_target": 50.0,
        "episode_failure_is_never_silently_excluded": True,
        "metric_names": list(METRIC_NAMES),
        "metric_version": METRIC_VERSION,
        "observation_visibility_is_not_an_outcome": True,
        "target_range": {"inclusive_lower": 40.0, "inclusive_upper": 60.0},
    }


def compute_case_metrics(
    latent_bis: Sequence[float],
    propofol_rate_mg_per_min: Sequence[float],
    rewards: Sequence[float],
    *,
    step_seconds: float = 10.0,
    episode_completed: bool = True,
    failure_reason: str = "",
) -> dict[str, object]:
    bis = np.asarray(latent_bis, dtype=np.float64)
    rates = np.asarray(propofol_rate_mg_per_min, dtype=np.float64)
    reward = np.asarray(rewards, dtype=np.float64)
    if bis.ndim != 1 or bis.size == 0 or rates.shape != bis.shape or reward.shape != bis.shape:
        raise FinalEvaluationError("metric trajectory shape mismatch")
    if not np.isfinite(bis).all() or not np.isfinite(rates).all() or not np.isfinite(reward).all():
        raise FinalEvaluationError("metric trajectory contains non-finite values")
    if step_seconds != 10.0 or np.any(rates < 0):
        raise FinalEvaluationError("metric interval or action invariant mismatch")
    deviation = np.abs(bis - 50.0)
    duration_minutes = bis.size * step_seconds / 60.0
    return {
        "action_change_magnitude_mg_per_min": float(np.abs(np.diff(rates)).mean()) if rates.size > 1 else 0.0,
        "cumulative_episode_reward": float(reward.sum()),
        "cumulative_propofol_amount_mg": float(rates.sum() * step_seconds / 60.0),
        "episode_completed": bool(episode_completed),
        "episode_failure_reason": str(failure_reason),
        "integrated_absolute_bis_error_bis_seconds": float(deviation.sum() * step_seconds),
        "maximum_absolute_bis_deviation": float(deviation.max()),
        "mean_absolute_bis_deviation": float(deviation.mean()),
        "mean_propofol_infusion_rate_mg_per_min": float(rates.sum() * step_seconds / 60.0 / duration_minutes),
        "root_mean_squared_bis_deviation": float(np.sqrt(np.mean(np.square(bis - 50.0)))),
        "time_above_bis_60_seconds": float((bis > 60.0).sum() * step_seconds),
        "time_below_bis_40_seconds": float((bis < 40.0).sum() * step_seconds),
        "time_in_bis_40_60_seconds": float(((bis >= 40.0) & (bis <= 60.0)).sum() * step_seconds),
    }


@dataclass(frozen=True, slots=True)
class VerifiedModel:
    condition_id: str
    directory: Path
    final_model_path: Path
    final_model_sha256: str
    state_schema_sha256: str


def verify_final_model(models_root: Path, condition: str, *, expected_training_sha: str) -> VerifiedModel:
    if condition not in CONDITIONS:
        raise FinalEvaluationError(f"unknown final condition: {condition}")
    directory = models_root / condition / "seed_42"
    marker_path = directory / "OUTPUT_COMPLETE.json"
    if not marker_path.is_file():
        raise FinalEvaluationError(f"missing final completion marker: {condition}")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    required = {
        "completed": True,
        "condition_id": condition,
        "config_sha256": FINAL_CONFIG_SHA256,
        "git_implementation_sha": expected_training_sha,
        "seed": SEED,
        "timestep": FINAL_TIMESTEP,
        "total_timestep_budget": FINAL_TIMESTEP,
        "test_access_count": 0,
    }
    for field, expected in required.items():
        if marker.get(field) != expected:
            raise FinalEvaluationError(f"final model metadata mismatch: {condition}: {field}")
    final_path = directory / "final_model.zip"
    if not final_path.is_file():
        raise FinalEvaluationError(f"final model file missing: {condition}")
    observed = sha256_path(final_path)
    if observed != marker.get("final_model_sha256"):
        raise FinalEvaluationError(f"final model checksum mismatch: {condition}")
    checkpoint_marker = directory / "checkpoint_0001000000" / "COMPLETE.json"
    checkpoint_model = directory / "checkpoint_0001000000" / "model.zip"
    if not checkpoint_marker.is_file() or not checkpoint_model.is_file() or sha256_path(checkpoint_model) != observed:
        raise FinalEvaluationError(f"final one-million checkpoint mismatch: {condition}")
    manifest = json.loads((directory / "checkpoint_manifest.json").read_text(encoding="utf-8"))
    timesteps = [int(row["timestep"]) for row in manifest["checkpoints"]]
    if timesteps != list(range(100_000, 1_000_001, 100_000)):
        raise FinalEvaluationError(f"checkpoint sequence mismatch: {condition}")
    return VerifiedModel(condition, directory, final_path, observed, str(marker["state_schema_sha256"]))


def verify_four_models(models_root: Path | str, *, expected_training_sha: str = TRAINING_IMPLEMENTATION_SHA) -> list[VerifiedModel]:
    if expected_training_sha != TRAINING_IMPLEMENTATION_SHA:
        raise FinalEvaluationError("training implementation SHA mismatch")
    models = [verify_final_model(Path(models_root), condition, expected_training_sha=expected_training_sha) for condition in CONDITIONS]
    return models


def verify_evaluation_inputs(
    repository_root: Path | str,
    test_runtime_root: Path | str,
) -> dict[str, object]:
    root = Path(repository_root)
    store = TestRuntimeInputStore(test_runtime_root, root)
    caseids = [row["caseid"] for row in store.rows]
    if len(caseids) != EXPECTED_TEST_CASES or len(set(caseids)) != EXPECTED_TEST_CASES:
        raise FinalEvaluationError("sealed-test evaluation accounting mismatch")
    private_root = store.verify_all()
    scalers = load_scaler_registry(root / "data/manifests/phase8c_scaler_registry.json")
    if len(scalers["S0"].fields) != 34 or len(scalers["S1"].fields) != 42:
        raise FinalEvaluationError("train scaler dimension mismatch")
    return {
        "case_count": EXPECTED_TEST_CASES,
        "case_order_sha256": hashlib.sha256("".join(f"{caseid}\n" for caseid in caseids).encode("ascii")).hexdigest(),
        "condition_order": list(CONDITIONS),
        "deterministic_inference": True,
        "episode_execution_count": 0,
        "private_runtime_root_sha256": private_root,
        "scaler_fit_or_update_allowed": False,
        "test_access_during_verify_only": 0,
    }


def execute_evaluation(
    *,
    repository_root: Path | str,
    models_root: Path | str,
    test_runtime_root: Path | str,
    output_root: Path | str,
    expected_training_sha: str,
    seed: int,
) -> dict[str, object]:
    """Execute only after explicit CLI --execute; never called by preparation."""

    if seed != SEED:
        raise FinalEvaluationError("final evaluation seed must be 42")
    verified = verify_four_models(models_root, expected_training_sha=expected_training_sha)
    inputs = verify_evaluation_inputs(repository_root, test_runtime_root)
    # Imports remain behind the execute gate so verify-only cannot load a model.
    from stable_baselines3 import PPO
    from vitaldb_state_selection.rl_integration.train_runtime import make_train_runtime_environment

    root = Path(repository_root)
    store = TestRuntimeInputStore(test_runtime_root, root)
    scalers = load_scaler_registry(root / "data/manifests/phase8c_scaler_registry.json")
    output = Path(output_root)
    rows: list[dict[str, object]] = []
    for model_record in verified:
        model = PPO.load(model_record.final_model_path, device="cpu")
        before = sha256_path(model_record.final_model_path)
        scaler = scalers["S0" if model_record.condition_id.endswith("S0") else "S1"]
        for index_row in store.rows:
            environment = make_train_runtime_environment(
                store=store,
                caseid=index_row["caseid"],
                condition_id=model_record.condition_id,
                scaler=scaler,
                seed=seed,
            )
            observation, _ = environment.reset(seed=seed)
            latent: list[float] = []
            rates: list[float] = []
            rewards: list[float] = []
            terminated = truncated = False
            failure = ""
            try:
                while not (terminated or truncated):
                    action, _ = model.predict(observation, deterministic=True)
                    observation, reward, terminated, truncated, info = environment.step(action)
                    latent.append(float(info["latent_true_bis"]))
                    rates.append(float(info["propofol_rate_mg_per_min"]))
                    rewards.append(float(reward))
            except Exception as error:
                failure = f"{type(error).__name__}: {error}"
            finally:
                environment.close()
            metrics = (
                compute_case_metrics(latent, rates, rewards, episode_completed=not failure, failure_reason=failure)
                if latent
                else {**{name: None for name in METRIC_NAMES}, "episode_completed": False, "episode_failure_reason": failure}
            )
            rows.append({"caseid": index_row["caseid"], "subjectid": index_row["subjectid"], "condition_id": model_record.condition_id, **metrics})
        if sha256_path(model_record.final_model_path) != before:
            raise FinalEvaluationError("model changed during deterministic evaluation")
    # Case-level output is deliberately private and atomically written.
    fieldnames = ("caseid", "subjectid", "condition_id", *METRIC_NAMES, "episode_completed", "episode_failure_reason")
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(output / "case_level_metrics.csv", stream.getvalue().encode("utf-8"))
    return {**inputs, "episode_execution_count": len(rows), "case_condition_rows": len(rows)}

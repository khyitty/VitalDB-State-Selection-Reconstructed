"""Bounded synthetic PPO interface smoke execution; no performance analysis."""

from __future__ import annotations

import hashlib
import math
import random
import time
import tracemalloc
from typing import Any

import numpy as np
import torch

from vitaldb_state_selection.anesthesia import (
    BISEvent, ConditionID, PiecewiseConstantRemifentanilSchedule, SQIEvent,
    SyntheticObservationTemplate,
)
from vitaldb_state_selection.pkpd import PatientProfile, Sex

from .config import PPO_INTEGRATION_SMOKE_V1, make_ppo_model
from .factory import make_gymnasium_environment


SMOKE_PROFILE = PatientProfile(age_years=45.0, sex=Sex.FEMALE, height_cm=165.0, weight_kg=60.0)
SMOKE_TEMPLATE = SyntheticObservationTemplate(
    template_id="phase7h-synthetic-smoke-template-v1",
    episode_horizon_seconds=3600.0,
    bis_events=tuple(BISEvent(float(t)) for t in range(0, 361, 10)),
    sqi_events=tuple(SQIEvent(float(t), 80.0 if t % 40 else 40.0) for t in range(0, 361, 10)),
)
SMOKE_SCHEDULE = PiecewiseConstantRemifentanilSchedule(((0.0, 0.0), (40.0, 2.0), (90.0, 1.0)))


def _parameter_checksum(model: Any) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.policy.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def run_condition_smoke(condition_id: ConditionID | str) -> dict[str, Any]:
    """Run exactly 128 library timesteps for one synthetic condition."""

    condition = condition_id if isinstance(condition_id, ConditionID) else ConditionID(condition_id)
    configuration = PPO_INTEGRATION_SMOKE_V1
    random.seed(configuration.seed)
    np.random.seed(configuration.seed)
    torch.manual_seed(configuration.seed)
    torch.set_num_threads(1)
    environment = make_gymnasium_environment(
        condition_id=condition,
        patient_profile=SMOKE_PROFILE,
        observation_template=SMOKE_TEMPLATE,
        remifentanil_schedule=SMOKE_SCHEDULE,
        seed=configuration.seed,
        episode_horizon_seconds=360.0,
    )
    observation, _ = environment.reset(seed=configuration.seed)
    model = make_ppo_model(environment, configuration)
    first_action, _ = model.predict(observation, deterministic=True)
    if first_action.shape != (1,) or not np.isfinite(first_action).all():
        raise RuntimeError("deterministic smoke prediction is not a finite shape-(1,) action")
    tracemalloc.start()
    started = time.perf_counter()
    model.learn(total_timesteps=configuration.total_timesteps, reset_num_timesteps=True, progress_bar=False)
    runtime_seconds = time.perf_counter() - started
    _, peak_traced_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if model.num_timesteps != configuration.total_timesteps:
        raise RuntimeError("bounded smoke did not execute exactly 128 timesteps")
    parameters_finite = all(torch.isfinite(parameter).all().item() for parameter in model.policy.parameters())
    gradients = [parameter.grad for parameter in model.policy.parameters() if parameter.grad is not None]
    gradients_finite = all(torch.isfinite(gradient).all().item() for gradient in gradients)
    logged_losses = [
        float(value) for key, value in model.logger.name_to_value.items()
        if key.startswith("train/") and "loss" in key and isinstance(value, (int, float, np.floating))
    ]
    losses_finite = bool(logged_losses) and all(math.isfinite(value) for value in logged_losses)
    result = {
        "condition_id": condition.value,
        "status": "passed",
        "seed": configuration.seed,
        "device": str(model.device),
        "total_timesteps": int(model.num_timesteps),
        "runtime_seconds": runtime_seconds,
        "peak_traced_python_memory_bytes": int(peak_traced_bytes),
        "observation_shape": list(observation.shape),
        "action_shape": list(first_action.shape),
        "first_deterministic_action_finite": True,
        "initial_observation_sha256": hashlib.sha256(observation.tobytes()).hexdigest(),
        "first_deterministic_action_sha256": hashlib.sha256(np.asarray(first_action).tobytes()).hexdigest(),
        "parameters_finite": bool(parameters_finite),
        "gradients_finite_where_present": bool(gradients_finite),
        "finite_logged_loss_count": len(logged_losses),
        "logged_losses_finite": bool(losses_finite),
        "environment_core_clip_count": environment.core._saturation_count,
        "model_parameter_sha256": _parameter_checksum(model),
        "checkpoint_created": False,
        "performance_metrics_recorded": False,
    }
    environment.close()
    if not all((result["parameters_finite"], result["gradients_finite_where_present"], result["logged_losses_finite"])):
        raise RuntimeError("nonfinite PPO smoke diagnostic")
    if result["environment_core_clip_count"] != 0:
        raise RuntimeError("normal adapter smoke invoked the core clipping guard")
    return result

"""Fail-closed Phase 8E final-policy evaluation infrastructure."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from vitaldb_state_selection.cohort.test_runtime_inputs import (
    EXPECTED_TEST_CASES,
    TestRuntimeInputStore,
    load_scaler_registry,
    sha256_path,
)
from vitaldb_state_selection.rl_integration.final_training import _tree_inventory


CONDITIONS = ("P0S0", "P1S0", "P0S1", "P1S1")
TRAINING_IMPLEMENTATION_SHA = "b782b5e4a9d418f6b907a87d046c4e9789a3e5f0"
FINAL_CONFIG_SHA256 = "b5d79a2fb8be3b5337c7cb807936247c630b86f108f2a92cc6f645023f789b3e"
FINAL_TIMESTEP = 1_000_000
SEED = 42
ALLOWED_EVALUATION_SEEDS = (42, 43, 44)
TRAINING_IMPLEMENTATION_SHA_BY_SEED = {
    42: TRAINING_IMPLEMENTATION_SHA,
    43: "bffcafe7d6c01cc0190b6f3abfe3e2b13a7f8bd6",
    44: "bffcafe7d6c01cc0190b6f3abfe3e2b13a7f8bd6",
}
EVALUATION_CONFIG_SHA256_BY_SEED = {
    42: FINAL_CONFIG_SHA256,
    43: "1329282fb84e31e9667c1fcf2d3b3e3e488340c5a527831477c9b031c2f32ff8",
    44: "f673781ee526e0290ef8e9b2e9ac7d2a777627577486979422691de96fe9272e",
}
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
    seed: int
    directory: Path
    final_model_path: Path
    final_model_sha256: str
    output_root_sha256: str
    state_schema_sha256: str


def validate_evaluation_seed(seed: int) -> int:
    if isinstance(seed, bool) or seed not in ALLOWED_EVALUATION_SEEDS:
        raise FinalEvaluationError("evaluation seed must be one of 42, 43, or 44")
    return seed


def evaluation_unit_paths(
    output_root: Path | str,
    condition: str,
    seed: int,
) -> dict[str, Path]:
    validate_evaluation_seed(seed)
    if condition not in CONDITIONS:
        raise FinalEvaluationError(f"unknown final condition: {condition}")
    directory = Path(output_root) / condition / f"seed_{seed}"
    stem = f"{condition}_seed_{seed}"
    return {
        "directory": directory,
        "result": directory / f"case_level_metrics_{stem}.csv",
        "manifest": directory / f"evaluation_manifest_{stem}.json",
        "complete": directory / f"EVALUATION_COMPLETE_{stem}.json",
        "log": directory / f"evaluation_log_{stem}.jsonl",
    }


def verify_evaluation_completion(
    output_root: Path | str,
    condition: str,
    seed: int,
) -> dict[str, object]:
    paths = evaluation_unit_paths(output_root, condition, seed)
    if not paths["complete"].is_file():
        raise FinalEvaluationError(
            f"evaluation completion marker missing: {condition}: seed {seed}"
        )
    complete = json.loads(paths["complete"].read_text(encoding="utf-8"))
    required = {
        "complete": True,
        "condition_id": condition,
        "model_seed": seed,
    }
    if any(complete.get(key) != value for key, value in required.items()):
        raise FinalEvaluationError("evaluation completion identity mismatch")
    if not paths["manifest"].is_file() or not paths["result"].is_file():
        raise FinalEvaluationError("evaluation manifest or result missing")
    if sha256_path(paths["manifest"]) != complete.get("manifest_sha256"):
        raise FinalEvaluationError("evaluation manifest checksum mismatch")
    if sha256_path(paths["result"]) != complete.get("result_sha256"):
        raise FinalEvaluationError("evaluation result checksum mismatch")
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    expected_manifest = {
        "completed_case_count": EXPECTED_TEST_CASES,
        "condition_id": condition,
        "evaluation_seed": SEED,
        "model_seed": seed,
        "result_filename": paths["result"].name,
        "result_sha256": complete["result_sha256"],
        "test_access_count": EXPECTED_TEST_CASES,
        "unexpected_test_access_count": 0,
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        raise FinalEvaluationError("evaluation manifest metadata mismatch")
    return manifest


def verify_final_model(
    models_root: Path,
    condition: str,
    *,
    seed: int = SEED,
    expected_training_sha: str | None = None,
    verify_output_root: bool = True,
) -> VerifiedModel:
    seed = validate_evaluation_seed(seed)
    if condition not in CONDITIONS:
        raise FinalEvaluationError(f"unknown final condition: {condition}")
    approved_training_sha = TRAINING_IMPLEMENTATION_SHA_BY_SEED[seed]
    if expected_training_sha is None:
        expected_training_sha = approved_training_sha
    if expected_training_sha != approved_training_sha:
        raise FinalEvaluationError("training implementation SHA mismatch")
    directory = models_root / condition / f"seed_{seed}"
    marker_path = directory / "OUTPUT_COMPLETE.json"
    if not marker_path.is_file():
        raise FinalEvaluationError(f"missing final completion marker: {condition}")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    required = {
        "completed": True,
        "condition_id": condition,
        "config_sha256": EVALUATION_CONFIG_SHA256_BY_SEED[seed],
        "git_implementation_sha": expected_training_sha,
        "seed": seed,
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
    optimizer_path = directory / "final_optimizer_state.pt"
    if not optimizer_path.is_file() or sha256_path(optimizer_path) != marker.get(
        "final_optimizer_state_sha256"
    ):
        raise FinalEvaluationError(f"final optimizer checksum mismatch: {condition}")
    output_root_sha = str(marker.get("output_root_sha256", ""))
    if verify_output_root:
        observed_root, _ = _tree_inventory(directory, exclude=("OUTPUT_COMPLETE.json",))
        if observed_root != output_root_sha:
            raise FinalEvaluationError(f"final output-root checksum mismatch: {condition}")
    return VerifiedModel(
        condition,
        seed,
        directory,
        final_path,
        observed,
        output_root_sha,
        str(marker["state_schema_sha256"]),
    )


def verify_four_models(
    models_root: Path | str,
    *,
    seed: int = SEED,
    expected_training_sha: str | None = None,
    verify_output_root: bool = True,
) -> list[VerifiedModel]:
    return verify_models(
        models_root,
        CONDITIONS,
        seed=seed,
        expected_training_sha=expected_training_sha,
        verify_output_root=verify_output_root,
    )


def verify_models(
    models_root: Path | str,
    conditions: Sequence[str],
    *,
    seed: int = SEED,
    expected_training_sha: str | None = None,
    verify_output_root: bool = True,
) -> list[VerifiedModel]:
    seed = validate_evaluation_seed(seed)
    if not conditions or len(set(conditions)) != len(conditions):
        raise FinalEvaluationError("evaluation conditions must be nonempty and unique")
    models = [
        verify_final_model(
            Path(models_root),
            condition,
            seed=seed,
            expected_training_sha=expected_training_sha,
            verify_output_root=verify_output_root,
        )
        for condition in conditions
    ]
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
    expected_training_sha: str | None,
    seed: int,
    conditions: Sequence[str] = CONDITIONS,
) -> dict[str, object]:
    """Execute only after explicit CLI --execute; never called by preparation."""

    seed = validate_evaluation_seed(seed)
    if seed != SEED:
        return _execute_multiseed_evaluation(
            repository_root=repository_root,
            models_root=models_root,
            test_runtime_root=test_runtime_root,
            output_root=output_root,
            expected_training_sha=expected_training_sha,
            model_seed=seed,
            conditions=conditions,
        )
    if tuple(conditions) != CONDITIONS:
        raise FinalEvaluationError(
            "legacy seed-42 execution remains fixed to all four conditions"
        )
    verified = verify_four_models(
        models_root,
        seed=SEED,
        expected_training_sha=expected_training_sha,
    )
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evaluate_one_model(
    *,
    model_record: VerifiedModel,
    store: TestRuntimeInputStore,
    scaler: object,
    evaluation_seed: int,
) -> list[dict[str, object]]:
    from stable_baselines3 import PPO
    from vitaldb_state_selection.rl_integration.train_runtime import (
        make_train_runtime_environment,
    )

    model = PPO.load(model_record.final_model_path, device="cpu")
    before = sha256_path(model_record.final_model_path)
    rows: list[dict[str, object]] = []
    for index_row in store.rows:
        environment = make_train_runtime_environment(
            store=store,
            caseid=index_row["caseid"],
            condition_id=model_record.condition_id,
            scaler=scaler,
            seed=evaluation_seed,
        )
        observation, _ = environment.reset(seed=evaluation_seed)
        latent: list[float] = []
        rates: list[float] = []
        rewards: list[float] = []
        terminated = truncated = False
        failure = ""
        try:
            while not (terminated or truncated):
                action, _ = model.predict(observation, deterministic=True)
                observation, reward, terminated, truncated, info = environment.step(
                    action
                )
                latent.append(float(info["latent_true_bis"]))
                rates.append(float(info["propofol_rate_mg_per_min"]))
                rewards.append(float(reward))
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
        finally:
            environment.close()
        metrics = (
            compute_case_metrics(
                latent,
                rates,
                rewards,
                episode_completed=not failure,
                failure_reason=failure,
            )
            if latent
            else {
                **{name: None for name in METRIC_NAMES},
                "episode_completed": False,
                "episode_failure_reason": failure,
            }
        )
        rows.append(
            {
                "caseid": index_row["caseid"],
                "subjectid": index_row["subjectid"],
                "condition_id": model_record.condition_id,
                **metrics,
            }
        )
    if sha256_path(model_record.final_model_path) != before:
        raise FinalEvaluationError("model changed during deterministic evaluation")
    return rows


def _case_rows_csv(rows: Sequence[Mapping[str, object]]) -> bytes:
    import io

    fieldnames = (
        "caseid",
        "subjectid",
        "condition_id",
        *METRIC_NAMES,
        "episode_completed",
        "episode_failure_reason",
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _execute_multiseed_evaluation(
    *,
    repository_root: Path | str,
    models_root: Path | str,
    test_runtime_root: Path | str,
    output_root: Path | str,
    expected_training_sha: str | None,
    model_seed: int,
    conditions: Sequence[str],
) -> dict[str, object]:
    evaluation_seed = SEED
    verified = verify_models(
        models_root,
        conditions,
        seed=model_seed,
        expected_training_sha=expected_training_sha,
    )
    inputs = verify_evaluation_inputs(repository_root, test_runtime_root)
    root = Path(repository_root)
    store = TestRuntimeInputStore(test_runtime_root, root)
    scalers = load_scaler_registry(root / "data/manifests/phase8c_scaler_registry.json")
    units: list[dict[str, object]] = []
    executed_rows = 0
    for model_record in verified:
        paths = evaluation_unit_paths(
            output_root, model_record.condition_id, model_seed
        )
        if paths["complete"].is_file():
            manifest = verify_evaluation_completion(
                output_root, model_record.condition_id, model_seed
            )
            units.append({**manifest, "already_complete": True})
            continue
        if paths["directory"].exists() and any(paths["directory"].iterdir()):
            raise FinalEvaluationError(
                "incomplete evaluation output requires manual review: "
                f"{model_record.condition_id}: seed {model_seed}"
            )
        paths["directory"].mkdir(parents=True, exist_ok=True)
        started = _utc_now()
        scaler = scalers[
            "S0" if model_record.condition_id.endswith("S0") else "S1"
        ]
        rows = _evaluate_one_model(
            model_record=model_record,
            store=store,
            scaler=scaler,
            evaluation_seed=evaluation_seed,
        )
        result_bytes = _case_rows_csv(rows)
        atomic_bytes(paths["result"], result_bytes)
        failed = sum(row["episode_completed"] is not True for row in rows)
        manifest = {
            "case_order_sha256": inputs["case_order_sha256"],
            "completed_case_count": len(rows) - failed,
            "condition_id": model_record.condition_id,
            "end_timestamp_utc": _utc_now(),
            "evaluation_seed": evaluation_seed,
            "final_timestep": FINAL_TIMESTEP,
            "metric_version": METRIC_VERSION,
            "model_seed": model_seed,
            "model_sha256": model_record.final_model_sha256,
            "result_filename": paths["result"].name,
            "result_sha256": sha256_path(paths["result"]),
            "sealed_test_case_count": EXPECTED_TEST_CASES,
            "start_timestamp_utc": started,
            "test_access_count": len(rows),
            "training_implementation_sha": TRAINING_IMPLEMENTATION_SHA_BY_SEED[
                model_seed
            ],
            "training_output_root_sha256": model_record.output_root_sha256,
            "unexpected_test_access_count": 0,
            "failed_case_count": failed,
        }
        atomic_bytes(paths["manifest"], canonical_json_bytes(manifest))
        log_rows = [
            {
                "condition_id": model_record.condition_id,
                "event": "evaluation_start",
                "model_seed": model_seed,
                "timestamp_utc": started,
            },
            {
                "condition_id": model_record.condition_id,
                "event": "evaluation_complete",
                "failed_case_count": failed,
                "model_seed": model_seed,
                "timestamp_utc": manifest["end_timestamp_utc"],
            },
        ]
        atomic_bytes(
            paths["log"],
            b"".join(
                json.dumps(row, sort_keys=True).encode("utf-8") + b"\n"
                for row in log_rows
            ),
        )
        complete = {
            "complete": True,
            "condition_id": model_record.condition_id,
            "manifest_sha256": sha256_path(paths["manifest"]),
            "model_seed": model_seed,
            "result_sha256": sha256_path(paths["result"]),
        }
        atomic_bytes(paths["complete"], canonical_json_bytes(complete))
        verified_manifest = verify_evaluation_completion(
            output_root, model_record.condition_id, model_seed
        )
        units.append({**verified_manifest, "already_complete": False})
        executed_rows += len(rows)
    return {
        **inputs,
        "case_condition_rows": sum(
            int(unit["completed_case_count"]) + int(unit["failed_case_count"])
            for unit in units
        ),
        "episode_execution_count": executed_rows,
        "evaluation_seed": evaluation_seed,
        "model_seed": model_seed,
        "units": units,
    }

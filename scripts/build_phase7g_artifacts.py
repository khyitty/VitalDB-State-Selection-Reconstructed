"""Build deterministic, synthetic-only Phase 7G contracts and validation artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.anesthesia import (  # noqa: E402
    AnesthesiaEnvironmentCore, BISEvent, ConstantRemifentanilSchedule,
    EnvironmentConfig, FOUR_CONDITION_CONFIGS, PiecewiseConstantRemifentanilSchedule,
    PreprocessingID, S0_FIELDS, S1_FIELDS, SQIEvent, StateID,
    SyntheticObservationTemplate,
)
from vitaldb_state_selection.pkpd import PatientProfile, Sex  # noqa: E402


OUT = ROOT / "data" / "manifests"


def write_json(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contracts() -> None:
    approved = {
        "MC-010": "No LOWESS; raw causal BIS only.",
        "MC-011": "Recent dose is completed intervals in (t-60,t].",
        "MC-012": "Reward alpha is 1.0 and uses latent endpoint BIS only.",
        "MC-013": "Zero-drug reset, zero drug histories, unavailable BIS prehistory.",
        "MC-014": "Scientific invalidity terminates; configured horizon truncates.",
        "MC-015": "Synthetic default horizon is configurable 3600 seconds.",
        "MC-016": "Action is propofol mg per next 10 seconds, [0,27.7], rate=dose*6.",
        "MC-017": "Finite action is clipped once with raw/applied diagnostics.",
        "MC-018": "Synthetic deterministic right-continuous remifentanil schedules only.",
        "MC-031": "Observation age cap 30 seconds; P0 <=30, P1 <=20.",
        "MC-032": "Female=0, male=1; unsupported sex errors; S0=34, S1=42.",
    }
    write_json("phase7g_stage_ii_human_decisions.json", {
        "phase": "7G_stage_ii_dependency_free_environment_core",
        "approved_decisions": [{"id": key, "status": "approved_for_stage_ii", "decision": value} for key, value in approved.items()],
        "still_pending_ids": [*(f"MC-{value:03d}" for value in range(19, 31)), "MC-033", "MC-034"],
        "scope_note": "Approvals apply only to the synthetic Stage II core, not final PPO training or evaluation.",
    })
    write_json("phase7g_environment_constants.json", {
        "registry_id": "phase7g-environment-v1",
        "control_interval_seconds": 10.0,
        "history_offsets_seconds": [-50, -40, -30, -20, -10, 0],
        "target_bis": 50.0,
        "synthetic_default_horizon_seconds": 3600.0,
        "synthetic_default_max_steps": 360,
        "bis_age_clip_seconds": 30.0,
        "p0_staleness_seconds_inclusive": 30.0,
        "p1_staleness_seconds_inclusive": 20.0,
        "p1_sqi_threshold_inclusive": 50.0,
        "action_bounds_mg_per_10s": [0.0, 27.7],
        "reward_alpha": 1.0,
        "final_training_or_evaluation_horizon_approved": False,
    })
    write_json("phase7g_transition_order_contract.json", {
        "contract_id": "phase7g-transition-order-v1",
        "ordered_steps": [
            "validate_raw_action", "clip_once", "convert_dose_to_rate", "query_current_remifentanil_schedule",
            "partition_interval_at_events", "exact_zoh_advance_each_subinterval", "sample_latent_bis_at_bis_events",
            "finalize_endpoint_latent_state", "update_completed_drug_histories_and_doses", "update_elapsed_time",
            "query_causal_bis_history", "build_next_state", "compute_reward_from_latent_endpoint_bis",
            "determine_terminated_and_truncated", "return_diagnostics",
        ],
        "future_event_access": False,
    })
    write_json("phase7g_action_contract.json", {
        "public_field": "propofol_dose_mg_per_10s", "minimum": 0.0, "maximum": 27.7,
        "simulator_conversion": "propofol_rate_mg_per_min = propofol_dose_mg_per_10s * 6",
        "nonfinite_behavior": "raise_input_exception", "finite_out_of_bounds_behavior": "clip_exactly_once",
        "normalized_action_wrapper_implemented": False,
    })
    write_json("phase7g_remifentanil_schedule_contract.json", {
        "source_type": "synthetic_only", "unit": "microgram_per_min", "continuity": "right_continuous",
        "implementations": ["ConstantRemifentanilSchedule", "PiecewiseConstantRemifentanilSchedule"],
        "within_interval_change": "split_at_exact_timestamp_and_apply_exact_ZOH_per_subinterval",
        "controller_future_schedule_access": False,
    })
    write_json("phase7g_observation_template_schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "SyntheticObservationTemplate",
        "type": "object", "additionalProperties": False,
        "required": ["template_id", "source_type", "episode_horizon_seconds", "bis_events", "sqi_events"],
        "properties": {
            "template_id": {"type": "string", "minLength": 1}, "source_type": {"const": "synthetic"},
            "episode_horizon_seconds": {"type": "number", "exclusiveMinimum": 0},
            "bis_events": {"type": "array", "items": {"type": "object", "required": ["timestamp_seconds", "available"], "properties": {"timestamp_seconds": {"type": "number", "minimum": 0}, "available": {"type": "boolean"}}, "additionalProperties": False}},
            "sqi_events": {"type": "array", "items": {"type": "object", "required": ["timestamp_seconds", "value"], "properties": {"timestamp_seconds": {"type": "number", "minimum": 0}, "value": {"type": "number"}}, "additionalProperties": False}},
        },
        "raw_bis_values_permitted": False,
    })
    for state_id, fields in (("S0", S0_FIELDS), ("S1", S1_FIELDS)):
        write_json(f"phase7g_{state_id.lower()}_state_schema.json", {
            "state_id": state_id, "dimension": len(fields), "ordered_fields": list(fields),
            "dtype": "float64", "shape": [len(fields)], "finite_only": True,
            "contains_sqi_value": False, "contains_reason_code": False, "contains_target_bis": False,
            "s0_strict_prefix": state_id == "S1",
        })
    write_json("phase7g_four_condition_configs.json", {
        "conditions": [{"condition_id": name, "preprocessing_id": cfg.preprocessing_id.value, "state_id": cfg.state_id.value, "dimension": 34 if cfg.state_id is StateID.S0 else 42} for name, cfg in FOUR_CONDITION_CONFIGS.items()],
        "shared_latent_trajectory_required": True, "condition_specific_episode_deletion": False,
    })


def run_validation() -> dict[str, object]:
    profile = PatientProfile(45, Sex.FEMALE, 165, 60)
    scenario_specs = [
        ("perfect_observation", (10, 20, 30), ((10, 80), (20, 80), (30, 80)), ConstantRemifentanilSchedule(1)),
        ("low_sqi_episode", (10, 20, 30), ((10, 20), (20, 20), (30, 20)), ConstantRemifentanilSchedule(1)),
        ("missing_observation_episode", (10, 50), ((10, 80), (50, 80)), ConstantRemifentanilSchedule(1)),
        ("irregular_intra_interval_events", (3, 17, 28), ((3, 80), (17, 80), (28, 80)), ConstantRemifentanilSchedule(1)),
        ("piecewise_remifentanil", (4, 14, 29), ((4, 80), (14, 80), (29, 80)), PiecewiseConstantRemifentanilSchedule(((0, 0), (6, 2), (23, 4)))),
    ]
    rows = []
    for scenario_id, bis_times, sqi, schedule in scenario_specs:
        tmpl = SyntheticObservationTemplate(
            f"synthetic-{scenario_id}", 100,
            tuple(BISEvent(float(t)) for t in bis_times), tuple(SQIEvent(float(t), float(v)) for t, v in sqi),
        )
        environments = {}
        for name, base in FOUR_CONDITION_CONFIGS.items():
            cfg = EnvironmentConfig(base.preprocessing_id, base.state_id, episode_horizon_seconds=100)
            environments[name] = AnesthesiaEnvironmentCore(profile=profile, config=cfg, observation_template=tmpl, remifentanil_schedule=schedule)
        for env in environments.values():
            env.reset(seed=20260720)
        for action in (0.0, 2.0, 28.0):
            results = {name: env.step(action) for name, env in environments.items()}
            latent = [result[4]["latent_true_bis"] for result in results.values()]
            rewards = [result[1] for result in results.values()]
            assert max(latent) - min(latent) <= 1e-12
            assert max(rewards) - min(rewards) <= 1e-12
            assert all(np.isfinite(result[0]).all() for result in results.values())
            assert all(result[0].shape == ((34,) if name.endswith("S0") else (42,)) for name, result in results.items())
            np.testing.assert_array_equal(results["P0S0"][0], results["P0S1"][0][:34])
            np.testing.assert_array_equal(results["P1S0"][0], results["P1S1"][0][:34])
        rows.append({"scenario_id": scenario_id, "source_type": "synthetic", "steps": 3, "passed": True})
    write_json("phase7g_synthetic_validation_scenarios.json", {"fixed_seed": 20260720, "scenarios": rows, "control_performance_claimed": False})
    return {
        "phase": "7G_stage_ii_dependency_free_environment_core", "status": "passed",
        "scenario_count": len(rows), "condition_count": 4, "conditions": list(FOUR_CONDITION_CONFIGS),
        "s0_dimension": 34, "s1_dimension": 42, "latent_invariance_tolerance": 1e-12,
        "all_synthetic_scenarios_passed": True, "no_patient_data_used": True,
        "no_control_performance_evaluation": True, "no_ppo_training_or_evaluation": True,
    }


def source_snapshot() -> None:
    inputs = [
        "pyproject.toml", "data/manifests/final_eligible_cohort_manifest.csv",
        "data/manifests/subject_linkage_summary.json", "data/manifests/protocol_v1_3_1_source_snapshot.json",
        "data/manifests/protocol_v1_3_2_missing_constants.csv", "data/manifests/phase7f_artifact_checksums.json",
    ]
    write_json("phase7g_source_snapshot.json", {
        "phase": "7G_stage_ii_dependency_free_environment_core",
        "source_remote_main_at_start": "31fd5ae515255e564800266455dfbd3055c62786",
        "frozen_case_count": 2460, "frozen_subject_count": 2415,
        "input_artifact_sha256": {path: sha256(ROOT / path) for path in inputs},
        "dependency_installed_or_modified": False,
        "legacy_state_before": {"head": "9501b16a5c4db27f06fa0d0b252a3a75f633967f", "tree": "60917f0b61ec1e6a195b9a648faa6466406aeda1", "status": ["?? debug.log"]},
        "legacy_state_after": {"head": "9501b16a5c4db27f06fa0d0b252a3a75f633967f", "tree": "60917f0b61ec1e6a195b9a648faa6466406aeda1", "status": ["?? debug.log"]},
        "legacy_source_imported_or_copied": False, "legacy_artifacts_accessed": [],
        "execution_flags": {
            "synthetic_environment_implemented": True, "raw_vitaldb_access": False, "subject_metadata_access": False,
            "split_created": False, "test_seal_created": False, "modeling_array_created": False,
            "gymnasium_imported": False, "stable_baselines3_imported": False, "torch_imported": False,
            "ppo_implemented": False, "checkpoint_created": False, "training_run": False,
            "evaluation_run": False, "prediction_run": False,
        },
    })


def checksums() -> None:
    paths = [
        *sorted((ROOT / "src/vitaldb_state_selection/anesthesia").glob("*.py")),
        ROOT / "tests/test_anesthesia_environment.py", ROOT / "tests/test_phase7g_artifacts.py",
        ROOT / "scripts/build_phase7g_artifacts.py", ROOT / "docs/phase7g_stage_ii_validation_report.md",
        ROOT / "docs/phase7g_report.md",
        *sorted(OUT.glob("phase7g_*.json")),
    ]
    destination = OUT / "phase7g_artifact_checksums.json"
    paths = [path for path in paths if path != destination]
    write_json(destination.name, {"artifacts": [{"relative_path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in paths], "self_excluded": True})


if __name__ == "__main__":
    contracts()
    write_json("phase7g_validation_summary.json", run_validation())
    source_snapshot()
    checksums()

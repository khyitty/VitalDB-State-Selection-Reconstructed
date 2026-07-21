"""Create aggregate-only Phase 8E evaluation specifications and synthetic evidence."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.test_observation_templates import atomic_json, sha256_path  # noqa: E402
from vitaldb_state_selection.rl_integration.final_evaluation import (  # noqa: E402
    CONDITIONS,
    FINAL_CONFIG_SHA256,
    FINAL_TIMESTEP,
    METRIC_NAMES,
    SEED,
    TRAINING_IMPLEMENTATION_SHA,
    compute_case_metrics,
    metric_manifest,
    verify_four_models,
)
from vitaldb_state_selection.statistics.paired_evaluation import (  # noqa: E402
    CONTRAST_WEIGHTS,
    paired_differences,
    paired_metric_summary,
    paired_summary,
)


MANIFESTS = ROOT / "data/manifests"


def _synthetic_models(root: Path) -> None:
    for condition in CONDITIONS:
        directory = root / condition / "seed_42"
        final_checkpoint = directory / "checkpoint_0001000000"
        final_checkpoint.mkdir(parents=True)
        payload = f"synthetic-private-free-{condition}".encode("ascii")
        (directory / "final_model.zip").write_bytes(payload)
        (final_checkpoint / "model.zip").write_bytes(payload)
        atomic_json(final_checkpoint / "COMPLETE.json", {"complete": True})
        atomic_json(directory / "checkpoint_manifest.json", {
            "checkpoints": [{"timestep": value} for value in range(100_000, 1_000_001, 100_000)]
        })
        atomic_json(directory / "OUTPUT_COMPLETE.json", {
            "completed": True,
            "condition_id": condition,
            "config_sha256": FINAL_CONFIG_SHA256,
            "final_model_sha256": sha256_path(directory / "final_model.zip"),
            "git_implementation_sha": TRAINING_IMPLEMENTATION_SHA,
            "seed": SEED,
            "state_schema_sha256": "synthetic-s0" if condition.endswith("S0") else "synthetic-s1",
            "test_access_count": 0,
            "timestep": FINAL_TIMESTEP,
            "total_timestep_budget": FINAL_TIMESTEP,
        })


def main() -> int:
    summary = json.loads((MANIFESTS / "phase8e_test_input_summary.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        synthetic_root = Path(directory)
        _synthetic_models(synthetic_root)
        verified = verify_four_models(synthetic_root)
    trajectory = compute_case_metrics(
        [70.0, 60.0, 50.0, 45.0],
        [0.0, 3.0, 3.0, 1.0],
        [0.05, 0.1, 1.0, 0.2],
    )
    paired_rows = []
    for caseid, subjectid in (("1", "10"), ("2", "10"), ("3", "20"), ("4", "30")):
        base = float(caseid)
        for condition, offset in zip(CONDITIONS, (0.0, -1.0, -2.0, -4.0)):
            paired_rows.append({
                "caseid": caseid,
                "condition_id": condition,
                "metric": base + offset,
                "subjectid": subjectid,
            })
    contrast_validation = {}
    for contrast in CONTRAST_WEIGHTS:
        differences = paired_differences(paired_rows, "metric", contrast)
        contrast_validation[contrast] = paired_summary(
            differences,
            seed=SEED,
            bootstrap_replicates=64,
            permutation_replicates=64,
        )
    subject_pipeline = paired_metric_summary(
        paired_rows,
        "metric",
        seed=SEED,
        bootstrap_replicates=64,
        permutation_replicates=64,
    )
    evaluation_config = {
        "actual_evaluation_started": False,
        "case_count": 490,
        "case_order_sha256": summary["case_order_sha256"],
        "checkpoint_selection_allowed": False,
        "condition_order": list(CONDITIONS),
        "deterministic_inference": True,
        "episode_timing": "identical_test_bundle_horizon_and_10_second_control_interval",
        "evaluation_seed": SEED,
        "exploration_noise": False,
        "final_timestep_required": FINAL_TIMESTEP,
        "model_parameter_update_allowed": False,
        "optimizer_step_allowed": False,
        "scaler_fit_or_update_allowed": False,
        "training_implementation_sha": TRAINING_IMPLEMENTATION_SHA,
    }
    statistics_plan = {
        "actual_test_statistics_computed": False,
        "bootstrap_confidence_interval_percent": 95,
        "bootstrap_unit": "subjectid_after_case_level_metrics",
        "contrasts": CONTRAST_WEIGHTS,
        "effect_size": "paired_standardized_mean_difference_cohens_dz",
        "paired_structure": "same_case_under_all_four_conditions",
        "permutation_test": "paired_sign_flip_two_sided",
        "primary_summary": ["mean_difference", "median_difference"],
        "secondary_outcome_multiplicity": "Holm",
        "source_plan": "protocol_v1_3_statistical_analysis_plan.json",
    }
    synthetic = {
        "actual_model_episode_count": 0,
        "actual_test_case_count": 0,
        "four_model_metadata_gate_passed": len(verified) == 4,
        "metric_names_exercised": list(trajectory),
        "paired_contrast_formulas_passed": list(contrast_validation),
        "subject_level_aggregation_passed": subject_pipeline["subject_count"] == 3,
        "holm_multiplicity_pipeline_passed": all(
            "holm_adjusted_p" in row for row in subject_pipeline["contrasts"].values()
        ),
        "private_or_patient_data_used": False,
        "synthetic_only": True,
    }
    atomic_json(MANIFESTS / "phase8e_evaluation_config.json", evaluation_config)
    atomic_json(MANIFESTS / "phase8e_metric_manifest.json", metric_manifest())
    atomic_json(MANIFESTS / "phase8e_statistics_plan.json", statistics_plan)
    atomic_json(MANIFESTS / "phase8e_synthetic_validation.json", synthetic)
    evaluation_output = ROOT / "data/processed/phase8e_evaluation_outputs_v1"
    if evaluation_output.exists():
        raise RuntimeError("private evaluation output already exists; preparation refuses deletion or overwrite")
    print(json.dumps(synthetic, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

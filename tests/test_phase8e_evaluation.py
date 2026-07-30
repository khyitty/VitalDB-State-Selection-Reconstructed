from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.statistics.paired_evaluation import (  # noqa: E402
    holm_adjust,
    paired_differences,
    paired_metric_summary,
    paired_summary,
)

try:
    from vitaldb_state_selection.cohort.test_observation_templates import atomic_json, sha256_path  # noqa: E402
    from vitaldb_state_selection.rl_integration.final_evaluation import (  # noqa: E402
        ALLOWED_EVALUATION_SEEDS,
        CONDITIONS,
        EVALUATION_CONFIG_SHA256_BY_SEED,
        FinalEvaluationError,
        TRAINING_IMPLEMENTATION_SHA_BY_SEED,
        compute_case_metrics,
        evaluation_unit_paths,
        verify_evaluation_completion,
        verify_four_models,
    )
    OPTIONAL_RL_AVAILABLE = True
except ModuleNotFoundError:
    OPTIONAL_RL_AVAILABLE = False
    CONDITIONS = ("P0S0", "P1S0", "P0S1", "P1S1")


def synthetic_models(
    root: Path,
    *,
    seed: int = 42,
    omit: str | None = None,
    timestep: int = 1_000_000,
) -> None:
    for condition in CONDITIONS:
        if condition == omit:
            continue
        directory = root / condition / f"seed_{seed}"
        checkpoint = directory / "checkpoint_0001000000"
        checkpoint.mkdir(parents=True)
        payload = condition.encode("ascii")
        (directory / "final_model.zip").write_bytes(payload)
        (directory / "final_optimizer_state.pt").write_bytes(payload)
        (checkpoint / "model.zip").write_bytes(payload)
        atomic_json(checkpoint / "COMPLETE.json", {"complete": True})
        atomic_json(directory / "checkpoint_manifest.json", {"checkpoints": [{"timestep": value} for value in range(100_000, 1_000_001, 100_000)]})
        atomic_json(directory / "OUTPUT_COMPLETE.json", {
            "completed": True,
            "condition_id": condition,
            "config_sha256": EVALUATION_CONFIG_SHA256_BY_SEED[seed],
            "final_model_sha256": sha256_path(directory / "final_model.zip"),
            "final_optimizer_state_sha256": sha256_path(directory / "final_model.zip"),
            "git_implementation_sha": TRAINING_IMPLEMENTATION_SHA_BY_SEED[seed],
            "output_root_sha256": "synthetic-output-root",
            "seed": seed,
            "state_schema_sha256": "s0" if condition.endswith("S0") else "s1",
            "test_access_count": 0,
            "timestep": timestep,
            "total_timestep_budget": 1_000_000,
        })


@unittest.skipUnless(OPTIONAL_RL_AVAILABLE, "optional Phase 7H RL dependencies are isolated")
class Phase8EEvaluationTests(unittest.TestCase):
    def test_metrics_use_latent_bis_and_frozen_thresholds(self) -> None:
        result = compute_case_metrics([30, 50, 70], [0, 3, 6], [0.1, 1.0, 0.1])
        self.assertAlmostEqual(result["mean_absolute_bis_deviation"], 40 / 3)
        self.assertEqual(result["time_below_bis_40_seconds"], 10.0)
        self.assertEqual(result["time_in_bis_40_60_seconds"], 10.0)
        self.assertEqual(result["time_above_bis_60_seconds"], 10.0)
        self.assertEqual(result["cumulative_propofol_amount_mg"], 1.5)

    def test_four_final_models_and_exact_timestep_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic_models(root)
            self.assertEqual(
                [
                    row.condition_id
                    for row in verify_four_models(root, verify_output_root=False)
                ],
                list(CONDITIONS),
            )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic_models(root, omit="P1S1")
            with self.assertRaises(FinalEvaluationError):
                verify_four_models(root, verify_output_root=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic_models(root, timestep=900_000)
            with self.assertRaises(FinalEvaluationError):
                verify_four_models(root, verify_output_root=False)

    def test_sha_seed_and_config_mismatch_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic_models(root)
            with self.assertRaises(FinalEvaluationError):
                verify_four_models(
                    root,
                    expected_training_sha="0" * 40,
                    verify_output_root=False,
                )
            marker_path = root / "P0S0/seed_42/OUTPUT_COMPLETE.json"
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["seed"] = 7
            atomic_json(marker_path, marker)
            with self.assertRaises(FinalEvaluationError):
                verify_four_models(root, verify_output_root=False)

    def test_multiseed_models_use_explicit_seed_and_approved_training_sha(self) -> None:
        self.assertEqual(ALLOWED_EVALUATION_SEEDS, (42, 43, 44))
        for seed in (43, 44):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                synthetic_models(root, seed=seed)
                models = verify_four_models(
                    root,
                    seed=seed,
                    expected_training_sha=TRAINING_IMPLEMENTATION_SHA_BY_SEED[seed],
                    verify_output_root=False,
                )
                self.assertEqual([row.condition_id for row in models], list(CONDITIONS))
                self.assertTrue(all(row.seed == seed for row in models))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic_models(root, seed=43)
            with self.assertRaises(FinalEvaluationError):
                verify_four_models(root, seed=41)
            with self.assertRaises(FinalEvaluationError):
                verify_four_models(
                    root,
                    seed=43,
                    expected_training_sha=TRAINING_IMPLEMENTATION_SHA_BY_SEED[42],
                )

    def test_evaluation_unit_paths_include_condition_and_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = evaluation_unit_paths(Path(directory), "P0S1", 44)
            self.assertEqual(paths["directory"], Path(directory) / "P0S1/seed_44")
            self.assertEqual(paths["result"].name, "case_level_metrics_P0S1_seed_44.csv")
            self.assertEqual(paths["manifest"].name, "evaluation_manifest_P0S1_seed_44.json")
            self.assertEqual(paths["complete"].name, "EVALUATION_COMPLETE_P0S1_seed_44.json")
            self.assertEqual(paths["log"].name, "evaluation_log_P0S1_seed_44.jsonl")

    def test_evaluation_completion_is_seed_specific_and_checksum_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = evaluation_unit_paths(Path(directory), "P1S0", 43)
            paths["directory"].mkdir(parents=True)
            result = b"caseid,subjectid,condition_id\n"
            paths["result"].write_bytes(result)
            manifest = {
                "completed_case_count": 490,
                "condition_id": "P1S0",
                "evaluation_seed": 42,
                "model_seed": 43,
                "result_filename": paths["result"].name,
                "result_sha256": sha256_path(paths["result"]),
                "test_access_count": 490,
                "unexpected_test_access_count": 0,
            }
            atomic_json(paths["manifest"], manifest)
            atomic_json(
                paths["complete"],
                {
                    "complete": True,
                    "condition_id": "P1S0",
                    "manifest_sha256": sha256_path(paths["manifest"]),
                    "model_seed": 43,
                    "result_sha256": sha256_path(paths["result"]),
                },
            )
            verified = verify_evaluation_completion(
                Path(directory), "P1S0", 43
            )
            self.assertEqual(verified["evaluation_seed"], 42)
            paths["result"].write_bytes(result + b"tampered")
            with self.assertRaises(FinalEvaluationError):
                verify_evaluation_completion(Path(directory), "P1S0", 43)

    def test_multiseed_source_keeps_phase8e_simulator_seed_fixed(self) -> None:
        source = (
            ROOT
            / "src/vitaldb_state_selection/rl_integration/final_evaluation.py"
        ).read_text(encoding="utf-8")
        execute = source.split("def execute_evaluation(", 1)[1]
        self.assertIn("evaluation_seed = SEED", execute)
        self.assertIn("seed=evaluation_seed", execute)
        self.assertIn("environment.reset(seed=evaluation_seed)", execute)

    def test_paired_contrast_and_synthetic_statistics(self) -> None:
        rows = []
        values = {"P0S0": 10.0, "P1S0": 8.0, "P0S1": 7.0, "P1S1": 4.0}
        for caseid, subjectid in (("1", "10"), ("2", "10"), ("3", "20")):
            for condition, value in values.items():
                rows.append({
                    "caseid": caseid,
                    "condition_id": condition,
                    "metric": value + int(caseid),
                    "subjectid": subjectid,
                })
        self.assertEqual(paired_differences(rows, "metric", "P1S0_minus_P0S0").tolist(), [-2.0] * 3)
        self.assertEqual(paired_differences(rows, "metric", "interaction").tolist(), [-1.0] * 3)
        summary = paired_summary([-2.0, -1.0, -3.0], bootstrap_replicates=32, permutation_replicates=32)
        self.assertEqual(summary["case_count"], 3)
        pipeline = paired_metric_summary(rows, "metric", bootstrap_replicates=32, permutation_replicates=32)
        self.assertEqual(pipeline["case_count"], 3)
        self.assertEqual(pipeline["subject_count"], 2)
        self.assertTrue(all("holm_adjusted_p" in row for row in pipeline["contrasts"].values()))
        self.assertEqual(holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03}), {"a": 0.03, "b": 0.06, "c": 0.06})

    def test_runner_default_is_verify_only_and_execute_is_explicit(self) -> None:
        source = (ROOT / "scripts/run_phase8e_final_evaluation.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--execute", action="store_true"', source)
        self.assertIn("if not args.execute:", source)
        safe_branch = source.split("if not args.execute:", 1)[1].split("if args.output_root is None:", 1)[0]
        self.assertNotIn("PPO.load", safe_branch)
        self.assertNotIn("execute_evaluation(", safe_branch)
        self.assertIn("choices=ALLOWED_EVALUATION_SEEDS", source)
        self.assertNotIn("if args.seed != SEED:", source)
        self.assertIn('parser.add_argument("--condition"', source)
        preparation = (ROOT / "scripts/prepare_phase8e_evaluation.py").read_text(encoding="utf-8")
        self.assertNotIn("rmtree", preparation)
        self.assertIn("preparation refuses deletion or overwrite", preparation)


if __name__ == "__main__":
    unittest.main()

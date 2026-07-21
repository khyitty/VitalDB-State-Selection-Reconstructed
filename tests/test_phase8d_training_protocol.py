from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data/manifests"
CONFIG = MANIFESTS / "phase8d_final_ppo_config.json"


@unittest.skipUnless(CONFIG.is_file(), "official Phase 8D artifacts not generated")
class Phase8DTrainingProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.protocol = json.loads((MANIFESTS / "phase8d_training_protocol.json").read_text(encoding="utf-8"))
        cls.shards = json.loads((MANIFESTS / "phase8d_shard_definition.json").read_text(encoding="utf-8"))
        cls.sampling = json.loads((MANIFESTS / "phase8d_sampling_summary.json").read_text(encoding="utf-8"))
        cls.preflight = json.loads((MANIFESTS / "phase8d_preflight_summary.json").read_text(encoding="utf-8"))
        cls.source = json.loads((MANIFESTS / "phase8d_source_snapshot.json").read_text(encoding="utf-8"))

    def test_shards_are_disjoint_and_cover_each_condition_once(self) -> None:
        a = self.shards["assignments"]["A"]["conditions"]
        b = self.shards["assignments"]["B"]["conditions"]
        self.assertEqual(a, ["P0S0", "P1S0"])
        self.assertEqual(b, ["P0S1", "P1S1"])
        self.assertFalse(set(a) & set(b))
        self.assertEqual(set(a + b), {"P0S0", "P1S0", "P0S1", "P1S1"})
        self.assertTrue(self.shards["all_conditions_covered_exactly_once"])

    def test_seed_budget_and_checkpoint_schedule_are_frozen(self) -> None:
        self.assertEqual(self.config["seed"], 42)
        self.assertEqual(self.config["total_timesteps"], 1_000_000)
        self.assertEqual(self.config["checkpoint_interval_timesteps"], 100_000)
        self.assertEqual(self.protocol["checkpoint_timesteps"], list(range(100_000, 1_000_001, 100_000)))
        self.assertFalse(self.config["single_seed_only"] is False)
        self.assertFalse(self.protocol["early_stopping"])
        self.assertFalse(self.protocol["best_checkpoint_selection"])

    def test_resolved_hyperparameters_and_architecture_are_common(self) -> None:
        expected = {
            "policy": "MlpPolicy", "gamma": 0.99, "gae_lambda": 0.95,
            "clip_range": 0.2, "n_steps": 2048, "batch_size": 64,
            "n_epochs": 10, "vf_coef": 0.1, "ent_coef": 0.0,
            "max_grad_norm": 0.5, "learning_rate": 0.001,
            "optimizer": "Adam", "optimizer_weight_decay": 0.001,
            "actor_hidden_layers": [128], "critic_hidden_layers": [128],
            "activation": "Tanh", "device": "cpu",
        }
        for key, value in expected.items():
            self.assertEqual(self.config[key], value)
        self.assertEqual(self.protocol["state_dimension_difference_only"], {"S0": 34, "S1": 42})
        self.assertTrue(self.protocol["same_hyperparameters_all_conditions"])

    def test_sampling_is_uniform_deterministic_common_and_train_only(self) -> None:
        self.assertEqual(self.sampling["algorithm"], "numpy_PCG64_uniform_integer_index_v1")
        self.assertEqual(self.sampling["master_seed"], 42)
        self.assertEqual(self.sampling["train_case_count"], 1970)
        self.assertEqual(self.sampling["test_case_count_used"], 0)
        self.assertTrue(self.sampling["same_sequence_all_conditions"])
        self.assertFalse(self.sampling["case_sequence_published"])
        self.assertRegex(self.sampling["ordered_episode_sequence_sha256"], r"^[0-9a-f]{64}$")

    def test_four_condition_preflight_passes_without_persistence_or_test_access(self) -> None:
        rows = self.preflight["results"]
        self.assertEqual([row["condition_id"] for row in rows], ["P0S0", "P1S0", "P0S1", "P1S1"])
        self.assertTrue(all(row["status"] == "passed" and row["timesteps"] == 1024 for row in rows))
        self.assertTrue(all(row["parameters_finite"] and row["gradients_finite"] for row in rows))
        self.assertTrue(all(row["logged_training_values_finite"] for row in rows))
        self.assertTrue(all(row["model_or_checkpoint_persisted"] is False for row in rows))
        self.assertEqual(self.preflight["test_access_count"], 0)
        self.assertEqual(self.preflight["final_training_timesteps_consumed"], 0)

    def test_source_boundaries_and_roots_are_immutable(self) -> None:
        self.assertEqual(self.source["phase8b_private_root_sha256"], "96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2")
        self.assertEqual(self.source["phase8c_private_root_sha256"], "25ad8a860f6c9b0b45febec7ff7d0d0edf88c0f1953229c8d95e207508d3a606")
        self.assertEqual(self.source["legacy_state_before"], self.source["legacy_state_after"])
        self.assertTrue(all(value is False or value == 0 for value in self.source["execution_flags"].values()))

    def test_runner_exposes_no_evaluation_or_selection_capability(self) -> None:
        path = ROOT / "scripts/run_phase8d_final_training.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertNotIn("test_case", source.lower())
        self.assertNotIn("best_model", source.lower())
        self.assertNotIn("p_value", source.lower())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and node.func.attr in {"evaluate", "predict"} for node in calls))

    def test_output_directories_are_ignored_and_untracked(self) -> None:
        relative = "data/processed/phase8d_final_training_v1"
        ignored = subprocess.run(["git", "check-ignore", "-q", relative], cwd=ROOT, check=False)
        self.assertEqual(ignored.returncode, 0)
        self.assertEqual(subprocess.check_output(["git", "ls-files", relative], cwd=ROOT, text=True).strip(), "")

    def test_public_artifact_inventory_is_exact_self_excluded_and_private_free(self) -> None:
        inventory_path = MANIFESTS / "phase8d_artifact_checksums.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        self.assertTrue(inventory["self_excluded"])
        paths = [row["relative_path"] for row in inventory["artifacts"]]
        self.assertEqual(paths, sorted(paths))
        self.assertNotIn("data/manifests/phase8d_artifact_checksums.json", paths)
        self.assertNotIn("PHASE_STATUS.md", paths)
        self.assertFalse(any(path.startswith("data/processed/") for path in paths))
        for row in inventory["artifacts"]:
            path = ROOT / row["relative_path"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(path.stat().st_size, row["bytes"])
            self.assertEqual(digest, row["sha256"])

    def test_public_results_are_aggregate_only_and_have_no_local_path(self) -> None:
        public = [
            MANIFESTS / "phase8d_training_protocol.json",
            MANIFESTS / "phase8d_shard_definition.json",
            MANIFESTS / "phase8d_sampling_summary.json",
            MANIFESTS / "phase8d_preflight_summary.json",
            MANIFESTS / "phase8d_source_snapshot.json",
            ROOT / "docs/phase8d_final_training_protocol.md",
            ROOT / "docs/phase8d_parallel_training_runbook.md",
            ROOT / "docs/phase8d_training_infrastructure_report.md",
        ]
        for path in public:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("C:\\Users\\", text)
            self.assertNotRegex(text, r'"caseid"\s*:')
            self.assertNotRegex(text, r'"subjectid"\s*:')
            self.assertNotIn("event_timestamps", text)
            self.assertNotIn("final_model.zip", text)


if __name__ == "__main__":
    unittest.main()

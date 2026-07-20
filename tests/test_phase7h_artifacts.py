import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"


def load(name):
    return json.loads((MANIFESTS / name).read_text(encoding="utf-8"))


class Phase7HArtifactTests(unittest.TestCase):
    def test_direct_dependencies_are_exact_and_only_approved_rl_packages(self):
        lines = [line for line in (ROOT / "requirements/phase7h_rl_direct.txt").read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
        self.assertEqual(lines, ["stable-baselines3==2.8.0", "gymnasium==1.2.3"])
        lock = (ROOT / "requirements/phase7h_rl_lock.txt").read_text(encoding="utf-8")
        self.assertIn("stable_baselines3==2.8.0", lock)
        self.assertIn("gymnasium==1.2.3", lock)
        self.assertIn("torch==2.13.0", lock)

    def test_runtime_manifest_locks_cpu_versions_and_adam_defaults(self):
        runtime = load("phase7h_runtime_environment.json")
        self.assertEqual(runtime["environment_path_token"], ".venv-phase7h")
        self.assertEqual(runtime["stable_baselines3_version"], "2.8.0")
        self.assertEqual(runtime["gymnasium_version"], "1.2.3")
        self.assertEqual(runtime["execution_device"], "cpu")
        self.assertFalse(runtime["cuda_used"])
        self.assertEqual(runtime["adam_defaults_locked"]["betas"], [0.9, 0.999])
        self.assertEqual(runtime["adam_defaults_locked"]["eps"], 1e-8)
        self.assertEqual(runtime["phase7h_optimizer_override"], {"learning_rate": 0.001, "weight_decay": 0.001})

    def test_approved_and_pending_mc_ids_are_exact(self):
        decisions = load("phase7h_human_decisions.json")
        self.assertEqual(set(decisions["approved_scoped_ids"]), {*(f"MC-{n:03d}" for n in range(19, 30)), "MC-034"})
        self.assertEqual(set(decisions["still_pending_ids"]), {"MC-030", "MC-033"})
        self.assertTrue(decisions["not_yun_dependency_versions"])
        self.assertTrue(decisions["not_exact_unpublished_architecture_reproduction"])

    def test_candidate_and_smoke_manifests_remain_separate(self):
        candidate = load("phase7h_scientific_ppo_candidate.json")
        smoke = load("phase7h_smoke_ppo_configuration.json")
        self.assertEqual(candidate["configuration_id"], "paper_oriented_ppo_candidate_v1")
        self.assertEqual((candidate["n_steps"], candidate["batch_size"], candidate["n_epochs"]), (2048, 64, 10))
        self.assertIsNone(candidate["total_timesteps"])
        self.assertIsNone(candidate["seed"])
        self.assertEqual((smoke["n_steps"], smoke["batch_size"], smoke["n_epochs"], smoke["total_timesteps"], smoke["seed"]), (64, 32, 1, 128, 42))
        for payload in (candidate, smoke):
            self.assertEqual(payload["policy"], "MlpPolicy")
            self.assertEqual(payload["actor_hidden_layers"], [128])
            self.assertEqual(payload["critic_hidden_layers"], [128])
            self.assertEqual(payload["vf_coef"], 0.1)
            self.assertEqual(payload["optimizer_weight_decay"], 0.001)

    def test_adapter_and_smoke_summaries_are_correctness_only(self):
        adapter = load("phase7h_adapter_validation_summary.json")
        self.assertTrue(all(row["gymnasium_checker_passed"] and row["sb3_checker_passed"] for row in adapter["conditions"]))
        self.assertTrue(all(row["classification"] == "expected_and_harmless" for row in adapter["checker_warnings"]))
        smoke = load("phase7h_smoke_summary.json")
        self.assertEqual(smoke["official_smoke_run_count"], 4)
        self.assertEqual({row["condition_id"] for row in smoke["runs"]}, {"P0S0", "P1S0", "P0S1", "P1S1"})
        self.assertTrue(all(row["total_timesteps"] == 128 and row["seed"] == 42 for row in smoke["runs"]))
        self.assertFalse(smoke["condition_ranking_created"])
        self.assertFalse(smoke["reward_or_bis_comparison_created"])
        self.assertFalse(smoke["persistent_checkpoint_created"])
        run_payload = json.dumps(smoke["runs"]).lower()
        self.assertNotIn("reward", run_payload)
        self.assertNotIn("bis", run_payload)

    def test_determinism_and_source_boundaries(self):
        determinism = load("phase7h_determinism_summary.json")
        self.assertEqual(determinism["rollout_transition_counts"], [128, 128])
        self.assertTrue(determinism["initial_observation_equal"])
        self.assertTrue(determinism["first_deterministic_prediction_equal"])
        self.assertTrue(determinism["model_parameter_checksum_equal"])
        self.assertFalse(determinism["best_run_selected"])
        source = load("phase7h_source_snapshot.json")
        self.assertEqual(source["frozen_case_count"], 2460)
        self.assertEqual(source["frozen_subject_count"], 2415)
        self.assertEqual(source["legacy_state_before"], source["legacy_state_after"])
        self.assertEqual(source["input_artifact_sha256"]["pyproject.toml"], "0e403ab599452d41b32938e2a558a69af326e398229f8657d2a6fa24efbc9ff8")
        self.assertTrue(all(value is False for value in source["execution_flags"].values()))

    def test_base_scientific_packages_do_not_import_optional_rl(self):
        sources = "\n".join(path.read_text(encoding="utf-8") for directory in (ROOT / "src/vitaldb_state_selection/pkpd", ROOT / "src/vitaldb_state_selection/anesthesia") for path in directory.glob("*.py"))
        for forbidden in ("import gymnasium", "stable_baselines3", "import torch"):
            self.assertNotIn(forbidden, sources)
        self.assertIn(".venv-phase7h/", (ROOT / ".gitignore").read_text(encoding="utf-8"))

    def test_artifact_checksums(self):
        payload = load("phase7h_artifact_checksums.json")
        self.assertTrue(payload["self_excluded"])
        for row in payload["artifacts"]:
            path = ROOT / row["relative_path"]
            self.assertTrue(path.is_file(), row["relative_path"])
            self.assertEqual(path.stat().st_size, row["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data/manifests"
SUMMARY_PATH = MANIFESTS / "phase8e_test_input_summary.json"


@unittest.skipUnless(SUMMARY_PATH.is_file(), "official Phase 8E artifacts not generated")
class Phase8EArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        cls.config = json.loads((MANIFESTS / "phase8e_evaluation_config.json").read_text(encoding="utf-8"))
        cls.source = json.loads((MANIFESTS / "phase8e_source_snapshot.json").read_text(encoding="utf-8"))
        cls.synthetic = json.loads((MANIFESTS / "phase8e_synthetic_validation.json").read_text(encoding="utf-8"))

    def test_private_store_counts_roots_and_accesses(self) -> None:
        self.assertEqual(self.summary["test_case_count"], 490)
        self.assertEqual(self.summary["test_template_count"], 490)
        self.assertEqual(self.summary["test_runtime_bundle_count"], 490)
        self.assertEqual(self.summary["test_bis_logical_access_count"], 490)
        self.assertEqual(self.summary["test_sqi_logical_access_count"], 490)
        self.assertEqual(self.summary["test_remifentanil_logical_access_count"], 490)
        self.assertRegex(self.summary["private_test_template_root_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(self.summary["private_test_runtime_root_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.summary["missing_required_profile_count"], 0)
        self.assertEqual(self.summary["invalid_profile_count"], 0)
        self.assertFalse(self.summary["approved_fallback_used"])

    def test_no_propofol_or_train_access_and_train_roots_unchanged(self) -> None:
        self.assertEqual(self.summary["train_case_access_count_during_test_extraction"], 0)
        self.assertEqual(self.summary["train_scaler_fit_count_during_test_phase"], 0)
        self.assertEqual(self.summary["phase8b_train_root_before"], self.summary["phase8b_train_root_after"])
        self.assertEqual(self.summary["phase8c_train_root_before"], self.summary["phase8c_train_root_after"])
        self.assertEqual(self.summary["phase8b_train_root_after"], "96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2")
        self.assertEqual(self.summary["phase8c_train_root_after"], "25ad8a860f6c9b0b45febec7ff7d0d0edf88c0f1953229c8d95e207508d3a606")

    def test_shard_a_is_read_only_checksum_verified_without_episode(self) -> None:
        shard = self.summary["shard_a_read_only_verification"]
        self.assertFalse(shard["models_loaded"])
        self.assertEqual(shard["episode_execution_count"], 0)
        self.assertEqual(shard["test_access_count"], 0)
        self.assertEqual([row["condition_id"] for row in shard["records"]], ["P0S0", "P1S0"])
        self.assertEqual([row["timestep"] for row in shard["records"]], [1_000_000, 1_000_000])
        self.assertEqual(self.source["legacy_repository_before"], self.source["legacy_repository_after"])
        self.assertEqual(self.source["legacy_repository_after"]["commit_sha"], "9501b16a5c4db27f06fa0d0b252a3a75f633967f")
        self.assertEqual(self.source["legacy_repository_after"]["tree_sha"], "60917f0b61ec1e6a195b9a648faa6466406aeda1")
        self.assertFalse(self.source["shard_a_policy_models_loaded"])
        self.assertFalse(self.source["shard_b_accessed"])

    def test_evaluation_is_readiness_only_and_synthetic_validation_is_private_free(self) -> None:
        self.assertFalse(self.config["actual_evaluation_started"])
        self.assertFalse(self.config["model_parameter_update_allowed"])
        self.assertFalse(self.config["optimizer_step_allowed"])
        self.assertFalse(self.config["scaler_fit_or_update_allowed"])
        self.assertEqual(self.synthetic["actual_model_episode_count"], 0)
        self.assertEqual(self.synthetic["actual_test_case_count"], 0)
        self.assertTrue(self.synthetic["synthetic_only"])
        self.assertTrue(self.synthetic["private_or_patient_data_used"] is False)

    def test_private_paths_are_ignored_and_untracked(self) -> None:
        for relative in (
            "data/processed/phase8e_test_observation_templates_v1",
            "data/processed/phase8e_test_runtime_inputs_v1",
            "data/processed/phase8e_evaluation_outputs_v1",
        ):
            ignored = subprocess.run(["git", "check-ignore", "-q", relative], cwd=ROOT, check=False)
            self.assertEqual(ignored.returncode, 0)
            self.assertEqual(subprocess.check_output(["git", "ls-files", relative], cwd=ROOT, text=True).strip(), "")

    def test_public_artifacts_are_aggregate_only_and_local_path_free(self) -> None:
        public = [
            path for path in MANIFESTS.glob("phase8e_*.json")
            if path.name != "phase8e_artifact_checksums.json"
        ] + list((ROOT / "docs").glob("phase8e_*.md"))
        for path in public:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("C:\\Users\\", text)
            self.assertNotRegex(text, r'"caseid"\s*:')
            self.assertNotRegex(text, r'"subjectid"\s*:')
        self.assertEqual(self.summary["public_event_level_value_count"], 0)

    def test_artifact_inventory_is_exact_and_self_excluded(self) -> None:
        inventory = json.loads((MANIFESTS / "phase8e_artifact_checksums.json").read_text(encoding="utf-8"))
        self.assertTrue(inventory["self_excluded"])
        paths = [row["relative_path"] for row in inventory["artifacts"]]
        self.assertEqual(paths, sorted(paths))
        self.assertNotIn("PHASE_STATUS.md", paths)
        self.assertNotIn("data/manifests/phase8e_artifact_checksums.json", paths)
        self.assertFalse(any(path.startswith("data/processed/") for path in paths))
        for row in inventory["artifacts"]:
            path = ROOT / row["relative_path"]
            self.assertEqual(path.stat().st_size, row["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])


if __name__ == "__main__":
    unittest.main()

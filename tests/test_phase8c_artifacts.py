from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MANIFESTS = ROOT / "data/manifests"
PRIVATE = ROOT / "data/processed/phase8c_train_runtime_inputs_v1"
SUMMARY_PATH = MANIFESTS / "phase8c_runtime_input_summary.json"

from vitaldb_state_selection.cohort.train_runtime_inputs import sha256_path  # noqa: E402


@unittest.skipUnless(SUMMARY_PATH.is_file(), "official Phase 8C artifacts not generated")
class Phase8CArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        cls.smoke = json.loads((MANIFESTS / "phase8c_smoke_summary.json").read_text(encoding="utf-8"))
        cls.scalers = json.loads((MANIFESTS / "phase8c_scaler_registry.json").read_text(encoding="utf-8"))
        cls.snapshot = json.loads((MANIFESTS / "phase8c_source_snapshot.json").read_text(encoding="utf-8"))

    def test_public_accounting_and_phase8b_root_are_exact(self) -> None:
        self.assertEqual(self.summary["train_patient_profile_count"], 1970)
        self.assertEqual(self.summary["remifentanil_schedule_count"], 1970)
        self.assertEqual(self.summary["train_remifentanil_logical_access_count"], 1970)
        self.assertEqual(self.summary["missing_required_profile_count"], 0)
        self.assertEqual(self.summary["invalid_profile_count"], 0)
        self.assertFalse(self.summary["approved_fallback_used"])
        self.assertEqual(self.summary["test_raw_access_count"], 0)
        self.assertEqual(self.summary["test_runtime_bundle_count"], 0)
        self.assertEqual(self.summary["partial_directory_count"], 0)
        expected = "96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2"
        self.assertEqual(self.summary["phase8b_private_root_before"], expected)
        self.assertEqual(self.summary["phase8b_private_root_after"], expected)

    def test_preflight_and_smoke_are_four_condition_correctness_only(self) -> None:
        preflight = self.summary["preflight"]
        self.assertEqual(preflight["case_count"], 3)
        self.assertEqual(preflight["condition_case_checks"], 12)
        self.assertTrue(all(item["passed"] for item in preflight["conditions"].values()))
        self.assertEqual({key: value["shape"] for key, value in preflight["conditions"].items()}, {
            "P0S0": 34, "P1S0": 34, "P0S1": 42, "P1S1": 42,
        })
        self.assertEqual(self.smoke["seed"], 42)
        self.assertEqual(self.smoke["timestep_budget_per_condition"], 128)
        self.assertEqual(len(self.smoke["results"]), 4)
        self.assertTrue(all(row["status"] == "passed" for row in self.smoke["results"]))
        self.assertTrue(all(row["env_checker_passed"] and row["vec_env_created"] and row["learn_completed"] for row in self.smoke["results"]))
        self.assertTrue(all(row["parameters_finite"] and row["logged_losses_finite"] for row in self.smoke["results"]))
        self.assertFalse(self.smoke["performance_ranking_computed"])
        self.assertFalse(self.smoke["final_performance_claimed"])
        self.assertFalse(self.smoke["model_or_checkpoint_created"])

    def test_scalers_have_exact_dimensions_train_only_and_shared_p_pairs(self) -> None:
        self.assertEqual(self.scalers["fit_case_count"], 1970)
        self.assertEqual(self.scalers["test_case_count_used"], 0)
        self.assertTrue(self.scalers["p0_p1_share_same_scaler_for_each_state"])
        self.assertTrue(self.scalers["binary_and_mask_fields_unchanged"])
        self.assertEqual(self.scalers["scalers"]["S0"]["dimension"], 34)
        self.assertEqual(self.scalers["scalers"]["S1"]["dimension"], 42)
        self.assertEqual(len(self.scalers["scalers"]["S0"]["fields"]), 34)
        self.assertEqual(len(self.scalers["scalers"]["S1"]["fields"]), 42)

    def test_source_scope_and_immutable_inputs(self) -> None:
        self.assertEqual(self.snapshot["source_remote_main_at_start"], "a7821b43b608180f52e471c4bd8247d60336d8ef")
        self.assertEqual(self.snapshot["remifentanil_exact_track"], "Orchestra/RFTN20_RATE")
        self.assertEqual(self.snapshot["train_remifentanil_logical_access_count"], 1970)
        self.assertFalse(self.snapshot["phase8a_membership_changed"])
        self.assertFalse(self.snapshot["phase8a_seal_changed"])
        self.assertEqual(self.snapshot["phase8a_seal_payload_sha256"], "6083be99567d5d7d4989ef3c9e35fc51255f614098697f289daac756d643f9af")
        self.assertEqual(self.snapshot["legacy_state_before"], self.snapshot["legacy_state_after"])
        self.assertTrue(all(value is False or value == 0 for value in self.snapshot["execution_flags"].values()))

    def test_single_seed_decision_supersedes_but_does_not_erase_history(self) -> None:
        historical = json.loads((MANIFESTS / "protocol_v1_3_seed_protocol.json").read_text(encoding="utf-8"))
        current = json.loads((MANIFESTS / "phase8c_human_decisions.json").read_text(encoding="utf-8"))
        self.assertEqual(historical["final_ppo_seeds"], [7, 42, 84])
        self.assertEqual(current["canonical_ppo_seed"], 42)
        self.assertEqual(current["multi_seed_plan_status"], "superseded_by_single_seed_42")
        self.assertFalse(current["seed_sweep_allowed"])

    def test_public_artifacts_are_aggregate_only_and_contain_no_local_path(self) -> None:
        public = [
            SUMMARY_PATH,
            MANIFESTS / "phase8c_scaler_registry.json",
            MANIFESTS / "phase8c_smoke_summary.json",
            MANIFESTS / "phase8c_source_snapshot.json",
            MANIFESTS / "phase8c_human_decisions.json",
            ROOT / "docs/phase8c_train_runtime_input_design.md",
            ROOT / "docs/phase8c_train_runtime_input_report.md",
        ]
        for path in public:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("C:\\Users\\", text)
            self.assertNotIn("selected_caseids", text)
            self.assertNotIn("event_timestamps", text)
            self.assertNotIn("remifentanil_timestamp_seconds.npy", text)
            self.assertNotIn("patient_profile.json", text)

    def test_private_raw_model_checkpoint_tracking_is_zero(self) -> None:
        ignored = subprocess.check_output(["git", "check-ignore", str(PRIVATE.relative_to(ROOT))], cwd=ROOT, text=True).strip()
        self.assertTrue(ignored)
        tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        self.assertFalse(any(path.startswith(("data/processed/", "data/raw/", "data/modeling/", "checkpoints/")) for path in tracked))
        self.assertFalse(any(path.endswith((".npy", ".npz", ".pt", ".pth", ".ckpt")) for path in tracked))

    def test_inventory_is_self_excluded_exact_and_public_only(self) -> None:
        inventory = json.loads((MANIFESTS / "phase8c_artifact_checksums.json").read_text(encoding="utf-8"))
        self.assertTrue(inventory["self_excluded"])
        paths = [entry["relative_path"] for entry in inventory["artifacts"]]
        self.assertEqual(paths, sorted(paths))
        self.assertNotIn("data/manifests/phase8c_artifact_checksums.json", paths)
        self.assertNotIn("PHASE_STATUS.md", paths)
        self.assertFalse(any(path.startswith("data/processed/") for path in paths))
        for entry in inventory["artifacts"]:
            path = ROOT / entry["relative_path"]
            self.assertEqual(path.stat().st_size, entry["bytes"])
            self.assertEqual(sha256_path(path), entry["sha256"])


if __name__ == "__main__":
    unittest.main()

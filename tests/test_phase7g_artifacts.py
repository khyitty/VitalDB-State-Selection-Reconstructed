import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"


def load(name):
    return json.loads((MANIFESTS / name).read_text(encoding="utf-8"))


class Phase7GArtifactTests(unittest.TestCase):
    def test_human_decisions_have_exact_approved_and_pending_ids(self):
        payload = load("phase7g_stage_ii_human_decisions.json")
        approved = {row["id"] for row in payload["approved_decisions"]}
        self.assertEqual(approved, {*(f"MC-{n:03d}" for n in range(10, 19)), "MC-031", "MC-032"})
        self.assertEqual(set(payload["still_pending_ids"]), {*(f"MC-{n:03d}" for n in range(19, 31)), "MC-033", "MC-034"})

    def test_state_schemas_are_exact_and_prefix_preserving(self):
        s0 = load("phase7g_s0_state_schema.json")
        s1 = load("phase7g_s1_state_schema.json")
        self.assertEqual(s0["dimension"], 34)
        self.assertEqual(s1["dimension"], 42)
        self.assertEqual(s1["ordered_fields"][:34], s0["ordered_fields"])
        self.assertFalse(s0["contains_sqi_value"])
        self.assertFalse(s1["contains_reason_code"])

    def test_four_configs_and_validation_scenarios(self):
        configs = load("phase7g_four_condition_configs.json")
        self.assertEqual({row["condition_id"] for row in configs["conditions"]}, {"P0S0", "P1S0", "P0S1", "P1S1"})
        scenarios = load("phase7g_synthetic_validation_scenarios.json")
        self.assertEqual(len(scenarios["scenarios"]), 5)
        self.assertTrue(all(row["source_type"] == "synthetic" and row["passed"] for row in scenarios["scenarios"]))
        self.assertFalse(scenarios["control_performance_claimed"])

    def test_source_snapshot_preserves_boundaries_and_dependency_hash(self):
        snapshot = load("phase7g_source_snapshot.json")
        self.assertEqual(snapshot["frozen_case_count"], 2460)
        self.assertEqual(snapshot["frozen_subject_count"], 2415)
        self.assertEqual(snapshot["input_artifact_sha256"]["pyproject.toml"], "0e403ab599452d41b32938e2a558a69af326e398229f8657d2a6fa24efbc9ff8")
        self.assertEqual(snapshot["legacy_state_before"], snapshot["legacy_state_after"])
        flags = snapshot["execution_flags"]
        for key in ("raw_vitaldb_access", "subject_metadata_access", "split_created", "test_seal_created", "modeling_array_created", "gymnasium_imported", "stable_baselines3_imported", "torch_imported", "ppo_implemented", "checkpoint_created", "training_run", "evaluation_run"):
            self.assertFalse(flags[key])

    def test_artifact_checksum_manifest(self):
        payload = load("phase7g_artifact_checksums.json")
        self.assertTrue(payload["self_excluded"])
        self.assertGreaterEqual(len(payload["artifacts"]), 20)
        for row in payload["artifacts"]:
            path = ROOT / row["relative_path"]
            self.assertTrue(path.is_file(), row["relative_path"])
            self.assertEqual(path.stat().st_size, row["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])


if __name__ == "__main__":
    unittest.main()

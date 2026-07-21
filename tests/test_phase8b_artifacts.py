from __future__ import annotations

import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MANIFESTS = ROOT / "data/manifests"
PRIVATE = ROOT / "data/processed/phase8b_train_observation_templates_v1"
SUMMARY = MANIFESTS / "phase8b_private_tree_summary.json"

from vitaldb_state_selection.anesthesia.recorded_observation import TrainObservationTemplateStore  # noqa: E402
from vitaldb_state_selection.anesthesia import (  # noqa: E402
    AnesthesiaEnvironmentCore, EnvironmentConfig, PreprocessingID, StateID,
)
from vitaldb_state_selection.cohort.train_observation_templates import sha256_path  # noqa: E402
from vitaldb_state_selection.pkpd import PatientProfile, Sex  # noqa: E402


@unittest.skipUnless(SUMMARY.is_file(), "official Phase 8B artifacts not generated yet")
class Phase8BArtifactTests(unittest.TestCase):
    def test_full_private_accounting_and_store_fingerprint(self) -> None:
        store = TrainObservationTemplateStore(PRIVATE, ROOT)
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        self.assertEqual(len(store.rows), 1970)
        self.assertEqual(len({row["caseid"] for row in store.rows}), 1970)
        self.assertEqual(len({row["template_id"] for row in store.rows}), 1970)
        self.assertTrue(all(row["assigned_split"] == "train" for row in store.rows))
        self.assertEqual(summary["test_template_count"], 0)
        self.assertEqual(store.verify_all(), summary["private_template_store_root_sha256"])
        self.assertEqual(sha256_path(PRIVATE / "private_index.csv"), summary["private_index_sha256"])
        self.assertEqual(sha256_path(PRIVATE / "access_ledger.csv"), summary["private_access_ledger_sha256"])

    def test_access_ledger_exact_scope(self) -> None:
        import csv
        with (PRIVATE / "access_ledger.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3940)
        self.assertEqual(Counter(row["track_name"] for row in rows), {"BIS/BIS": 1970, "BIS/SQI": 1970})
        self.assertTrue(all(row["assigned_split"] == "train" and row["status"] == "complete" for row in rows))
        self.assertTrue(all(row["expected_source_sha256"] == row["observed_source_sha256"] for row in rows))
        access = json.loads((MANIFESTS / "phase8b_access_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(access["test_logical_file_access_count"], 0)
        self.assertEqual(access["drug_logical_file_access_count"], 0)
        self.assertEqual(access["source_checksum_mismatch_count"], 0)

    def test_qc_hard_gates_and_visibility(self) -> None:
        qc = json.loads((MANIFESTS / "phase8b_template_qc_summary.json").read_text(encoding="utf-8"))
        self.assertTrue(all(value == 0 for value in qc["structural_hard_gates"].values()))
        visibility = qc["visibility_audit"]
        self.assertGreater(visibility["p0_visible_grid_points"], 0)
        self.assertGreater(visibility["p1_visible_grid_points"], 0)
        self.assertEqual(visibility["templates_with_zero_p0_visibility"], 0)
        self.assertEqual(visibility["templates_with_zero_p1_visibility"], 0)
        self.assertFalse(visibility["scientific_result"])

    def test_public_artifacts_contain_no_event_or_mapping_payload(self) -> None:
        public = [path for path in MANIFESTS.glob("phase8b_*") if path.name != "phase8b_artifact_checksums.json"]
        for path in public:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("bis_timestamp_seconds.npy", text if path.name != "phase8b_private_template_schema.json" else "")
            self.assertNotIn("sqi_value\": [", text)
            self.assertNotIn("C:\\Users\\", text)
        decisions = json.loads((MANIFESTS / "phase8b_train_template_human_decisions.json").read_text(encoding="utf-8"))
        self.assertFalse(decisions["public_event_level_data_authorized"])
        self.assertFalse(decisions["raw_bis_persistence_authorized"])

    def test_public_inventory_is_self_excluded_and_exact(self) -> None:
        inventory = json.loads((MANIFESTS / "phase8b_artifact_checksums.json").read_text(encoding="utf-8"))
        self.assertTrue(inventory["self_excluded"])
        paths = [entry["relative_path"] for entry in inventory["artifacts"]]
        self.assertEqual(paths, sorted(paths))
        self.assertNotIn("data/manifests/phase8b_artifact_checksums.json", paths)
        self.assertNotIn("PHASE_STATUS.md", paths)
        self.assertFalse(any(path.startswith("data/processed/") for path in paths))
        for entry in inventory["artifacts"]:
            path = ROOT / entry["relative_path"]
            self.assertEqual(path.stat().st_size, entry["bytes"])
            self.assertEqual(sha256_path(path), entry["sha256"])

    def test_private_store_ignored_untracked_and_no_model_artifacts(self) -> None:
        ignored = subprocess.check_output(["git", "check-ignore", str(PRIVATE.relative_to(ROOT))], cwd=ROOT, text=True).strip()
        self.assertTrue(ignored)
        tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
        self.assertFalse(any(path.startswith(("data/processed/", "data/raw/", "data/modeling/", "checkpoints/")) for path in tracked))
        self.assertFalse(any(path.endswith((".npy", ".npz", ".pt", ".pth", ".ckpt")) for path in tracked))

    def test_source_snapshot_lineage_and_prohibited_execution(self) -> None:
        snapshot = json.loads((MANIFESTS / "phase8b_source_snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot["operational_timing_source"]["sha256"], "911e4b44e626cc9f7d4944c825011c8e6b7b5b2be486dd8d7a29af9586913d5d")
        self.assertEqual(snapshot["upstream_authoritative_timing_lineage"]["sha256"], "66c65af9fa72467c29544e6d9c84550449370e61781b703461f83508964f30a8")
        self.assertEqual(snapshot["timing_lineage_mismatch_count"], 0)
        for field in ("normalization_fitted", "real_subject_simulator_run", "ppo_training", "ppo_evaluation", "model_or_checkpoint_created"):
            self.assertFalse(snapshot[field])
        self.assertTrue(snapshot["legacy_unchanged"])

    def test_one_private_template_is_structurally_compatible_with_p0_and_p1(self) -> None:
        store = TrainObservationTemplateStore(PRIVATE, ROOT)
        template = store.load_case(store.rows[0]["caseid"])
        profile = PatientProfile(age_years=45, sex=Sex.FEMALE, height_cm=165, weight_kg=60)
        for preprocessing in (PreprocessingID.P0, PreprocessingID.P1):
            environment = AnesthesiaEnvironmentCore(
                profile=profile,
                config=EnvironmentConfig(preprocessing, StateID.S0, episode_horizon_seconds=30.0),
                observation_template=template,
            )
            state, _ = environment.reset(seed=7)
            self.assertEqual(state.shape, (34,))
            for _step in range(3):
                state, _reward, terminated, truncated, _info = environment.step(0.0)
                self.assertEqual(state.shape, (34,))
                if terminated or truncated:
                    break
            self.assertEqual(environment.template.template_id, template.template_id)

    def test_verify_only_is_read_only(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/run_phase8b_train_template_extraction.py", "--stage", "verify-only"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

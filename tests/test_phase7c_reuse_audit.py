from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase7CReuseAuditTests(unittest.TestCase):
    def test_audit_utility_is_read_only_and_bounded(self) -> None:
        text = (ROOT / "scripts/audit_phase7c_reuse.py").read_text(encoding="utf-8")
        for forbidden in (
            "vitaldb.load_case",
            "model.learn(",
            "torch.save",
            "git reset",
            "git clean",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("duration_seconds=10", text)

    def test_source_snapshot_records_expected_probe_boundary(self) -> None:
        snapshot = json.loads(
            (ROOT / "data/manifests/phase7c_source_snapshot.json").read_text(encoding="utf-8")
        )
        self.assertEqual(snapshot["legacy_repository"]["commit_sha"], "9501b16a5c4db27f06fa0d0b252a3a75f633967f")
        self.assertEqual(snapshot["probes"]["simulator_reset_and_one_step"]["returncode"], 0)
        self.assertNotEqual(snapshot["probes"]["environment_import"]["returncode"], 0)
        self.assertNotEqual(snapshot["probes"]["ppo_import"]["returncode"], 0)
        self.assertFalse(snapshot["raw_vitaldb_accessed"])
        self.assertFalse(snapshot["ppo_training_run"])
        self.assertFalse(snapshot["checkpoint_created"])

    def test_reuse_classifications_are_closed_and_not_overclaimed(self) -> None:
        with (ROOT / "data/manifests/phase7c_component_reuse_audit.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        allowed = {
            "executable_and_reusable",
            "executable_after_small_refactor",
            "partial_reference_only",
            "placeholder",
            "missing",
            "prohibited_artifact",
        }
        self.assertEqual(len(rows), 16)
        self.assertTrue(all(row["classification"] in allowed for row in rows))
        executable = [row for row in rows if row["classification"] == "executable_and_reusable"]
        self.assertEqual({row["component"] for row in executable}, {"patient_simulator", "pk_pd_model"})
        self.assertTrue(all(row["synthetic_probe"] == "passed" for row in executable))

    def test_missing_encoding_options_remain_pending(self) -> None:
        with (ROOT / "data/manifests/phase7c_missing_encoding_options.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({row["option"] for row in rows}, {"A", "B", "C"})
        self.assertTrue(all(row["status"] != "approved" for row in rows))
        self.assertEqual(
            {row["status"] for row in rows},
            {"candidate_pending_human_approval", "recommended_pending_human_approval"},
        )

    def test_phase7c_does_not_make_research_outputs(self) -> None:
        tracked_or_present = {
            path.name for path in (ROOT / "data/manifests").glob("phase7c_*")
        }
        self.assertFalse(any("split" in name or "checkpoint" in name for name in tracked_or_present))
        self.assertIsNotNone(importlib.util.spec_from_file_location("phase7c_audit", ROOT / "scripts/audit_phase7c_reuse.py"))

    def test_artifact_checksum_manifest_is_complete(self) -> None:
        manifest = json.loads(
            (ROOT / "data/manifests/phase7c_artifact_checksums.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["artifact_count"], 13)
        self.assertEqual(len(manifest["artifacts"]), 13)
        for row in manifest["artifacts"]:
            path = ROOT / row["path"]
            self.assertEqual(path.stat().st_size, row["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])


if __name__ == "__main__":
    unittest.main()

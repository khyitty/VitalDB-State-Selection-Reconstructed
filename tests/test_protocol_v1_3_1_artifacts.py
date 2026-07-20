from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"


def read_json(name: str) -> dict:
    return json.loads((MANIFESTS / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProtocolV131ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = read_json("protocol_v1_3_1_source_snapshot.json")
        cls.p0 = read_json("protocol_v1_3_1_p0_online_schema.json")
        cls.p1 = read_json("protocol_v1_3_1_p1_online_schema.json")
        cls.missing = read_json("protocol_v1_3_1_missing_encoding_decision.json")
        cls.s0 = read_json("protocol_v1_3_1_s0_state_schema.json")
        cls.s1 = read_json("protocol_v1_3_1_s1_state_schema.json")
        cls.template = read_json("protocol_v1_3_1_observation_template_contract.json")

    def test_source_remote_upstream_and_cohort_are_fixed(self) -> None:
        self.assertEqual(
            self.source["source_remote_main_at_start"],
            "989dc909e7e2380d27c5fb1b3ab8601018ef68f7",
        )
        self.assertEqual((self.source["frozen_case_count"], self.source["frozen_subject_count"]), (2460, 2415))
        self.assertEqual(
            sha256(MANIFESTS / "final_eligible_cohort_manifest.csv"),
            self.source["expected_final_cohort_sha256"],
        )
        subject = read_json("subject_linkage_summary.json")
        self.assertEqual(subject["total_case_count"], 2460)
        self.assertEqual(subject["unique_subject_count"], 2415)
        self.assertEqual(subject["subject_linkage_sha256"], self.source["expected_subject_linkage_sha256"])

    def test_protocol_v12_v13_artifact_checksums_remain_valid(self) -> None:
        v12 = read_json("protocol_v1_2_artifact_checksums.json")
        for relative_path, expected_hash in v12.items():
            path = ROOT / relative_path
            self.assertEqual(sha256(path), expected_hash, path)
        v13 = read_json("protocol_v1_3_artifact_checksums.json")
        for row in v13["artifacts"]:
            path = ROOT / row["relative_path"]
            self.assertEqual(path.stat().st_size, row["bytes"], path)
            self.assertEqual(sha256(path), row["sha256"], path)
        self.assertFalse(self.source["old_protocol_v1_3_artifacts_modified"])

    def test_online_pipelines_have_only_bundled_bis_difference(self) -> None:
        self.assertEqual(self.p0["sqi_rule"], "not_required")
        self.assertEqual(self.p1["sqi_rule"], "exact_timestamp_gte_50")
        self.assertEqual(self.p1["sqi_exact_timestamp_threshold"], 50)
        self.assertEqual((self.p0["bis_staleness_cap_seconds"], self.p1["bis_staleness_cap_seconds"]), (30, 20))
        for field in (
            "drug_histories",
            "drug_staleness_contrast",
            "drug_artificial_missingness",
            "drug_availability_mask_in_state",
            "drug_observation_age_in_state",
            "history_relative_seconds",
            "grid_interval_seconds",
        ):
            self.assertEqual(self.p0[field], self.p1[field], field)
        self.assertFalse(self.p0["drug_staleness_contrast"])

    def test_retrospective_ids_are_preserved_but_not_online_ids(self) -> None:
        rows = read_csv("protocol_v1_3_1_preprocessing_distinction.csv")
        self.assertEqual(len(rows), 7)
        drug_hold = next(row for row in rows if row["component"] == "Drug-rate hold")
        self.assertEqual(drug_hold["online_protocol_v1_3_1"], "none vs none")
        self.assertEqual(
            drug_hold["relationship"], "retrospective_component_removed_from_online_protocol"
        )
        self.assertNotEqual(self.p0["pipeline_id"], self.p0["retrospective_source_candidate"])
        self.assertNotEqual(self.p1["pipeline_id"], self.p1["retrospective_source_candidate"])

    def test_option_b_state_contract_and_zero_semantics(self) -> None:
        self.assertEqual(self.missing["selection"], "Option_B_minimal")
        self.assertEqual(self.missing["status"], "human_approved_structure")
        self.assertEqual(self.missing["unavailable_bis"]["value_placeholder"], 0)
        self.assertEqual(self.missing["unavailable_bis"]["availability_mask"], 0)
        self.assertEqual(self.missing["available_bis_zero"], {"availability_mask": 1, "value": 0})
        self.assertFalse(self.missing["no_prior_state_channel"])
        self.assertIsNone(self.missing["age_clip_maximum_seconds"])
        self.assertFalse(self.missing["implemented_in_phase7d"])

    def test_s0_s1_dimensions_and_sqi_exclusion(self) -> None:
        self.assertEqual(self.s0["conceptual_dimension"], 34)
        self.assertEqual(self.s0["bis_history"]["conceptual_dimension"], 18)
        self.assertEqual(self.s0["drug_histories"]["conceptual_dimension"], 12)
        self.assertFalse(self.s0["drug_histories"]["mask_or_age_channels"])
        self.assertEqual(self.s1["strict_superset_of"], "S0")
        self.assertEqual(self.s1["conceptual_dimension"], 42)
        self.assertEqual(len(self.s1["additional_features"]), 8)
        self.assertFalse(self.s0["sqi_numeric_value_included"])
        self.assertFalse(self.s1["sqi_numeric_value_included"])

    def test_template_contract_is_outcome_blind_and_not_extracted(self) -> None:
        self.assertIn("bis_sqi_values", self.template["included_fields"])
        self.assertIn("raw_observed_bis_values", self.template["excluded_fields"])
        self.assertTrue(self.template["same_template_for_p0_and_p1"])
        self.assertTrue(self.template["same_latent_trajectory_for_p0_and_p1"])
        self.assertEqual(self.template["reward_bis_source"], "latent_true_bis")
        self.assertFalse(self.template["template_extracted_in_phase7d"])

    def test_lab_handoff_uses_closed_statuses_and_has_korean_draft(self) -> None:
        rows = read_csv("protocol_v1_3_1_lab_handoff_checklist.csv")
        allowed = {
            "already_available",
            "available_but_unverified",
            "missing_request_from_lab",
            "conflicting",
            "not_needed",
        }
        self.assertEqual(len(rows), 21)
        self.assertTrue(all(row["status"] in allowed for row in rows))
        draft = (ROOT / "docs" / "phase7d_lab_request_ko.md").read_text(encoding="utf-8")
        self.assertIn("교수님", draft)
        self.assertNotRegex(draft, r"[A-Za-z]:\\Users\\|/home/")

    def test_backup_summary_is_recoverable_without_absolute_path(self) -> None:
        backup = self.source["backup_verification"]
        self.assertEqual(backup["excluded_path_count"], 14)
        self.assertEqual(backup["exact_copy_sha256_verified_count"], 14)
        self.assertEqual(backup["tracked_reconstruction_verified_count"], 5)
        self.assertTrue(backup["binary_patch_apply_check"])
        self.assertFalse(backup["backup_committed_to_git"])
        text = (ROOT / "docs" / "phase7d_excluded_scaffold_backup_verification.md").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"[A-Za-z]:\\Users\\|/home/")

    def test_no_split_raw_dependency_or_model_execution(self) -> None:
        self.assertFalse(self.source["dependency_files_changed"])
        self.assertEqual(sha256(ROOT / "pyproject.toml"), self.source["input_artifact_sha256"]["pyproject.toml"])
        self.assertEqual(subprocess.check_output(["git", "ls-files", "data/raw"], cwd=ROOT, text=True).splitlines(), [])
        self.assertTrue(all(value in (False, 0) for value in self.source["execution_flags"].values()))
        prohibited_names = re.compile(r"(train_ids|test_ids|test_seal|modeling_array|checkpoint)", re.I)
        phase_paths = [path.name for path in MANIFESTS.glob("protocol_v1_3_1*")]
        self.assertEqual([name for name in phase_paths if prohibited_names.search(name)], [])
        self.assertFalse((ROOT / "src" / "vitaldb_state_selection" / "pkpd" / "simulator.py").exists())
        self.assertFalse((ROOT / "src" / "vitaldb_state_selection" / "rl" / "ppo.py").exists())

    def test_artifact_checksum_manifest_and_report_boundary(self) -> None:
        inventory = read_json("protocol_v1_3_1_artifact_checksums.json")
        self.assertTrue(inventory["self_excluded"])
        self.assertEqual(len(inventory["artifacts"]), 19)
        for row in inventory["artifacts"]:
            path = ROOT / row["relative_path"]
            self.assertEqual(path.stat().st_size, row["bytes"], path)
            self.assertEqual(sha256(path), row["sha256"], path)
        report = (ROOT / "docs" / "phase7d_online_observation_contract_report.md").read_text(encoding="utf-8")
        self.assertIn("No split", report)
        self.assertIn("no artificial drug missingness", report)
        self.assertIn("34 and 42 conceptual fields", report)

    def test_legacy_repository_snapshot_is_unchanged(self) -> None:
        self.assertTrue(self.source["legacy_state_unchanged"])
        self.assertEqual(self.source["legacy_state_before"], self.source["legacy_state_after"])


if __name__ == "__main__":
    unittest.main()

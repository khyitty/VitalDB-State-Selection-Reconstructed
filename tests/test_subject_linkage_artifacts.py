from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.subject_linkage import (  # noqa: E402
    EXPECTED_CLUSTER_SIZE_COUNTS,
    SOURCE_ELIGIBLE_IDS_SHA256,
    SOURCE_PHASE6D_FOLLOWUP,
    sorted_caseid_checksum,
    subject_linkage_checksum,
)


def read_csv(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SubjectLinkageArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.linkage = read_csv("subject_linkage_case_manifest.csv")
        cls.clusters = read_csv("subject_level_cluster_summary.csv")
        cls.distribution = read_csv("repeated_subject_distribution.csv")
        cls.consistency = read_csv("within_subject_metadata_consistency.csv")
        cls.alternatives = read_csv("alternative_split_objective_comparison.csv")
        cls.summary = json.loads((MANIFESTS / "subject_linkage_summary.json").read_text(encoding="utf-8"))
        cls.feasibility = json.loads(
            (MANIFESTS / "patient_level_split_feasibility_summary.json").read_text(encoding="utf-8")
        )
        cls.source = json.loads((MANIFESTS / "subject_linkage_source_snapshot.json").read_text(encoding="utf-8"))

    def test_complete_2460_case_to_subject_linkage_is_unambiguous(self) -> None:
        self.assertEqual(len(self.linkage), 2460)
        self.assertEqual(len({int(row["caseid"]) for row in self.linkage}), 2460)
        self.assertTrue(all(row["subjectid"] for row in self.linkage))
        self.assertEqual(sorted_caseid_checksum([int(row["caseid"]) for row in self.linkage]), SOURCE_ELIGIBLE_IDS_SHA256)
        eligible = read_csv("final_eligible_caseids.csv")
        self.assertEqual(
            {int(row["caseid"]) for row in self.linkage},
            {int(row["caseid"]) for row in eligible},
        )
        ineligible = {int(row["caseid"]) for row in read_csv("final_ineligible_caseids.csv")}
        self.assertEqual({int(row["caseid"]) for row in self.linkage} & ineligible, set())
        self.assertEqual(subject_linkage_checksum(self.linkage), self.summary["subject_linkage_sha256"])

    def test_no_split_membership_or_seal_exists(self) -> None:
        self.assertTrue(all(row["split_created"] == "false" for row in self.linkage))
        self.assertTrue(all(row["assigned_split"] == "" for row in self.linkage))
        self.assertTrue(all(row["split_created"] == "false" for row in self.clusters))
        self.assertTrue(all(row["assigned_split"] == "" for row in self.clusters))
        self.assertFalse(self.summary["split_created"])
        self.assertEqual(self.summary["assigned_split_nonblank_count"], 0)
        self.assertFalse(self.summary["test_seal_created"])
        self.assertFalse(self.feasibility["allocation_executed"])
        self.assertFalse(self.feasibility["alternative_selected"])

    def test_subject_accounting_and_cluster_distribution_are_exact(self) -> None:
        self.assertEqual(len(self.clusters), 2415)
        counts = Counter(int(row["subject_case_count"]) for row in self.clusters)
        self.assertEqual(dict(sorted(counts.items())), EXPECTED_CLUSTER_SIZE_COUNTS)
        self.assertEqual(self.summary["total_case_count"], 2460)
        self.assertEqual(self.summary["unique_subject_count"], 2415)
        self.assertEqual(self.summary["subjects_with_exactly_1_case"], 2378)
        self.assertEqual(self.summary["subjects_with_exactly_2_cases"], 35)
        self.assertEqual(self.summary["subjects_with_exactly_3_cases"], 1)
        self.assertEqual(self.summary["subjects_with_4_or_more_cases"], 1)
        self.assertEqual(self.summary["repeated_subject_case_count"], 82)
        self.assertEqual(self.summary["largest_subject_cluster_case_count"], 9)
        self.assertEqual(sum(int(row["subject_count"]) for row in self.distribution), 2415)
        self.assertEqual(sum(int(row["case_count"]) for row in self.distribution), 2460)

    def test_within_subject_consistency_is_descriptive_only(self) -> None:
        self.assertEqual(len(self.consistency), 2415)
        self.assertTrue(all(row["linkage_changed_from_metadata_variation"] == "false" for row in self.consistency))
        warning_count = sum(row["sex_inconsistency_warning"] == "true" for row in self.consistency)
        self.assertEqual(warning_count, self.summary["sex_inconsistency_warning_subject_count"])
        self.assertTrue(all(int(row["distinct_asa_count"]) >= 1 for row in self.consistency))

    def test_count_only_feasibility_has_no_membership(self) -> None:
        self.assertEqual(
            {name: value["nearest_integer"] for name, value in self.feasibility["case_count_targets"].items()},
            {"train": 1722, "validation": 369, "test": 369},
        )
        self.assertEqual(
            {name: value["nearest_integer"] for name, value in self.feasibility["subject_count_targets"].items()},
            {"train": 1691, "validation": 362, "test": 362},
        )
        self.assertTrue(self.feasibility["exact_case_targets_arithmetically_feasible"])
        self.assertTrue(self.feasibility["exact_joint_nearest_case_and_subject_targets_arithmetically_feasible"])
        self.assertEqual(self.feasibility["minimum_total_absolute_case_count_deviation_under_nearest_subject_targets"], 0)
        self.assertEqual(self.feasibility["analysis_type"], "cluster_size_histogram_only_no_subject_membership_allocation")

    def test_metadata_inventory_preserves_case_level_contributions(self) -> None:
        definitions = json.loads(
            (MANIFESTS / "patient_level_balance_variable_definitions.json").read_text(encoding="utf-8")
        )
        self.assertIn("sum of all case-level marginal contribution vectors", definitions["subject_allocation_rule"])
        self.assertFalse(definitions["variables"]["bmi_group"]["eligibility_role"])
        self.assertFalse(definitions["variables"]["bmi_group"]["model_feature_role"])
        self.assertEqual(len(self.alternatives), 3)
        self.assertTrue(all(row["selected"] == "false" for row in self.alternatives))
        self.assertTrue(all(row["allocation_executed"] == "false" for row in self.alternatives))

    def test_source_checksums_and_prohibited_execution_flags(self) -> None:
        self.assertEqual(self.source["source_phase6d_followup"], SOURCE_PHASE6D_FOLLOWUP)
        self.assertTrue(self.source["phase6d_remote_sha_verified_before_phase7a"])
        for relative, expected in self.source["source_artifact_sha256"].items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)
        self.assertEqual(self.source["raw_tree_before"], self.source["raw_tree_after"])
        self.assertTrue(self.source["legacy_state_unchanged"])
        for field in (
            "split_created", "provisional_split_created", "split_id_list_created", "test_seal_created",
            "modeling_arrays_created", "preprocessing_statistics_fitted",
        ):
            self.assertFalse(self.source[field], field)
        for field in ("raw_signal_file_open_count", "api_request_count", "new_raw_file_count", "outcome_access_count"):
            self.assertEqual(self.source[field], 0, field)
        self.assertEqual(subprocess.check_output(["git", "ls-files", "data/raw"], cwd=ROOT, text=True).splitlines(), [])

    def test_artifact_checksums_and_report_boundary(self) -> None:
        inventory = json.loads(
            (MANIFESTS / "subject_linkage_artifact_checksums.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(inventory), 10)
        for relative, expected in inventory.items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)
        report = (ROOT / "docs" / "phase7a_subject_linkage_audit_report.md").read_text(encoding="utf-8")
        self.assertIn("No subject or case was assigned to a split", report)
        self.assertIn("Phase 7B patient-level allocation is not authorized", report)

    def test_production_entrypoint_has_no_raw_api_or_model_capability(self) -> None:
        code = (ROOT / "scripts" / "run_subject_linkage_audit.py").read_text(encoding="utf-8")
        for prohibited in ("import requests", "VitalDBOpenAPI", "parse_observation", "numpy", "pandas", "sklearn", "torch"):
            self.assertNotIn(prohibited, code)


if __name__ == "__main__":
    unittest.main()

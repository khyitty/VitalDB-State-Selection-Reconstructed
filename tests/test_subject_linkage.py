from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.subject_linkage import (  # noqa: E402
    age_group,
    asa_group,
    bmi_group,
    build_subject_cluster_rows,
    calculate_bmi,
    count_only_split_feasibility,
    emergency_group,
    nearest_integer_targets,
    repeated_subject_distribution,
    sex_group,
    subject_accounting,
)
from vitaldb_state_selection.data.access_policy import (  # noqa: E402
    TestAccessDenied,
    assert_disjoint_split_ids,
    authorize_access,
)


class SubjectLinkageTests(unittest.TestCase):
    def test_metadata_groups_are_deterministic_and_noninferential(self) -> None:
        self.assertEqual(sex_group("M"), "male")
        self.assertEqual(sex_group("F"), "female")
        self.assertEqual(sex_group("unknown"), "missing_or_other")
        self.assertEqual(age_group("39.9"), "18_to_lt_40")
        self.assertEqual(age_group("40"), "40_to_lt_60")
        self.assertEqual(age_group("75"), "ge_75")
        bmi = calculate_bmi("170", "70")
        self.assertAlmostEqual(bmi or 0, 70 / 1.7**2)
        self.assertEqual(bmi_group(bmi), "18_5_to_lt_25")
        self.assertEqual(asa_group("4"), "ASA_4_or_higher")
        self.assertEqual(asa_group(""), "missing_or_other")
        self.assertEqual(emergency_group("0"), "non_emergency")
        self.assertEqual(emergency_group("1"), "emergency")

    def test_subject_consistency_preserves_warning_without_changing_linkage(self) -> None:
        rows = [
            {"caseid": 1, "subjectid": "s1", "subject_case_count": 2, "sex_source_value": "M", "age": 20.0,
             "height_cm": 170.0, "weight_kg": 70.0, "bmi_calculated": 24.2, "asa_source_value": "1",
             "emergency_group": "non_emergency", "operation_type_source_value": "A"},
            {"caseid": 2, "subjectid": "s1", "subject_case_count": 2, "sex_source_value": "F", "age": 21.0,
             "height_cm": 171.0, "weight_kg": 71.0, "bmi_calculated": 24.3, "asa_source_value": "2",
             "emergency_group": "emergency", "operation_type_source_value": "B"},
            {"caseid": 3, "subjectid": "s2", "subject_case_count": 1, "sex_source_value": "F", "age": 30.0,
             "height_cm": 160.0, "weight_kg": 50.0, "bmi_calculated": 19.5, "asa_source_value": "1",
             "emergency_group": "non_emergency", "operation_type_source_value": "A"},
        ]
        clusters, consistency = build_subject_cluster_rows(rows)
        self.assertEqual(len(clusters), 2)
        by_subject = {row["subjectid"]: row for row in consistency}
        self.assertTrue(by_subject["s1"]["sex_inconsistency_warning"])
        self.assertFalse(by_subject["s1"]["linkage_changed_from_metadata_variation"])
        self.assertEqual(by_subject["s1"]["age_range"], 1.0)
        self.assertEqual(by_subject["s1"]["distinct_operation_type_count"], 2)

    def test_count_only_feasibility_creates_no_assignment(self) -> None:
        clusters = [
            {"subjectid": "s1", "subject_case_count": 2, "assigned_split": ""},
            {"subjectid": "s2", "subject_case_count": 1, "assigned_split": ""},
            {"subjectid": "s3", "subject_case_count": 1, "assigned_split": ""},
            {"subjectid": "s4", "subject_case_count": 1, "assigned_split": ""},
        ]
        first = count_only_split_feasibility(clusters)
        second = count_only_split_feasibility(clusters)
        self.assertEqual(first, second)
        self.assertFalse(first["split_created"])
        self.assertEqual(first["assigned_split_count"], 0)
        self.assertEqual(nearest_integer_targets(5), {"train": 3, "validation": 1, "test": 1})
        self.assertEqual(sum(row["subject_count"] for row in repeated_subject_distribution(clusters)), 4)
        self.assertEqual(subject_accounting(clusters)["total_case_count"], 5)

    def test_access_policy_is_fail_closed_for_test_and_fit(self) -> None:
        with self.assertRaises(TestAccessDenied):
            authorize_access("evaluation", ["test"])
        with self.assertRaises(TestAccessDenied):
            authorize_access("feature_selection", ["train", "validation"])
        with self.assertRaises(TestAccessDenied):
            authorize_access("normalization_fit", ["validation"])
        with self.assertRaises(TestAccessDenied):
            authorize_access("hyperparameter_selection", ["test"], authorization_manifest={"test_evaluation_authorized": True})
        with self.assertRaises(TestAccessDenied):
            authorize_access("target_summary", ["test"], authorization_manifest={"test_evaluation_authorized": True})
        authorize_access("early_stopping", ["train", "validation"])
        authorize_access("evaluation", ["test"], authorization_manifest={"test_evaluation_authorized": True})

    def test_split_id_overlap_is_rejected_synthetically(self) -> None:
        assert_disjoint_split_ids([1], [2], [3])
        with self.assertRaises(TestAccessDenied):
            assert_disjoint_split_ids([1], [2], [1])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import ast
import hashlib
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.subject_split import (  # noqa: E402
    ALLOCATION_METHOD,
    SPLIT_SEED,
    SubjectSplitError,
    allocate_subjects,
    allocation_rank_sha256,
    build_subject_rows,
    canonical_strata,
    empirical_quantile,
    hamilton_test_quotas,
    standardized_mean_difference,
    subject_age_group,
    subject_case_count_band,
)


def source_row(caseid: str, subjectid: str, *, sex: str = "male", age: str = "45") -> dict[str, str]:
    return {
        "caseid": caseid,
        "subjectid": subjectid,
        "subject_case_count": "1",
        "sex_group": sex,
        "age": age,
        "height_cm": "170",
        "weight_kg": "70",
        "age_group": "40_to_lt_60",
        "bmi_group": "18_5_to_lt_25",
        "asa_group": "ASA_2",
        "emergency_group": "non_emergency",
        "operation_type_group": "General",
    }


class Phase8ASubjectSplitTests(unittest.TestCase):
    def test_repository_age_groups_and_case_bands_are_exact(self) -> None:
        self.assertEqual([subject_age_group(value) for value in (18, 39.9, 40, 59.9, 60, 74.9, 75)], [
            "18_to_lt_40", "18_to_lt_40", "40_to_lt_60", "40_to_lt_60",
            "60_to_lt_75", "60_to_lt_75", "ge_75",
        ])
        self.assertEqual([subject_case_count_band(value) for value in (1, 2, 3, 9)], [
            "one_case", "two_cases", "three_or_more_cases", "three_or_more_cases",
        ])
        with self.assertRaises(SubjectSplitError):
            subject_age_group(17.9)

    def test_subject_aggregation_uses_median_minimum_maximum_and_range(self) -> None:
        rows = [source_row("1", "001", age="30"), source_row("2", "001", age="50")]
        for row in rows:
            row["subject_case_count"] = "2"
        rows[0].update(height_cm="160", weight_kg="50", age_group="18_to_lt_40")
        rows[1].update(height_cm="180", weight_kg="90", age_group="40_to_lt_60")
        subject = build_subject_rows(rows, enforce_production_counts=False)[0]
        self.assertEqual(subject["subjectid"], "001")
        self.assertEqual(subject["subject_age_median"], 40.0)
        self.assertEqual((subject["age_minimum"], subject["age_maximum"], subject["age_range"]), (30.0, 50.0, 20.0))
        self.assertEqual(subject["subject_height_median_cm"], 170.0)
        self.assertEqual(subject["height_range_cm"], 20.0)
        self.assertEqual(subject["subject_weight_median_kg"], 70.0)
        self.assertEqual(subject["weight_range_kg"], 40.0)
        self.assertEqual(subject["subject_age_group"], "40_to_lt_60")
        self.assertEqual(subject["subject_age_group_distinct_count"], 2)
        self.assertTrue(subject["subject_age_group_span_warning"])

    def test_invalid_or_inconsistent_metadata_hard_fails_without_imputation(self) -> None:
        with self.assertRaises(SubjectSplitError):
            build_subject_rows([source_row("1", "1", age="nan")], enforce_production_counts=False)
        with self.assertRaises(SubjectSplitError):
            build_subject_rows([source_row("1", "1", sex="unknown")], enforce_production_counts=False)
        rows = [source_row("1", "1"), source_row("2", "1", sex="female")]
        for row in rows:
            row["subject_case_count"] = "2"
        with self.assertRaises(SubjectSplitError):
            build_subject_rows(rows, enforce_production_counts=False)

    def test_exact_identifier_text_is_preserved(self) -> None:
        subject = build_subject_rows([source_row("0007", "0012")], enforce_production_counts=False)[0]
        self.assertEqual(subject["subjectid"], "0012")
        with self.assertRaises(SubjectSplitError):
            build_subject_rows([source_row("1x", "12")], enforce_production_counts=False)

    def test_sha256_rank_uses_pinned_null_delimited_payload(self) -> None:
        key = "male|40_to_lt_60|one_case"
        expected = hashlib.sha256((f"{SPLIT_SEED}\0{key}\0" + "0012").encode("utf-8")).hexdigest()
        self.assertEqual(allocation_rank_sha256("0012", key), expected)

    def test_hamilton_exact_fraction_and_canonical_tie_break(self) -> None:
        counts = {key: 0 for key in canonical_strata()}
        for key in canonical_strata()[:5]:
            counts[key] = 1
        quotas = hamilton_test_quotas(counts, 1)
        self.assertEqual(sum(quotas.values()), 1)
        self.assertEqual(quotas[canonical_strata()[0]], 1)

    def test_toy_allocation_is_deterministic_and_target_exact(self) -> None:
        source = [source_row(str(index), str(index)) for index in range(1, 11)]
        subjects = build_subject_rows(source, enforce_production_counts=False)
        first, strata_first = allocate_subjects(subjects, train_target=8, test_target=2)
        second, strata_second = allocate_subjects(subjects, train_target=8, test_target=2)
        self.assertEqual(first, second)
        self.assertEqual(strata_first, strata_second)
        self.assertEqual(Counter(row["assigned_split"] for row in first), {"train": 8, "test": 2})
        self.assertTrue(all(row["allocation_method"] == ALLOCATION_METHOD for row in first))

    def test_quantile_sample_sd_and_smd_formulas(self) -> None:
        self.assertEqual(empirical_quantile([1, 2, 3, 4], 0.25), 1.75)
        self.assertAlmostEqual(standardized_mean_difference([1, 2, 3], [2, 3, 4]), -1.0)
        self.assertEqual(standardized_mean_difference([2, 2], [2, 2]), 0.0)
        with self.assertRaises(SubjectSplitError):
            standardized_mean_difference([1, 1], [2, 2])

    def test_production_source_uses_no_rng_hash_or_alternate_seed_path(self) -> None:
        paths = [
            ROOT / "src/vitaldb_state_selection/cohort/subject_split.py",
            ROOT / "scripts/run_phase8a_subject_split.py",
        ]
        for path in paths:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            self.assertFalse({"random", "numpy"} & imports)
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
            self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id == "hash" for node in calls))
            self.assertNotIn("--seed", source)
            self.assertNotIn("--force", source)
            self.assertNotIn("--regenerate", source)


if __name__ == "__main__":
    unittest.main()

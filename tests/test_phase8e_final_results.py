from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.publication.final_results import (  # noqa: E402
    FinalResultsError,
    build_aggregate,
    validate_private_rows,
)
from vitaldb_state_selection.publication.phase8f_renderer import CONDITIONS, CONTRASTS, METRICS  # noqa: E402
from vitaldb_state_selection.statistics.paired_evaluation import (  # noqa: E402
    CONTRAST_WEIGHTS,
    FROZEN_CONTRAST_ACCUMULATION_ORDER,
    paired_differences,
)


def fixture_rows() -> list[dict[str, object]]:
    rows = []
    for condition_index, condition in enumerate(CONDITIONS):
        for caseid, subjectid in (("1", "10"), ("2", "10"), ("3", "11")):
            row: dict[str, object] = {
                "caseid": caseid,
                "subjectid": subjectid,
                "condition_id": condition,
                "episode_completed": True,
                "episode_failure_reason": "",
            }
            for metric_index, metric in enumerate(METRICS):
                case_number = int(caseid)
                condition_offset = (0.0, float(case_number), float(case_number**2), float(case_number**3))[condition_index]
                row[metric] = float(case_number + condition_offset + metric_index / 10)
            rows.append(row)
    return rows


class Phase8EFinalResultTests(unittest.TestCase):
    def test_contrast_accumulation_order_is_explicit_and_hash_seed_independent(self) -> None:
        rows = fixture_rows()
        observed = paired_differences(rows, METRICS[0], "interaction")
        by_case = {
            caseid: {
                condition: float(next(
                    row[METRICS[0]] for row in rows
                    if row["caseid"] == caseid and row["condition_id"] == condition
                ))
                for condition in CONDITIONS
            }
            for caseid in ("1", "2", "3")
        }
        expected = [
            sum(
                CONTRAST_WEIGHTS["interaction"][condition] * by_case[caseid][condition]
                for condition in FROZEN_CONTRAST_ACCUMULATION_ORDER
            )
            for caseid in ("1", "2", "3")
        ]
        self.assertEqual(observed.tolist(), expected)

    def test_complete_pairing_subject_aggregation_and_frozen_order(self) -> None:
        aggregate, statistics = build_aggregate(
            fixture_rows(),
            expected_cases=3,
            expected_subjects=2,
            bootstrap_replicates=32,
            permutation_replicates=32,
        )
        self.assertEqual([row["condition_id"] for row in aggregate["conditions"]], list(CONDITIONS))
        self.assertEqual(len(aggregate["contrasts"]), len(METRICS) * len(CONTRASTS))
        self.assertEqual(statistics["subject_aggregation"], "mean_of_case_level_metric_within_subject_before_inference")
        first = aggregate["conditions"][0]["metrics"][0]
        self.assertEqual(first["subject_count"], 2)
        self.assertAlmostEqual(first["mean"], 2.25)

    def test_duplicate_missing_failed_and_nonfinite_rows_are_rejected(self) -> None:
        variants = []
        duplicate = fixture_rows()
        duplicate[-1] = copy.deepcopy(duplicate[0])
        variants.append(duplicate)
        failed = fixture_rows()
        failed[0]["episode_completed"] = False
        failed[0]["episode_failure_reason"] = "error"
        variants.append(failed)
        nonfinite = fixture_rows()
        nonfinite[0][METRICS[0]] = math.nan
        variants.append(nonfinite)
        for rows in variants:
            with self.subTest():
                with self.assertRaises(FinalResultsError):
                    validate_private_rows(rows, expected_cases=3, expected_subjects=2)

    def test_condition_case_set_and_subject_mapping_must_match(self) -> None:
        rows = fixture_rows()
        rows[0]["subjectid"] = "999"
        with self.assertRaises(FinalResultsError):
            validate_private_rows(rows, expected_cases=3, expected_subjects=2)


if __name__ == "__main__":
    unittest.main()

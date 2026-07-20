from __future__ import annotations

import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.protocol_v1_2 import (  # noqa: E402
    EXPECTED_ELIGIBLE_IDS_SHA256,
    MINIMUM_USABLE_WINDOWS,
    PHASE6C_SOURCE_COMMIT,
    SELECTED_CANDIDATE_ID,
    SELECTED_PARAMETERS,
    build_sensitivity_reference,
    parse_bool,
    sorted_caseid_checksum,
)


class ProtocolV12Tests(unittest.TestCase):
    def test_selected_candidate_parameters_are_exactly_human_approved(self) -> None:
        self.assertEqual(SELECTED_CANDIDATE_ID, "sqi_ge_50__bis20s__drug60s")
        self.assertEqual(MINIMUM_USABLE_WINDOWS, 120)
        self.assertEqual(PHASE6C_SOURCE_COMMIT, "b8f010dcc67497f77e26cee53094819f2f5d6cd9")
        self.assertEqual(SELECTED_PARAMETERS["grid_interval_seconds"], 10)
        self.assertEqual(SELECTED_PARAMETERS["history_relative_seconds"], [-50, -40, -30, -20, -10, 0])
        self.assertEqual(SELECTED_PARAMETERS["target_relative_seconds"], 30)
        self.assertEqual(SELECTED_PARAMETERS["bis_admissible_range_inclusive"], [0, 100])
        self.assertTrue(SELECTED_PARAMETERS["bis_0_10_admissible"])
        self.assertEqual(SELECTED_PARAMETERS["sqi_exact_timestamp_threshold"], 50)
        self.assertEqual(SELECTED_PARAMETERS["bis_staleness_cap_seconds"], 20)
        self.assertEqual(SELECTED_PARAMETERS["drug_rate_hold_cap_seconds"], 60)

    def test_final_eligible_checksum_constant_is_pinned(self) -> None:
        self.assertEqual(
            EXPECTED_ELIGIBLE_IDS_SHA256,
            "f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd",
        )
        self.assertEqual(sorted_caseid_checksum([3, 1, 2]), sorted_caseid_checksum([1, 2, 3]))
        with self.assertRaisesRegex(Exception, "duplicate"):
            sorted_caseid_checksum([1, 1])

    def test_sensitivity_references_are_linked_counts_not_frozen_cohorts(self) -> None:
        path = ROOT / "data" / "manifests" / "causal_grid_minimum_window_sensitivity.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            source = list(csv.DictReader(stream))
        rows = build_sensitivity_reference(source)
        self.assertEqual(len(rows), 13)
        self.assertTrue(all(row["robustness_reference_only"] is True for row in rows))
        self.assertTrue(all(row["final_cohort"] is False for row in rows))
        self.assertTrue(all(row["selected"] is False for row in rows))
        self.assertEqual({row["dimension"] for row in rows}, {"sqi_rule", "bis_staleness", "drug_hold", "minimum_windows"})

    def test_boolean_parser_requires_explicit_values(self) -> None:
        self.assertTrue(parse_bool("true"))
        self.assertFalse(parse_bool("false"))
        with self.assertRaises(Exception):
            parse_bool(1)


if __name__ == "__main__":
    unittest.main()

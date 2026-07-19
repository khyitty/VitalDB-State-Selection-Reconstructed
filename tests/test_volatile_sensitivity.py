from __future__ import annotations

import unittest
from dataclasses import replace

from src.vitaldb_state_selection.cohort.volatile_characterization import (
    ALLOWED_TRACK_NAMES,
)
from src.vitaldb_state_selection.cohort.volatile_sensitivity import (
    DEFINITION_ORDER,
    EXPECTED_UNIVERSE_COUNT,
    absent_track_evidence,
    analyze_track_payload,
    build_case_record,
    candidate_protocols,
    definition_summaries,
    duration_histogram,
    proportion_histogram,
)


class VolatileSensitivityTests(unittest.TestCase):
    def test_gap_duplicate_and_duration_rules_preserve_original_row_order(self) -> None:
        payload = (
            "Time,Primus/MAC\n"
            "0,1\n"
            "1,1\n"
            "1,1\n"
            "2,1\n"
            "10,1\n"
            "11,1\n"
        ).encode()
        result = analyze_track_payload(
            payload,
            caseid=1,
            track_name="Primus/MAC",
            anesthesia_start=0,
            anesthesia_end=20,
        )
        self.assertEqual(result.median_positive_timestamp_interval_seconds, 1.0)
        self.assertEqual(result.continuity_gap_boundary_seconds, 3.0)
        self.assertEqual(result.duplicate_timestamp_count, 1)
        self.assertEqual(result.zero_interval_count, 1)
        self.assertEqual(result.long_gap_interval_count, 1)
        self.assertEqual(result.positive_run_count, 3)
        self.assertEqual(result.longest_positive_run_seconds, 1.0)
        self.assertEqual(result.total_positive_continuous_duration_seconds, 3.0)
        self.assertEqual(result.anesthesia_window_positive_count, 6)
        self.assertEqual(result.positive_proportion, 1.0)

    def test_negative_interval_breaks_run_without_sorting_or_deleting_rows(self) -> None:
        payload = (
            "Time,Primus/EXP_SEVO\n"
            "0,1\n"
            "2,1\n"
            "1,1\n"
            "3,1\n"
        ).encode()
        result = analyze_track_payload(
            payload,
            caseid=2,
            track_name="Primus/EXP_SEVO",
            anesthesia_start=0,
            anesthesia_end=3,
        )
        self.assertEqual(result.anesthesia_window_sample_count, 4)
        self.assertEqual(result.negative_interval_count, 1)
        self.assertIn("negative_interval", result.warning_flags)
        self.assertEqual(result.longest_positive_run_seconds, 2.0)

    def test_case_definitions_are_descriptive_and_a_equals_c(self) -> None:
        evidence = [absent_track_evidence(11, name) for name in ALLOWED_TRACK_NAMES]
        agent_index = ALLOWED_TRACK_NAMES.index("Primus/EXP_SEVO")
        evidence[agent_index] = replace(
            evidence[agent_index],
            track_present=True,
            positive_observed_anywhere=True,
            positive_observed_in_anesthesia_window=True,
            anesthesia_window_sample_count=100,
            anesthesia_window_finite_value_count=100,
            anesthesia_window_positive_count=5,
            positive_proportion=0.05,
            longest_positive_run_seconds=30.0,
        )
        record = build_case_record(
            {"caseid": 11, "anesthesia_start": 0, "anesthesia_end": 100},
            evidence,
        )
        definitions = record["definitions"]
        self.assertEqual(tuple(definitions), DEFINITION_ORDER)
        self.assertTrue(definitions["A_any_allowed_positive_once"])
        self.assertTrue(definitions["B_any_agent_specific_positive_once"])
        self.assertEqual(
            definitions["A_any_allowed_positive_once"],
            definitions["C_agent_specific_or_support_positive_once"],
        )
        self.assertTrue(definitions["D_longest_positive_run_ge_10s"])
        self.assertTrue(definitions["E_longest_positive_run_ge_30s"])
        self.assertFalse(definitions["F_longest_positive_run_ge_60s"])
        self.assertTrue(definitions["H_positive_proportion_ge_5pct"])
        self.assertFalse(definitions["H_positive_proportion_ge_10pct"])
        self.assertTrue(definitions["J_agent_specific_only_positive"])
        self.assertFalse(record["analysis_universe_frozen"])

    def test_inverted_anesthesia_window_is_flagged_without_swapping_or_excluding(self) -> None:
        payload = "Time,Primus/MAC\n1,1\n2,1\n".encode()
        result = analyze_track_payload(
            payload,
            caseid=4476,
            track_name="Primus/MAC",
            anesthesia_start=5,
            anesthesia_end=1,
        )
        self.assertTrue(result.positive_observed_anywhere)
        self.assertFalse(result.positive_observed_in_anesthesia_window)
        self.assertEqual(result.anesthesia_window_sample_count, 0)
        self.assertIn("inverted_anesthesia_window", result.warning_flags)

    def test_histograms_account_for_every_value_at_threshold_boundaries(self) -> None:
        durations = [0.0, 0.1, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0]
        proportions = [0.0, 0.0001, 0.001, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 1.0]
        self.assertEqual(sum(row["count"] for row in duration_histogram(durations)), len(durations))
        self.assertEqual(
            sum(row["count"] for row in proportion_histogram(proportions)),
            len(proportions),
        )

    def test_named_candidates_are_exact_unselected_comparisons(self) -> None:
        empty_definitions = {name: False for name in DEFINITION_ORDER}
        records = [
            {"caseid": value, "definitions": empty_definitions}
            for value in range(1, EXPECTED_UNIVERSE_COUNT + 1)
        ]
        summaries = definition_summaries(records)
        candidates = candidate_protocols(summaries)
        self.assertEqual(
            [row["candidate_name"] for row in candidates],
            ["conservative", "duration-based", "corroborated"],
        )
        self.assertTrue(all(row["selected"] is False for row in candidates))
        self.assertTrue(all(row["recommended"] is False for row in candidates))


if __name__ == "__main__":
    unittest.main()

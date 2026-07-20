from __future__ import annotations

import gzip
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.primary_signal_quality import (  # noqa: E402
    TRACK_NAMES,
    build_case_record,
    characterize_track,
    fixed_boundary_samples,
    scenario_results,
)


class PrimarySignalQualityTests(unittest.TestCase):
    def _track(self, name: str, rows: str, start: float = 0, end: float = 100):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track.signal"
            path.write_bytes(gzip.compress(f"Time,{name}\n{rows}".encode()))
            return characterize_track(path, expected_track_name=name,
                                      anesthesia_start=start, anesthesia_end=end,
                                      retain_finite_timestamps=True)

    def test_parser_keeps_original_order_duplicates_and_window_boundaries(self) -> None:
        row = self._track("BIS/BIS", "-1,5\n0,0\n10,50\n10,60\n5,110\n101,20\n")
        self.assertEqual(row["total_row_count"], 6)
        self.assertEqual(row["rows_before_anesthesia_window"], 1)
        self.assertEqual(row["rows_inside_anesthesia_window"], 4)
        self.assertEqual(row["rows_after_anesthesia_window"], 1)
        self.assertEqual(row["raw_duplicate_timestamp_count"], 1)
        self.assertEqual(row["raw_zero_interval_count"], 1)
        self.assertEqual(row["raw_negative_interval_count"], 1)
        self.assertEqual(row["window_negative_interval_count"], 1)
        self.assertFalse(row["processing_timestamp_sorting"])
        self.assertFalse(row["processing_duplicate_deletion"])
        self.assertEqual(row["bis_equal_zero_count"], 1)
        self.assertEqual(row["bis_gt_100_count"], 1)

    def test_drug_runs_compare_phase5d_and_fixed_boundaries_without_bridging(self) -> None:
        row = self._track(
            "Orchestra/PPF20_RATE",
            "0,1\n1,1\n2,1\n40,1\n41,0\n42,0\n42,0\n43,1\n",
        )
        self.assertEqual(row["drug_phase5d_gap_boundary_seconds"], 3.0)
        self.assertEqual(row["drug_positive_phase5d_3x_median_longest_seconds"], 2.0)
        self.assertEqual(row["drug_positive_fixed_30s_longest_seconds"], 2.0)
        self.assertEqual(row["drug_positive_fixed_60s_longest_seconds"], 40.0)
        self.assertEqual(row["window_zero_interval_count"], 1)

    def test_sqi_is_descriptive_and_exact_fraction_only(self) -> None:
        row = self._track("BIS/SQI", "0,-1\n1,20\n2,50\n3,80\n4,101\n")
        self.assertEqual(row["sqi_negative_count"], 1)
        self.assertEqual(row["sqi_gt_100_count"], 1)
        self.assertEqual(row["sqi_ge_50_fraction_of_finite"], 3 / 5)

    def test_case_common_span_is_first_last_overlap_not_continuous_coverage(self) -> None:
        tracks = {}
        for name in TRACK_NAMES:
            track = self._track(name, "0,10\n20,20\n40,30\n")
            if name == "BIS/BIS":
                track["bis_0_100_fraction_of_finite"] = 1.0
                track["bis_10_100_fraction_of_finite"] = 1.0
            if name == "BIS/SQI":
                track["sqi_ge_20_fraction_of_finite"] = 1.0
                track["sqi_ge_50_fraction_of_finite"] = 0.0
                track["sqi_ge_80_fraction_of_finite"] = 0.0
            tracks[name] = track
        case = build_case_record(1, 0, 100, tracks)
        self.assertEqual(case["common_observed_span_duration_seconds"], 40)
        self.assertFalse(case["common_span_is_continuous_coverage"])
        self.assertEqual(case["bis_sqi_exact_timestamp_overlap_count"], 3)

    def test_scenarios_are_unselected_comparisons_with_explicit_failures(self) -> None:
        record = {
            "anesthesia_duration_seconds": 3600, "common_observed_span_duration_seconds": 1800,
            "bis_0_100_fraction_of_finite": 0.95, "bis_10_100_fraction_of_finite": 0.85,
            "sqi_ge_50_fraction_of_finite": 0.60, "propofol_positive_record_count": 3,
            "remifentanil_positive_record_count": 3, "negative_drug_rate_present": False,
        }
        results = scenario_results(record)
        self.assertTrue(results["permissive"]["passes"])
        self.assertTrue(results["moderate"]["passes"])
        self.assertFalse(results["strict"]["passes"])
        self.assertIn("bis_10_100_fraction_lt_90pct", results["strict"]["failure_reasons"])


if __name__ == "__main__":
    unittest.main()

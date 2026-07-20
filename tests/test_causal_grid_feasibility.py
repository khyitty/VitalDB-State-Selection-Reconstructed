from __future__ import annotations

import gzip
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.causal_grid_feasibility import (  # noqa: E402
    ObservationIndex,
    TRACK_NAMES,
    align_bis,
    align_drug,
    all_candidate_ids,
    audit_case,
    build_grid,
    parse_observation_index,
)


class CausalGridFeasibilityTests(unittest.TestCase):
    def make_raw(self, name: str, rows: str, directory: str) -> Path:
        path = Path(directory) / name.replace("/", "_")
        path.write_bytes(gzip.compress(f"Time,{name}\n{rows}".encode()))
        return path

    def index(self, name: str, pairs: list[tuple[float, float]], duplicates: set[float] | None = None) -> ObservationIndex:
        duplicates = duplicates or set()
        return ObservationIndex(
            track_name=name,
            timestamps=tuple(time for time, _ in pairs),
            values=tuple(value for _, value in pairs),
            duplicated_timestamp=tuple(time in duplicates for time, _ in pairs),
            original_row_count=len(pairs), finite_row_count=len(pairs),
            duplicate_timestamp_count=len(duplicates), zero_interval_count=0,
            negative_interval_count=0,
        )

    def test_raw_parser_preserves_last_finite_duplicate_and_interval_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_raw("BIS/BIS", "0,10\n10,20\n10,30\n5,40\n10,nan\n", directory)
            index = parse_observation_index(
                path, expected_track_name="BIS/BIS", anesthesia_start=0, anesthesia_end=20,
            )
        self.assertEqual(index.timestamps, (0.0, 5.0, 10.0))
        self.assertEqual(index.values, (10.0, 40.0, 30.0))
        self.assertTrue(index.duplicated_timestamp[-1])
        self.assertEqual(index.duplicate_timestamp_count, 2)
        self.assertEqual(index.zero_interval_count, 1)
        self.assertEqual(index.negative_interval_count, 1)

    def test_bis_range_sqi_exact_match_staleness_and_no_future_use(self) -> None:
        bis = self.index("BIS/BIS", [(0, 5), (10, 50), (20, 101), (30, 60)])
        sqi = self.index("BIS/SQI", [(10, 50), (30, 19)])
        grid = (0.0, 5.0, 10.0, 25.0, 30.0)
        no_sqi = align_bis(bis, sqi, grid, sqi_rule="sqi_not_required", staleness_cap=10)
        required = align_bis(bis, sqi, grid, sqi_rule="sqi_ge_20", staleness_cap=20)
        self.assertEqual(no_sqi, (1, 1, 1, 0, 1))
        self.assertEqual(required, (0, 0, 1, 1, 1))
        self.assertGreater(required[0], -1)
        self.assertEqual(required[0], 0, "future SQI/BIS observation must not be used")

    def test_drug_alignment_never_assumes_zero_or_falls_back_after_negative(self) -> None:
        index = self.index(
            "Orchestra/PPF20_RATE", [(0, 1), (10, -1), (20, 0), (30, 2)],
            duplicates={30},
        )
        states, counts = align_drug(index, (-1.0, 0.0, 10.0, 20.0, 30.0, 100.0), hold_cap=30)
        self.assertEqual(states, (0, 2, 0, 1, 4, 0))
        self.assertEqual(counts["unavailable_no_prior_finite_observation"], 1)
        self.assertEqual(counts["unavailable_latest_finite_negative"], 1)
        self.assertEqual(counts["unavailable_hold_cap_exceeded"], 1)
        self.assertEqual(counts["duplicate_timestamp_observation_used"], 1)

    def test_grid_and_all_60_candidates_obey_same_case_history_target_boundary(self) -> None:
        grid = build_grid(-3, 107, 0, 103)
        self.assertEqual(grid[0], 7)
        self.assertEqual(grid[-1], 97)
        pairs = [(float(time), 50.0) for time in range(0, 101, 10)]
        indexes = {
            "BIS/BIS": self.index("BIS/BIS", pairs),
            "BIS/SQI": self.index("BIS/SQI", [(time, 100) for time, _ in pairs]),
            "Orchestra/PPF20_RATE": self.index("Orchestra/PPF20_RATE", [(time, 0) for time, _ in pairs]),
            "Orchestra/RFTN20_RATE": self.index("Orchestra/RFTN20_RATE", [(time, 1) for time, _ in pairs]),
        }
        rows, _ = audit_case(
            caseid=1, anesthesia_start=0, anesthesia_end=100,
            common_start=0, common_end=100, indexes=indexes,
        )
        self.assertEqual(len(rows), 60)
        self.assertEqual({row["candidate_id"] for row in rows}, set(all_candidate_ids()))
        self.assertTrue(all(row["total_candidate_grid_points"] == 3 for row in rows))
        self.assertTrue(all(row["total_usable_windows"] == 3 for row in rows))
        self.assertTrue(all(row["future_timestamp_use_count"] == 0 for row in rows))
        self.assertTrue(all(row["cross_case_connection_count"] == 0 for row in rows))
        self.assertTrue(all(row["modeling_array_saved"] is False for row in rows))

    def test_synthetic_case_processing_has_bounded_peak_memory(self) -> None:
        pairs = [(float(time), 50.0) for time in range(0, 601, 10)]
        indexes = {
            "BIS/BIS": self.index("BIS/BIS", pairs),
            "BIS/SQI": self.index("BIS/SQI", [(time, 100) for time, _ in pairs]),
            "Orchestra/PPF20_RATE": self.index("Orchestra/PPF20_RATE", [(time, 0) for time, _ in pairs]),
            "Orchestra/RFTN20_RATE": self.index("Orchestra/RFTN20_RATE", [(time, 1) for time, _ in pairs]),
        }
        tracemalloc.start()
        for caseid in range(50):
            rows, rates = audit_case(
                caseid=caseid, anesthesia_start=0, anesthesia_end=600,
                common_start=0, common_end=600, indexes=indexes,
            )
            self.assertEqual(len(rows), 60)
            del rows, rates
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertLess(peak, 32 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()

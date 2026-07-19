from __future__ import annotations

import csv
import gzip
import io
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.guards import CohortGuardError
from vitaldb_state_selection.cohort.primary_acquisition import (
    PHASE5D_PRIMARY_DEFINITION,
    PRIMARY_TRACK_NAMES,
    build_pre_quality_manifest,
    build_tasks,
    fixed_seed_preflight_caseids,
    parse_primary_track,
)


class PrimaryAcquisitionTests(unittest.TestCase):
    def _universe(self):
        p5c = [{"caseid": caseid} for caseid in range(1, 3220)]
        p5d = []
        for caseid in range(1, 3220):
            p5d.append({
                "caseid": caseid,
                "anesthesia_window_valid": caseid != 4476,
                "definitions": {PHASE5D_PRIMARY_DEFINITION: caseid % 10 == 0},
            })
        # Replace one ID so the synthetic universe includes the required preserved invalid case.
        p5c[-1]["caseid"] = 4476
        p5d[-1] = {
            "caseid": 4476, "anesthesia_window_valid": False,
            "definitions": {PHASE5D_PRIMARY_DEFINITION: False},
        }
        return p5c, p5d

    def test_pre_quality_manifest_preserves_multiple_reasons(self) -> None:
        p5c, p5d = self._universe()
        legacy = set(range(1, 99))
        rows = build_pre_quality_manifest(p5c, p5d, legacy)
        self.assertEqual(len(rows), 3219)
        self.assertEqual(len({row["caseid"] for row in rows}), 3219)
        case10 = next(row for row in rows if row["caseid"] == 10)
        self.assertEqual(
            case10["exclusion_reasons"],
            ["volatile_positive_run_ge_10s", "legacy_98_overlap"],
        )
        invalid = next(row for row in rows if row["caseid"] == 4476)
        self.assertFalse(invalid["included_for_primary_signal_acquisition"])
        self.assertIn("ineligible_invalid_anesthesia_window", invalid["exclusion_reasons"])
        self.assertTrue(all(row["final_eligibility"] == "pending_human_review" for row in rows))

    def test_fixed_seed_sample_is_25_unique_and_not_first_25(self) -> None:
        universe = list(range(1, 3000))
        chosen = fixed_seed_preflight_caseids(universe)
        self.assertEqual(len(chosen), 25)
        self.assertEqual(len(set(chosen)), 25)
        self.assertNotEqual(chosen, universe[:25])
        self.assertEqual(chosen, fixed_seed_preflight_caseids(universe))

    def test_task_matrix_has_every_case_and_exact_track(self) -> None:
        included = [3, 7]
        track_rows = [
            {"caseid": caseid, "tname": name, "tid": f"{caseid}-{index}"}
            for caseid in included for index, name in enumerate(PRIMARY_TRACK_NAMES)
        ]
        tasks = build_tasks(included, track_rows)
        self.assertEqual(len(tasks), 8)
        self.assertEqual({task.track_name for task in tasks}, set(PRIMARY_TRACK_NAMES))

    def test_parser_is_structural_only_and_preserves_duplicate_rows(self) -> None:
        payload = gzip.compress(b"Time,BIS/BIS\n0,40\n1,41\n1,42\n2,\n")
        parsed = parse_primary_track(payload, expected_track_name="BIS/BIS")
        self.assertEqual(parsed["sample_count"], 4)
        self.assertEqual(parsed["non_missing_sample_count"], 3)
        self.assertEqual(parsed["duplicate_timestamp_count"], 1)
        self.assertFalse(parsed["resampling_performed"])
        self.assertFalse(parsed["interpolation_performed"])

    def test_real_phase5d_inputs_build_exact_protocol_universe(self) -> None:
        with (ROOT / "data/manifests/volatile_signal_case_manifest.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            p5c = list(csv.DictReader(stream))
        p5d = json.loads(
            (ROOT / "data/manifests/volatile_exposure_rule_sensitivity_summary.json").read_text(
                encoding="utf-8"
            )
        )["case_records"]
        rows = build_pre_quality_manifest(p5c, p5d, set(range(1, 99)))
        self.assertEqual(len(rows), 3219)
        self.assertEqual(sum(row["volatile_positive_run_ge_10s"] for row in rows), 674)


if __name__ == "__main__":
    unittest.main()

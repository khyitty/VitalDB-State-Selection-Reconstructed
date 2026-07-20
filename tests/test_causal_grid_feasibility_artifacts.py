from __future__ import annotations

import csv
import gzip
import hashlib
import json
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
TRACKS = {"BIS/BIS", "BIS/SQI", "Orchestra/PPF20_RATE", "Orchestra/RFTN20_RATE"}


def read_csv(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class CausalGridFeasibilityArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case_candidates = []
        with gzip.open(
            MANIFESTS / "causal_grid_feasibility_case_candidate_manifest.csv.gz",
            mode="rt", encoding="utf-8", newline="",
        ) as stream:
            cls.case_candidates = list(csv.DictReader(stream))
        cls.candidates = read_csv("causal_grid_candidate_summary.csv")
        cls.minimum = read_csv("causal_grid_minimum_window_sensitivity.csv")
        cls.disagreement = read_csv("causal_grid_candidate_disagreement.csv")
        cls.scenario = read_csv("causal_grid_phase6b_scenario_disagreement.csv")
        cls.rates = read_csv("causal_grid_drug_alignment_summary.csv")
        cls.demographics = read_csv("causal_grid_demographics_pk_input_feasibility.csv")
        cls.boundaries = read_csv("causal_grid_boundary_review.csv")
        cls.summary = json.loads((MANIFESTS / "causal_grid_feasibility_summary.json").read_text(encoding="utf-8"))
        cls.source = json.loads((MANIFESTS / "causal_grid_feasibility_source_snapshot.json").read_text(encoding="utf-8"))

    def test_exact_2470_by_60_case_candidate_accounting(self) -> None:
        self.assertEqual(len(self.case_candidates), 148200)
        caseids = {int(row["caseid"]) for row in self.case_candidates}
        candidate_ids = {row["candidate_id"] for row in self.case_candidates}
        self.assertEqual(len(caseids), 2470)
        self.assertEqual(len(candidate_ids), 60)
        keys = {(int(row["caseid"]), row["candidate_id"]) for row in self.case_candidates}
        self.assertEqual(len(keys), 148200)
        self.assertEqual(Counter(row["candidate_id"] for row in self.case_candidates), {name: 2470 for name in candidate_ids})
        self.assertEqual({row["sqi_rule"] for row in self.case_candidates}, {"sqi_not_required", "sqi_ge_20", "sqi_ge_50", "sqi_ge_80"})
        self.assertEqual({int(row["bis_staleness_cap_seconds"]) for row in self.case_candidates}, {10, 20, 30})
        self.assertEqual({int(row["drug_hold_cap_seconds"]) for row in self.case_candidates}, {30, 60, 120, 300, 600})

    def test_causal_case_and_non_modeling_invariants_hold_for_every_row(self) -> None:
        for row in self.case_candidates:
            self.assertEqual(row["grid_anchor"], "anesthesia_start")
            self.assertEqual(row["grid_interval_seconds"], "10")
            self.assertEqual(row["future_timestamp_use_count"], "0")
            self.assertEqual(row["cross_case_connection_count"], "0")
            self.assertEqual(row["modeling_array_saved"], "false")
            self.assertEqual(row["selected"], "false")
            total = int(row["total_candidate_grid_points"])
            overlaps = json.loads(row["overlapping_failure_reason_counts"])
            self.assertEqual(sum(overlaps.values()), total)
            self.assertLessEqual(int(row["total_usable_windows"]), int(row["usable_history_endpoints"]))
            self.assertLessEqual(int(row["total_usable_windows"]), int(row["usable_target_points"]))
        self.assertFalse(self.summary["bis_numerical_range"]["bis_0_10_automatically_invalid"])
        self.assertNotIn("BIS/SQI", self.summary["prediction_feature_universe_inspected"])
        self.assertEqual(self.summary["sqi_role"], "qc_only_not_prediction_feature_not_ppo_state")

    def test_candidate_aggregates_recompute_from_case_rows(self) -> None:
        by_candidate: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in self.case_candidates:
            by_candidate[row["candidate_id"]].append(row)
        self.assertEqual(len(self.candidates), 60)
        for aggregate in self.candidates:
            rows = by_candidate[aggregate["candidate_id"]]
            self.assertEqual(len(rows), 2470)
            self.assertEqual(int(aggregate["total_candidate_grid_points"]), sum(int(row["total_candidate_grid_points"]) for row in rows))
            self.assertEqual(int(aggregate["usable_history_endpoints"]), sum(int(row["usable_history_endpoints"]) for row in rows))
            self.assertEqual(int(aggregate["usable_target_points"]), sum(int(row["usable_target_points"]) for row in rows))
            self.assertEqual(int(aggregate["total_usable_windows"]), sum(int(row["total_usable_windows"]) for row in rows))
            self.assertEqual(int(aggregate["usable_case_count"]), sum(int(row["total_usable_windows"]) > 0 for row in rows))
            self.assertEqual(int(aggregate["zero_window_cases"]), sum(int(row["total_usable_windows"]) == 0 for row in rows))
            self.assertEqual(aggregate["selected"], "false")
            self.assertEqual(aggregate["recommended"], "false")

    def test_nested_alignment_candidates_have_expected_outcome_blind_monotonicity(self) -> None:
        by_key = {
            (
                row["sqi_rule"], int(row["bis_staleness_cap_seconds"]),
                int(row["drug_hold_cap_seconds"]), int(row["caseid"]),
            ): int(row["total_usable_windows"])
            for row in self.case_candidates
        }
        caseids = {int(row["caseid"]) for row in self.case_candidates}
        for caseid in caseids:
            for sqi in ("sqi_not_required", "sqi_ge_20", "sqi_ge_50", "sqi_ge_80"):
                for drug in (30, 60, 120, 300, 600):
                    self.assertLessEqual(by_key[(sqi, 10, drug, caseid)], by_key[(sqi, 20, drug, caseid)])
                    self.assertLessEqual(by_key[(sqi, 20, drug, caseid)], by_key[(sqi, 30, drug, caseid)])
                for bis in (10, 20, 30):
                    values = [by_key[(sqi, bis, drug, caseid)] for drug in (30, 60, 120, 300, 600)]
                    self.assertEqual(values, sorted(values))
            for bis in (10, 20, 30):
                for drug in (30, 60, 120, 300, 600):
                    values = [by_key[(sqi, bis, drug, caseid)] for sqi in ("sqi_not_required", "sqi_ge_20", "sqi_ge_50", "sqi_ge_80")]
                    self.assertEqual(values, sorted(values, reverse=True))

    def test_minimum_window_sensitivity_is_complete_balanced_and_unselected(self) -> None:
        self.assertEqual(len(self.minimum), 300)
        self.assertEqual({int(row["minimum_usable_windows"]) for row in self.minimum}, {30, 60, 120, 300, 600})
        self.assertEqual(len({(row["candidate_id"], row["minimum_usable_windows"]) for row in self.minimum}), 300)
        for row in self.minimum:
            self.assertEqual(int(row["pass_case_count"]) + int(row["fail_case_count"]), 2470)
            self.assertEqual(row["is_continuous_duration_claim"], "false")
            self.assertEqual(row["selected"], "false")
        self.assertIsNone(self.summary["minimum_window_threshold_selected"])

    def test_pairwise_candidate_disagreement_matrix_is_symmetric(self) -> None:
        self.assertEqual(len(self.disagreement), 3600)
        matrix = {
            (row["candidate_left"], row["candidate_right"]): int(row["disagreement_case_count"])
            for row in self.disagreement
        }
        self.assertEqual(len(matrix), 3600)
        candidates = {row["candidate_id"] for row in self.candidates}
        for left in candidates:
            self.assertEqual(matrix[(left, left)], 0)
            for right in candidates:
                self.assertEqual(matrix[(left, right)], matrix[(right, left)])

    def test_phase6b_scenario_disagreement_has_all_900_comparisons(self) -> None:
        self.assertEqual(len(self.scenario), 900)
        self.assertEqual({row["phase6b_scenario"] for row in self.scenario}, {"permissive", "moderate", "strict"})
        self.assertEqual(len({(row["phase6b_scenario"], row["candidate_id"], row["minimum_usable_windows"]) for row in self.scenario}), 900)
        for row in self.scenario:
            total = (
                int(row["scenario_pass_but_below_minimum"])
                + int(row["scenario_fail_but_meets_minimum"])
                + int(row["both_pass"])
                + int(row["both_fail"])
            )
            self.assertEqual(total, 2470)
            self.assertLessEqual(int(row["scenario_pass_but_zero_usable_window"]), int(row["scenario_pass_but_below_minimum"]))
            self.assertIn("bis_10_100_fraction_reason_but_meets_minimum", row)
            self.assertEqual(row["selected"], "false")

    def test_drug_alignment_and_demographics_are_descriptive_only(self) -> None:
        self.assertEqual(len(self.rates), 10)
        for row in self.rates:
            self.assertEqual(int(row["usable_grid_points"]) + int(row["unavailable_grid_points"]), int(row["total_grid_points"]))
            self.assertEqual(int(row["positive_grid_points"]) + int(row["zero_grid_points"]), int(row["usable_grid_points"]))
            self.assertEqual(row["selected"], "false")
        self.assertEqual(len(self.demographics), 2470)
        self.assertEqual(len({row["caseid"] for row in self.demographics}), 2470)
        for row in self.demographics:
            self.assertEqual(row["pk_parameters_computed"], "false")
            self.assertEqual(row["lean_body_mass_computed"], "false")
            self.assertEqual(row["automatic_exclusion"], "false")
        self.assertEqual(self.summary["demographics_pk_input_feasibility"]["case_count"], 2470)

    def test_boundary_samples_are_fixed_seed_bounded_and_non_decisional(self) -> None:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in self.boundaries:
            grouped[row["category"]].append(row)
            self.assertEqual(row["seed"], "20260720")
            self.assertEqual(row["automatic_inclusion_or_exclusion"], "false")
        self.assertTrue(all(len(rows) <= 5 for rows in grouped.values()))
        for category, count in self.summary["boundary_category_counts"].items():
            if count == 0:
                self.assertNotIn(category, grouped)
            else:
                self.assertEqual(int(grouped[category][0]["category_case_count"]), count)

    def test_source_checksums_raw_tree_memory_and_legacy_state_are_verified(self) -> None:
        self.assertEqual(self.source["raw_checksum_before"], self.source["raw_checksum_after"])
        self.assertEqual(self.source["raw_checksum_before"]["verified_file_count"], 9880)
        self.assertEqual(self.source["raw_checksum_before"]["verified_total_bytes"], 2658264378)
        self.assertEqual(self.source["raw_tree_before"], self.source["raw_tree_after"])
        self.assertEqual(self.source["raw_tree_before"]["file_count"], 19761)
        self.assertEqual(self.source["raw_tree_before"]["total_bytes"], 2673762558)
        self.assertEqual(self.source["raw_tree_before"]["partial_file_count"], 0)
        self.assertTrue(self.source["legacy_state_unchanged"])
        self.assertFalse(self.source["legacy_artifact_accessed"])
        self.assertEqual(self.source["legacy_state_before"], self.source["legacy_state_after"])
        self.assertLess(self.source["peak_rss_bytes"], self.source["memory_abort_guard_bytes"])
        self.assertEqual(set(self.source["allowed_exact_tracks"]), TRACKS)

    def test_no_network_raw_git_or_downstream_execution_and_no_partial_outputs(self) -> None:
        self.assertEqual(self.source["api_request_count"], 0)
        self.assertEqual(self.source["new_raw_file_count"], 0)
        self.assertFalse(self.source["sqi_in_prediction_feature_universe"])
        self.assertFalse(self.source["bis_0_10_automatically_invalid"])
        flags = self.summary["execution_flags"]
        self.assertEqual(flags["api_requests"], 0)
        self.assertEqual(flags["new_raw_files"], 0)
        self.assertTrue(all(value is False for key, value in flags.items() if key not in {"api_requests", "new_raw_files"}))
        code = (ROOT / "scripts" / "run_causal_grid_feasibility_audit.py").read_text(encoding="utf-8")
        self.assertNotIn("import requests", code)
        self.assertNotIn("VitalDBOpenAPI", code)
        tracked = subprocess.check_output(["git", "ls-files", "data/raw"], cwd=ROOT, text=True).splitlines()
        self.assertEqual(tracked, [])
        self.assertEqual(list((ROOT / "data" / "raw" / "phase6a_primary_signals").rglob("*.part")), [])
        self.assertEqual(list(MANIFESTS.glob(".causal_grid*.tmp")), [])

    def test_report_and_artifact_checksum_inventory_match(self) -> None:
        report = (ROOT / "docs" / "causal_grid_window_feasibility_report.md").read_text(encoding="utf-8")
        for phrase in (
            "## Scope and accounting", "## Fixed causal structure",
            "including 0-10", "descriptive only", "No SQI rule",
            "cohort freeze", "No API request",
        ):
            self.assertIn(phrase, report)
        inventory = json.loads((MANIFESTS / "causal_grid_feasibility_artifact_checksums.json").read_text(encoding="utf-8"))
        self.assertEqual(len(inventory), 11)
        for relative, expected in inventory.items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)


if __name__ == "__main__":
    unittest.main()

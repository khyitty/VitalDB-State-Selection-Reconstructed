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
RAW_ROOT = ROOT / "data" / "raw" / "phase6a_primary_signals"
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


class PrimarySignalQualityArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = read_csv("primary_signal_quality_case_manifest.csv")
        cls.tracks = read_csv("primary_signal_quality_track_manifest.csv")
        cls.marginal = read_csv("primary_signal_quality_marginal_sensitivity.csv")
        cls.scenarios = read_csv("primary_signal_quality_scenario_sensitivity.csv")
        cls.disagreement = read_csv("primary_signal_quality_scenario_disagreement.csv")
        cls.boundaries = read_csv("primary_signal_quality_boundary_review.csv")
        cls.summary = json.loads((MANIFESTS / "primary_signal_quality_summary.json").read_text(encoding="utf-8"))
        cls.source = json.loads((MANIFESTS / "primary_signal_quality_source_snapshot.json").read_text(encoding="utf-8"))

    def test_case_and_track_manifests_have_complete_exact_accounting(self) -> None:
        self.assertEqual(len(self.cases), 2470)
        self.assertEqual(len({int(row["caseid"]) for row in self.cases}), 2470)
        self.assertEqual(len(self.tracks), 9880)
        keys = {(int(row["caseid"]), row["exact_track_name"]) for row in self.tracks}
        self.assertEqual(len(keys), 9880)
        self.assertEqual({row["exact_track_name"] for row in self.tracks}, TRACKS)
        self.assertEqual(Counter(row["parsing_status"] for row in self.tracks), {"complete": 9880})
        self.assertTrue(all(row["checksum_status"] == "verified_before_and_after_analysis" for row in self.tracks))
        self.assertTrue(all(row["final_eligibility"] == "pending_human_review" for row in self.cases))
        self.assertTrue(all(row["cohort_frozen"] == "false" for row in self.cases))
        self.assertTrue(all(row["split_assigned"] == "false" for row in self.cases))

    def test_original_rows_are_not_transformed_and_full_window_scopes_are_separate(self) -> None:
        for row in self.tracks:
            for field in (
                "processing_resampling", "processing_interpolation", "processing_smoothing",
                "processing_clipping", "processing_forward_fill", "processing_backward_fill",
                "processing_timestamp_sorting", "processing_duplicate_deletion",
            ):
                self.assertEqual(row[field], "false")
            self.assertEqual(
                int(row["total_row_count"]),
                int(row["rows_before_anesthesia_window"])
                + int(row["rows_inside_anesthesia_window"])
                + int(row["rows_after_anesthesia_window"]),
            )
            self.assertEqual(
                int(row["raw_strictly_positive_interval_count"])
                + int(row["raw_zero_interval_count"])
                + int(row["raw_negative_interval_count"]),
                max(0, int(row["total_row_count"]) - 1),
            )

    def test_bis_sqi_is_exact_timestamp_qc_only_and_common_span_is_not_coverage(self) -> None:
        self.assertTrue(all(row["common_span_is_continuous_coverage"] == "false" for row in self.cases))
        self.assertEqual(self.source["bis_sqi_role"], "qc_only_not_prediction_feature_not_ppo_state")
        config = (ROOT / "configs" / "track_aliases.yaml").read_text(encoding="utf-8")
        self.assertIn("prediction_feature_allowed: false", config)
        self.assertIn("ppo_state_allowed: false", config)
        self.assertNotIn("nearest", " ".join(self.cases[0].keys()).lower())

    def test_marginal_sensitivity_is_complete_independent_and_unselected(self) -> None:
        self.assertEqual(len(self.marginal), 60)
        expected_categories = {
            "anesthesia_window_duration", "common_observed_span_duration",
            "common_observed_span_ratio", "bis_descriptive_range_fraction",
            "sqi_descriptive_fraction", "timestamp_gap", "drug_evidence",
        }
        self.assertEqual({row["category"] for row in self.marginal}, expected_categories)
        for row in self.marginal:
            self.assertEqual(int(row["pass_count"]) + int(row["fail_count"]), 2470)
            self.assertEqual(int(row["total_case_count"]), 2470)
            self.assertEqual(row["selected_for_protocol"], "false")
        self.assertIsNone(self.summary["selected_quality_threshold"])

    def test_scenarios_recompute_balance_and_pairwise_disagreement(self) -> None:
        counts = {row["scenario"]: int(row["pass_count"]) for row in self.scenarios}
        self.assertEqual(counts, {"permissive": 2464, "moderate": 2333, "strict": 1723})
        for row in self.scenarios:
            self.assertEqual(int(row["pass_count"]) + int(row["fail_count"]), 2470)
            self.assertEqual(row["selected"], "false")
            self.assertEqual(row["recommended"], "false")
            self.assertTrue(json.loads(row["individual_failure_reason_counts"]))
        matrix = {(row["scenario_left"], row["scenario_right"]): int(row["disagreement_count"]) for row in self.disagreement}
        self.assertEqual(len(matrix), 9)
        for left in counts:
            self.assertEqual(matrix[(left, left)], 0)
            for right in counts:
                self.assertEqual(matrix[(left, right)], matrix[(right, left)])
        self.assertIsNone(self.summary["selected_scenario"])

    def test_boundary_samples_are_fixed_seed_bounded_and_never_decisions(self) -> None:
        grouped: dict[str, list[dict[str, str]]] = {}
        for row in self.boundaries:
            grouped.setdefault(row["category"], []).append(row)
            self.assertEqual(row["seed"], "20260720")
            self.assertEqual(row["automatic_inclusion_or_exclusion"], "false")
        self.assertTrue(grouped)
        self.assertTrue(all(len(rows) <= 5 for rows in grouped.values()))
        for category, rows in grouped.items():
            self.assertEqual(len({row["caseid"] for row in rows}), len(rows))
            self.assertEqual(
                self.summary["boundary_review_category_counts"][category],
                int(rows[0]["category_case_count"]),
            )

    def test_phase6a_raw_checksums_tree_and_legacy_state_are_unchanged(self) -> None:
        before = self.source["raw_checksum_before"]
        after = self.source["raw_checksum_after"]
        self.assertEqual(before, after)
        self.assertEqual(before["verified_file_count"], 9880)
        self.assertEqual(before["verified_total_bytes"], 2658264378)
        self.assertEqual(self.source["raw_tree_before"], self.source["raw_tree_after"])
        self.assertEqual(self.source["raw_tree_before"]["file_count"], 19761)
        self.assertEqual(self.source["raw_tree_before"]["total_bytes"], 2673762558)
        self.assertEqual(self.source["raw_tree_before"]["partial_file_count"], 0)
        self.assertEqual(self.source["new_raw_file_count"], 0)
        self.assertTrue(self.source["legacy_state_unchanged"])
        self.assertFalse(self.source["legacy_artifact_accessed"])
        self.assertEqual(self.source["legacy_state_before"], self.source["legacy_state_after"])

    def test_every_source_raw_checksum_still_matches_phase6a_manifest(self) -> None:
        phase6a = read_csv("primary_signal_download_manifest.csv")
        self.assertEqual(len(phase6a), 9880)
        for row in phase6a:
            path = RAW_ROOT / row["raw_relative_path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, int(row["raw_byte_count"]))
            self.assertEqual(sha256(path), row["raw_sha256"])

    def test_source_scope_has_no_network_or_downstream_execution(self) -> None:
        self.assertEqual(self.source["api_request_count"], 0)
        self.assertEqual(set(self.source["allowed_exact_tracks"]), TRACKS)
        self.assertFalse(self.source["anesthesia_window_lineage"]["volatile_raw_signal_read"])
        code = (ROOT / "scripts" / "run_primary_signal_quality_characterization.py").read_text(encoding="utf-8")
        self.assertNotIn("import requests", code)
        self.assertNotIn("VitalDBOpenAPI", code)
        flags = self.summary["execution_flags"]
        self.assertEqual(flags["api_requests"], 0)
        self.assertEqual(flags["new_raw_files"], 0)
        self.assertTrue(all(value is False for key, value in flags.items() if key not in {"api_requests", "new_raw_files"}))
        tracked = subprocess.check_output(["git", "ls-files", "data/raw"], cwd=ROOT, text=True).splitlines()
        self.assertEqual(tracked, [])
        self.assertEqual(list(RAW_ROOT.rglob("*.part")), [])

    def test_report_and_all_artifact_checksums_match(self) -> None:
        report = (ROOT / "docs" / "primary_signal_quality_characterization_report.md").read_text(encoding="utf-8")
        for phrase in (
            "## Facts", "## Interpretation boundary", "not continuous coverage",
            "No quality cutoff", "Every row below is an independent comparison",
            "No API request", "Protocol v1.2 human decision",
        ):
            self.assertIn(phrase, report)
        inventory = json.loads((MANIFESTS / "primary_signal_quality_artifact_checksums.json").read_text(encoding="utf-8"))
        self.assertEqual(len(inventory), 9)
        for relative, expected in inventory.items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)


if __name__ == "__main__":
    unittest.main()

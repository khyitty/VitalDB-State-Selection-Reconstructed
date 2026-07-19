from __future__ import annotations

import ast
import csv
import hashlib
import json
import subprocess
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.volatile_characterization import (  # noqa: E402
    ALLOWED_TRACK_NAMES,
    sha256_path,
)
from vitaldb_state_selection.cohort.volatile_sensitivity import (  # noqa: E402
    DEFINITION_ORDER,
    EXPECTED_UNIVERSE_COUNT,
    metric_distribution,
)


MANIFEST_DIR = ROOT / "data" / "manifests"
RAW_ROOT = ROOT / "data" / "raw" / "phase5c_volatile_signals"
SUMMARY_PATH = MANIFEST_DIR / "volatile_exposure_rule_sensitivity_summary.json"
REPORT_PATH = ROOT / "docs" / "volatile_exposure_rule_sensitivity_report.md"
TRACK_PATH = MANIFEST_DIR / "volatile_signal_track_manifest.csv"


class VolatileSensitivityArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        cls.records = cls.summary["case_records"]

    def test_complete_unfrozen_case_accounting_and_pending_decisions(self) -> None:
        caseids = [int(row["caseid"]) for row in self.records]
        self.assertEqual(len(caseids), EXPECTED_UNIVERSE_COUNT)
        self.assertEqual(len(caseids), len(set(caseids)))
        self.assertEqual(self.summary["analysis_universe"]["duplicate_case_count"], 0)
        self.assertEqual(self.summary["analysis_universe"]["missing_case_count"], 0)
        self.assertFalse(self.summary["analysis_universe"]["cohort_frozen"])
        self.assertIsNone(self.summary["selected_exposure_definition"])
        self.assertIsNone(self.summary["selected_protocol_candidate"])
        self.assertTrue(all(row["analysis_universe_frozen"] is False for row in self.records))
        self.assertTrue(
            all(row["volatile_exposure_decision"] == "pending_human_review" for row in self.records)
        )
        self.assertTrue(all(row["tiva_decision"] == "pending_human_review" for row in self.records))
        self.assertTrue(all(row["legacy_overlap"] == "pending_not_evaluated" for row in self.records))
        self.assertEqual(
            sum(row["anesthesia_window_valid"] is False for row in self.records),
            1,
        )

    def test_definition_counts_recompute_and_thresholds_are_not_selected(self) -> None:
        by_name = {row["definition"]: row for row in self.summary["definition_summaries"]}
        self.assertEqual(tuple(by_name), DEFINITION_ORDER)
        for name in DEFINITION_ORDER:
            excluded = sum(bool(row["definitions"][name]) for row in self.records)
            self.assertEqual(by_name[name]["excluded_case_count"], excluded)
            self.assertEqual(by_name[name]["retained_case_count"], EXPECTED_UNIVERSE_COUNT - excluded)
            self.assertFalse(by_name[name]["selected"])
        self.assertTrue(
            all(
                row["definitions"]["A_any_allowed_positive_once"]
                == row["definitions"]["C_agent_specific_or_support_positive_once"]
                for row in self.records
            )
        )
        duration_counts = [
            by_name[name]["excluded_case_count"]
            for name in (
                "D_longest_positive_run_ge_10s",
                "E_longest_positive_run_ge_30s",
                "F_longest_positive_run_ge_60s",
                "G_longest_positive_run_ge_300s",
            )
        ]
        proportion_counts = [
            by_name[name]["excluded_case_count"]
            for name in (
                "H_positive_proportion_ge_0_1pct",
                "H_positive_proportion_ge_1pct",
                "H_positive_proportion_ge_5pct",
                "H_positive_proportion_ge_10pct",
            )
        ]
        self.assertEqual(duration_counts, sorted(duration_counts, reverse=True))
        self.assertEqual(proportion_counts, sorted(proportion_counts, reverse=True))

    def test_pairwise_disagreement_matrix_recomputes_is_symmetric_and_has_zero_diagonal(self) -> None:
        matrix = self.summary["pairwise_disagreement_matrix"]
        self.assertEqual(tuple(matrix["definition_order"]), DEFINITION_ORDER)
        for left in DEFINITION_ORDER:
            self.assertEqual(matrix["counts"][left][left], 0)
            for right in DEFINITION_ORDER:
                expected = sum(
                    bool(row["definitions"][left]) != bool(row["definitions"][right])
                    for row in self.records
                )
                self.assertEqual(matrix["counts"][left][right], expected)
                self.assertEqual(matrix["counts"][left][right], matrix["counts"][right][left])

    def test_distributions_histograms_and_boundary_categories_recompute(self) -> None:
        durations = [float(row["max_allowed_longest_positive_run_seconds"]) for row in self.records]
        proportions = [float(row["max_allowed_track_positive_proportion"]) for row in self.records]
        self.assertEqual(
            self.summary["duration_distribution_seconds"]["summary"],
            metric_distribution(durations),
        )
        self.assertEqual(
            self.summary["positive_proportion_distribution"]["summary"],
            metric_distribution(proportions),
        )
        self.assertEqual(
            sum(row["count"] for row in self.summary["duration_distribution_seconds"]["histogram_bins"]),
            EXPECTED_UNIVERSE_COUNT,
        )
        self.assertEqual(
            sum(row["count"] for row in self.summary["positive_proportion_distribution"]["histogram_bins"]),
            EXPECTED_UNIVERSE_COUNT,
        )
        self.assertEqual(self.summary["boundary_category_counts"]["invalid_anesthesia_window"], 1)
        self.assertEqual(
            self.summary["boundary_category_counts"]["positive_only_outside_anesthesia_window"],
            sum(
                row["any_allowed_positive_anywhere"]
                and not row["any_allowed_positive_in_anesthesia_window"]
                for row in self.records
            ),
        )
        for category, sample in self.summary["manual_review_boundary_samples"].items():
            self.assertLessEqual(len(sample), 5, category)
            self.assertEqual(sample, sorted(set(sample)), category)
        boundaries = self.summary["continuity_boundary_distributions_by_track"]
        self.assertEqual(set(boundaries), set(ALLOWED_TRACK_NAMES))
        for name, item in boundaries.items():
            self.assertEqual(
                item["boundary_available_count"] + item["boundary_unavailable_count"],
                item["present_track_count"],
                name,
            )
            cadence = item["median_timestamp_interval_seconds_distribution"]
            boundary = item["continuity_gap_boundary_seconds_distribution"]
            self.assertEqual(cadence["count"], boundary["count"], name)
            self.assertAlmostEqual(boundary["q50"], 3.0 * cadence["q50"], places=9)

    def test_agent_gas2_mac_combinations_and_candidates_recompute(self) -> None:
        groups: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in self.records:
            key = "|".join(
                (
                    f"agent_specific_positive={str(bool(row['agent_specific_positive'])).lower()}",
                    f"gas2_positive={str(bool(row['gas2_positive'])).lower()}",
                    f"mac_positive={str(bool(row['mac_positive'])).lower()}",
                )
            )
            groups[key].append(row)
        reported = {
            row["combination"]: row
            for row in self.summary["agent_specific_gas2_mac_combination_results"]
        }
        self.assertEqual(set(reported), set(groups))
        self.assertEqual(sum(row["case_count"] for row in reported.values()), EXPECTED_UNIVERSE_COUNT)
        for combination, members in groups.items():
            self.assertEqual(reported[combination]["case_count"], len(members))
            for name in DEFINITION_ORDER:
                self.assertEqual(
                    reported[combination]["definition_excluded_counts"][name],
                    sum(bool(row["definitions"][name]) for row in members),
                )
        candidates = self.summary["protocol_candidates"]
        self.assertEqual(
            [row["candidate_name"] for row in candidates],
            ["conservative", "duration-based", "corroborated"],
        )
        self.assertTrue(all(not row["selected"] and not row["recommended"] for row in candidates))

    def test_phase5c_source_and_all_raw_signal_checksums_match(self) -> None:
        integrity = self.summary["source_integrity"]
        self.assertTrue(integrity["phase5c_artifact_checksums_verified"])
        for relative, expected in integrity["phase5c_artifact_checksums"].items():
            self.assertEqual(sha256_path(ROOT / relative), expected, relative)
        with TRACK_PATH.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        complete = [row for row in rows if row["download_status"] == "complete"]
        self.assertEqual(len(complete), 9059)
        fingerprint = hashlib.sha256()
        for row in complete:
            relative = row["raw_relative_path"]
            path = RAW_ROOT / relative
            self.assertTrue(path.is_file(), relative)
            checksum = sha256_path(path)
            self.assertEqual(checksum, row["raw_sha256"], relative)
            self.assertEqual(path.stat().st_size, int(row["raw_byte_count"]), relative)
            fingerprint.update(
                f"{relative}\0{checksum}\0{path.stat().st_size}\n".encode("utf-8")
            )
        self.assertEqual(
            fingerprint.hexdigest(), integrity["raw_signal_manifest_fingerprint_sha256"]
        )
        self.assertEqual(integrity["raw_signal_checksum_verified_count"], 9059)
        self.assertTrue(integrity["raw_tree_unchanged"])
        self.assertEqual(integrity["new_raw_file_count"], 0)
        self.assertEqual(
            integrity["raw_tree_content_fingerprint_before"],
            integrity["raw_tree_content_fingerprint_after"],
        )

    def test_no_network_capability_raw_git_tracking_or_downstream_execution(self) -> None:
        script_path = ROOT / "scripts" / "run_volatile_sensitivity_audit.py"
        tree = ast.parse(script_path.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue({"requests", "urllib", "httpx"}.isdisjoint(imported))
        script_text = script_path.read_text(encoding="utf-8")
        for forbidden in ("VitalDBOpenAPI", "fetch_tracks", "fetch_cases", "fetch_track"):
            self.assertNotIn(forbidden, script_text)
        result = subprocess.run(
            ["git", "ls-files", "--", "data/raw"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "")
        self.assertTrue(all(value is False for value in self.summary["execution_flags"].values()))
        self.assertEqual(
            {row["track_name"] for row in self.summary["allowed_exact_tracks"]},
            set(ALLOWED_TRACK_NAMES),
        )
        self.assertTrue(
            all(row["approval_status"] == "pending_human_review" for row in self.summary["allowed_exact_tracks"])
        )

    def test_report_records_method_boundaries_candidates_and_checksum(self) -> None:
        report = REPORT_PATH.read_text(encoding="utf-8")
        for required in (
            "No volatile-exposure rule",
            "three times the median",
            "Observed continuity-boundary distributions",
            "Timestamp and gap warning flags",
            "Pairwise disagreement matrix",
            "Named protocol candidates — comparison only",
            "None is recommended or selected",
            "No API request or raw download occurred",
            "Phase 5D stops here",
        ):
            self.assertIn(required, report)
        self.assertEqual(sha256_path(REPORT_PATH), self.summary["report_sha256"])


if __name__ == "__main__":
    unittest.main()

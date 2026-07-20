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
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.protocol_v1_2 import (  # noqa: E402
    EXPECTED_ELIGIBLE_IDS_SHA256,
    EXPECTED_INELIGIBLE_IDS_SHA256,
    PHASE6C_SOURCE_COMMIT,
    SELECTED_CANDIDATE_ID,
    sorted_caseid_checksum,
)


def read_csv(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProtocolV12ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = read_csv("final_eligible_cohort_manifest.csv")
        cls.eligible = read_csv("final_eligible_caseids.csv")
        cls.ineligible = read_csv("final_ineligible_caseids.csv")
        cls.sensitivity = read_csv("protocol_v1_2_sensitivity_reference.csv")
        cls.summary = json.loads((MANIFESTS / "final_cohort_accounting_summary.json").read_text(encoding="utf-8"))
        cls.freeze = json.loads((MANIFESTS / "protocol_v1_2_cohort_freeze.json").read_text(encoding="utf-8"))
        cls.source = json.loads((MANIFESTS / "protocol_v1_2_source_snapshot.json").read_text(encoding="utf-8"))

    def test_final_manifest_has_exact_2470_2460_10_accounting(self) -> None:
        self.assertEqual(len(self.manifest), 2470)
        self.assertEqual(len({int(row["caseid"]) for row in self.manifest}), 2470)
        self.assertEqual([int(row["caseid"]) for row in self.manifest], sorted(int(row["caseid"]) for row in self.manifest))
        eligible = [row for row in self.manifest if row["final_eligible"] == "true"]
        excluded = [row for row in self.manifest if row["final_eligible"] == "false"]
        self.assertEqual(len(eligible), 2460)
        self.assertEqual(len(excluded), 10)
        self.assertEqual(Counter(row["exclusion_reason"] for row in self.manifest), {
            "eligible": 2460, "ineligible_fewer_than_120_usable_windows": 10,
        })
        for row in self.manifest:
            windows = int(row["selected_candidate_usable_window_count"])
            expected = windows >= 120
            self.assertEqual(row["passes_minimum_120_windows"], str(expected).lower())
            self.assertEqual(row["final_eligible"], str(expected).lower())
            self.assertEqual(row["selected_candidate_id"], SELECTED_CANDIDATE_ID)
            self.assertEqual(row["source_pre_quality_inclusion"], "true")
            self.assertEqual(row["cohort_frozen"], "true")

    def test_final_id_lists_match_manifest_and_pinned_checksums(self) -> None:
        manifest_eligible = sorted(int(row["caseid"]) for row in self.manifest if row["final_eligible"] == "true")
        manifest_excluded = sorted(int(row["caseid"]) for row in self.manifest if row["final_eligible"] == "false")
        self.assertEqual([int(row["caseid"]) for row in self.eligible], manifest_eligible)
        self.assertEqual([int(row["caseid"]) for row in self.ineligible], manifest_excluded)
        self.assertEqual(len(self.eligible), 2460)
        self.assertEqual(len(self.ineligible), 10)
        self.assertEqual(sorted_caseid_checksum(manifest_eligible), EXPECTED_ELIGIBLE_IDS_SHA256)
        self.assertEqual(sorted_caseid_checksum(manifest_excluded), EXPECTED_INELIGIBLE_IDS_SHA256)
        self.assertEqual(manifest_excluded, [103, 335, 2602, 2791, 2857, 3733, 4201, 4694, 5979, 6221])

    def test_freeze_json_pins_protocol_candidate_threshold_and_manifest(self) -> None:
        self.assertEqual(self.freeze["protocol_version"], "1.2")
        self.assertEqual(self.freeze["source_commit_sha"], PHASE6C_SOURCE_COMMIT)
        self.assertEqual(self.freeze["selected_candidate_id"], SELECTED_CANDIDATE_ID)
        self.assertEqual(self.freeze["minimum_usable_window_count"], 120)
        self.assertEqual(self.freeze["source_case_count"], 2470)
        self.assertEqual(self.freeze["eligible_case_count"], 2460)
        self.assertEqual(self.freeze["excluded_case_count"], 10)
        self.assertEqual(self.freeze["sorted_eligible_case_ids_sha256"], EXPECTED_ELIGIBLE_IDS_SHA256)
        self.assertEqual(self.freeze["full_cohort_manifest_sha256"], sha256(MANIFESTS / "final_eligible_cohort_manifest.csv"))
        self.assertTrue(self.freeze["cohort_frozen"])
        self.assertFalse(self.freeze["split_created"])
        self.assertFalse(self.freeze["modeling_arrays_created"])
        self.assertFalse(self.freeze["outcome_or_model_used"])
        parameters = self.freeze["selected_preprocessing_parameters"]
        self.assertEqual(parameters["sqi_exact_timestamp_threshold"], 50)
        self.assertEqual(parameters["bis_staleness_cap_seconds"], 20)
        self.assertEqual(parameters["drug_rate_hold_cap_seconds"], 60)
        self.assertTrue(parameters["bis_0_10_admissible"])
        self.assertNotIn("BIS/SQI", ["BIS/BIS", "Orchestra/PPF20_RATE", "Orchestra/RFTN20_RATE"])

    def test_inherited_legacy_volatile_and_invalid_window_exclusions_cannot_reenter(self) -> None:
        self.assertTrue(all(row["legacy_98_overlap"] == "false" for row in self.manifest))
        self.assertTrue(all(row["volatile_excluded_overlap"] == "false" for row in self.manifest))
        self.assertTrue(all(row["invalid_anesthesia_window_overlap"] == "false" for row in self.manifest))
        pre = read_csv("pre_quality_acquisition_cohort.csv")
        final_ids = {int(row["caseid"]) for row in self.manifest if row["final_eligible"] == "true"}
        for flag in ("legacy_98_overlap", "volatile_positive_run_ge_10s", "invalid_anesthesia_window"):
            excluded = {int(row["caseid"]) for row in pre if row[flag] == "true"}
            self.assertEqual(final_ids & excluded, set(), flag)
        self.assertNotIn(4476, final_ids)
        self.assertEqual(self.summary["legacy_overlap_count"], 0)
        self.assertEqual(self.summary["volatile_excluded_overlap_count"], 0)
        self.assertEqual(self.summary["invalid_anesthesia_window_overlap_count"], 0)

    def test_demographic_feasibility_and_warnings_are_preserved_not_new_cutoffs(self) -> None:
        source = {int(row["caseid"]): row for row in read_csv("causal_grid_demographics_pk_input_feasibility.csv")}
        for row in self.manifest:
            original = source[int(row["caseid"])]
            self.assertEqual(row["all_four_demographics_present"], original["all_four_demographics_present"])
            self.assertEqual(row["schnider_minto_basic_input_feasible"], original["schnider_minto_basic_numeric_inputs_present"])
        self.assertEqual(self.summary["all_four_demographics_present_count"], 2470)
        self.assertEqual(self.summary["schnider_minto_basic_input_feasible_count"], 2470)
        self.assertTrue(all(row["outcome_or_model_used_for_eligibility"] == "false" for row in self.manifest))

    def test_excluded_cases_preserve_all_contributing_flags(self) -> None:
        self.assertTrue(all(row["contributing_fewer_than_120_windows"] == "true" for row in self.ineligible))
        by_id = {int(row["caseid"]): row for row in self.ineligible}
        self.assertEqual(by_id[103]["contributing_zero_usable_windows"], "true")
        self.assertEqual(by_id[103]["contributing_no_usable_bis_sqi_history"], "true")
        self.assertEqual(by_id[335]["contributing_no_candidate_grid_points"], "true")
        self.assertEqual(by_id[335]["contributing_no_usable_bis_sqi_history"], "false")
        self.assertEqual(by_id[2791]["contributing_zero_usable_windows"], "false")

    def test_sensitivity_counts_are_exact_phase6c_links_not_additional_freezes(self) -> None:
        source = {
            (row["candidate_id"], int(row["minimum_usable_windows"])): int(row["pass_case_count"])
            for row in read_csv("causal_grid_minimum_window_sensitivity.csv")
        }
        self.assertEqual(len(self.sensitivity), 13)
        for row in self.sensitivity:
            key = (row["candidate_id"], int(row["minimum_usable_windows"]))
            self.assertEqual(int(row["eligible_case_count"]), source[key])
            self.assertEqual(row["robustness_reference_only"], "true")
            self.assertEqual(row["final_cohort"], "false")
            self.assertEqual(row["selected"], "false")
        self.assertEqual(self.summary["primary_final_cohort_count"], 1)

    def test_protocol_record_separates_fact_decision_interpretation_and_reasons(self) -> None:
        text = (ROOT / "docs" / "protocol_v1_2_decision_record.md").read_text(encoding="utf-8")
        for phrase in (
            "## Provenance", "### Fact", "### Human decision", "### Interpretation",
            "BIS 0–10 remains admissible", "SQI 80", "120-, 300-, and 600-second",
            "300 and 600 thresholds were not selected", "No test outcome",
            "not described as 20 continuous minutes", "exactly one primary final cohort",
        ):
            self.assertIn(phrase, text)

    def test_source_snapshot_proves_artifact_only_scope_and_no_downstream_execution(self) -> None:
        self.assertEqual(self.source["phase6c_source_commit"], PHASE6C_SOURCE_COMMIT)
        self.assertTrue(self.source["phase6c_checksum_inventory_verified"])
        self.assertTrue(self.source["phase6c_remote_sha_verified_before_phase6d"])
        self.assertEqual(self.source["raw_tree_before"], self.source["raw_tree_after"])
        self.assertEqual(self.source["raw_tree_before"]["file_count"], 19761)
        self.assertEqual(self.source["raw_tree_before"]["total_bytes"], 2673762558)
        self.assertEqual(self.source["raw_tree_before"]["partial_file_count"], 0)
        self.assertEqual(self.source["raw_signal_file_open_count"], 0)
        self.assertEqual(self.source["new_raw_file_count"], 0)
        self.assertEqual(self.source["api_request_count"], 0)
        self.assertTrue(self.source["legacy_state_unchanged"])
        self.assertFalse(self.source["legacy_case_ids_accessed"])
        self.assertFalse(self.source["sqi_in_prediction_feature_universe"])
        self.assertTrue(self.source["bis_0_10_admissible"])
        self.assertFalse(self.source["first_n_sampling"])
        self.assertFalse(self.source["cohort_regeneration_from_model_result"])
        flags = self.summary["execution_flags"]
        self.assertEqual(flags["api_requests"], 0)
        self.assertEqual(flags["raw_signal_reads"], 0)
        self.assertEqual(flags["new_raw_files"], 0)
        self.assertTrue(all(value is False for key, value in flags.items() if key not in {"api_requests", "raw_signal_reads", "new_raw_files"}))

    def test_source_checksums_lineage_raw_git_and_artifact_checksums(self) -> None:
        for relative, expected in self.source["input_artifact_sha256"].items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", PHASE6C_SOURCE_COMMIT, "HEAD"], cwd=ROOT,
            check=False,
        )
        self.assertEqual(ancestor.returncode, 0)
        tracked_raw = subprocess.check_output(["git", "ls-files", "data/raw"], cwd=ROOT, text=True).splitlines()
        self.assertEqual(tracked_raw, [])
        inventory = json.loads((MANIFESTS / "protocol_v1_2_artifact_checksums.json").read_text(encoding="utf-8"))
        self.assertEqual(len(inventory), 9)
        for relative, expected in inventory.items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)

    def test_phase6d_entrypoint_has_no_network_raw_parser_or_model_capability(self) -> None:
        code = (ROOT / "scripts" / "freeze_protocol_v1_2_cohort.py").read_text(encoding="utf-8")
        self.assertNotIn("import requests", code)
        self.assertNotIn("VitalDBOpenAPI", code)
        self.assertNotIn("parse_observation_index", code)
        self.assertNotIn("ElasticNet", code)
        self.assertNotIn("torch", code)
        self.assertNotIn("sklearn", code)


if __name__ == "__main__":
    unittest.main()

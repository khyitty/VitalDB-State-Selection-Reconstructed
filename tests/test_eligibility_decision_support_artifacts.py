from __future__ import annotations

import csv
import hashlib
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.decision_support import (  # noqa: E402
    RATE_DOCUMENTATION,
    RELEVANT_TRACK_SPECS,
)
from vitaldb_state_selection.cohort.guards import assert_manifest_complete  # noqa: E402
from vitaldb_state_selection.cohort.track_inventory import AliasRegistry  # noqa: E402
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    read_csv_manifest,
)


MANIFEST_DIR = ROOT / "data" / "manifests"
PRESENCE_PATH = MANIFEST_DIR / "research_relevant_track_presence.csv"
TRACK_REVIEW_PATH = MANIFEST_DIR / "research_relevant_unapproved_tracks.csv"
SUMMARY_PATH = MANIFEST_DIR / "eligibility_decision_support_summary.json"
SNAPSHOT_PATH = MANIFEST_DIR / "eligibility_decision_support_source_snapshot.json"
FAILURE_PATH = MANIFEST_DIR / "eligibility_decision_support_failures.jsonl"
CHECKSUM_PATH = MANIFEST_DIR / "eligibility_decision_support_artifact_checksums.json"
REPORT_PATH = ROOT / "docs" / "decision_support_report.md"


def _bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise AssertionError(f"unexpected boolean encoding: {value!r}")


class EligibilityDecisionSupportArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = load_schema(ROOT / "schemas" / "eligibility_manifest.schema.json")
        cls.manifest = read_csv_manifest(
            MANIFEST_DIR / "all_case_eligibility_manifest.csv", schema
        )
        with PRESENCE_PATH.open(encoding="utf-8", newline="") as stream:
            raw_presence = list(csv.DictReader(stream))
        cls.presence = [
            {
                key: int(value) if key == "caseid" else _bool(value)
                for key, value in row.items()
            }
            for row in raw_presence
        ]
        with TRACK_REVIEW_PATH.open(encoding="utf-8", newline="") as stream:
            cls.track_review = list(csv.DictReader(stream))
        cls.summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        cls.snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        cls.failure_rows = [
            json.loads(line)
            for line in FAILURE_PATH.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_phase5b_has_exact_full_case_accounting(self) -> None:
        manifest_caseids = [int(row["caseid"]) for row in self.manifest]
        presence_caseids = [int(row["caseid"]) for row in self.presence]
        assert_manifest_complete(manifest_caseids)
        assert_manifest_complete(presence_caseids)
        self.assertEqual(manifest_caseids, list(range(1, 6389)))
        self.assertEqual(presence_caseids, manifest_caseids)
        self.assertEqual(self.summary["case_accounting"]["duplicate_case_count"], 0)
        self.assertEqual(self.summary["case_accounting"]["missing_case_count"], 0)

    def test_full_manifest_descriptors_recompute_without_outcomes(self) -> None:
        descriptive = self.summary["full_manifest_descriptive"]
        for field, key in (
            ("anesthesia_type", "anesthesia_type_frequency"),
            ("operation_type", "operation_type_frequency"),
            ("emergency_status", "emergency_status_frequency"),
        ):
            actual = Counter(str(row[field]) if row[field] is not None else "<missing>" for row in self.manifest)
            reported = {item["value"]: item["case_count"] for item in descriptive[key]}
            self.assertEqual(reported, dict(actual), field)
        ages = [float(row["age"]) for row in self.manifest if row["age"] is not None]
        self.assertEqual(descriptive["age"]["minimum"], min(ages))
        self.assertEqual(descriptive["age"]["maximum"], max(ages))
        self.assertEqual(
            descriptive["asa_missingness"]["missing_count"],
            sum(row["asa"] is None for row in self.manifest),
        )
        forbidden_keys = {"bis_value", "target", "mae", "prediction"}
        self.assertFalse(forbidden_keys & set(descriptive))

    def test_exact_primary_subset_and_requested_crosstabs_recompute(self) -> None:
        presence_by_case = {row["caseid"]: row for row in self.presence}
        joined = [
            {**row, **presence_by_case[int(row["caseid"])]} for row in self.manifest
        ]
        primary = [
            row
            for row in joined
            if all(
                row[f"{concept}_track_available"] is True
                for concept in ("bis", "propofol_rate", "remifentanil_rate")
            )
        ]
        self.assertEqual(len(primary), 3289)
        reported = self.summary["exact_primary_subset"]
        self.assertEqual(reported["case_count"], len(primary))
        anesthesia = Counter(str(row["anesthesia_type"]) for row in primary)
        self.assertEqual(
            {item["value"]: item["case_count"] for item in reported["anesthesia_type_frequency"]},
            dict(anesthesia),
        )
        self.assertEqual(
            sum(item["descriptive_expected_case_count"] for item in reported["combination_counts"]),
            3289,
        )
        requested_fields = {
            spec.field
            for spec in RELEVANT_TRACK_SPECS
            if spec.requested_scope in {
                "bis_sqi",
                "propofol_support",
                "remifentanil_20_support",
                "remifentanil_50_support",
            }
            and not spec.field.endswith("_ct_present")
        }
        self.assertEqual(set(reported["track_presence"]), requested_fields)
        for field in requested_fields:
            expected_present = sum(row[field] is True for row in primary)
            counts = {
                item["value"]: item["case_count"]
                for item in reported["track_presence"][field]
            }
            self.assertEqual(counts.get("present", 0), expected_present, field)
            self.assertEqual(counts.get("absent", 0), 3289 - expected_present, field)

    def test_scenarios_are_unselected_and_exclusions_balance(self) -> None:
        by_case = {row["caseid"]: row for row in self.presence}
        exact = [
            row
            for row in self.manifest
            if all(
                row[f"{concept}_track_available"] is True
                for concept in ("bis", "propofol_rate", "remifentanil_rate")
            )
        ]
        adult_general = [
            row
            for row in exact
            if row["adult_candidate"] is True and row["anesthesia_type"] == "General"
        ]
        no_volatile = [
            row
            for row in adult_general
            if by_case[int(row["caseid"])]["volatile_candidate_track_present"] is False
        ]
        expected = [len(exact), len(adult_general), len(no_volatile)]
        scenarios = self.summary["eligibility_scenarios"]
        self.assertEqual(
            [row["descriptive_expected_case_count"] for row in scenarios], expected
        )
        for row in scenarios:
            self.assertEqual(
                row["descriptive_expected_case_count"] + row["excluded_case_count"],
                6388,
            )
            self.assertEqual(
                sum(row["sequential_exclusion_reason_counts"].values()),
                row["excluded_case_count"],
            )
        self.assertIsNone(self.summary["selected_scenario"])
        self.assertFalse(self.summary["execution_flags"]["cohort_frozen"])

    def test_relevant_track_review_is_narrow_pending_and_unmerged(self) -> None:
        expected_names = {spec.track_name for spec in RELEVANT_TRACK_SPECS}
        actual_names = {row["track_name"] for row in self.track_review}
        self.assertEqual(actual_names, expected_names)
        self.assertEqual(len(actual_names), 21)
        self.assertTrue(
            all(row["review_status"] == "pending_human_review" for row in self.track_review)
        )
        self.assertTrue(all(row["auto_approved"] == "false" for row in self.track_review))
        self.assertTrue(
            all(row["merged_with_other_track"] == "false" for row in self.track_review)
        )
        review = self.summary["relevant_track_review"]
        self.assertFalse(review["all_193_semantically_classified"])
        self.assertFalse(review["rftn20_rftn50_merged"])
        self.assertEqual(review["auto_approved_count"], 0)

    def test_rate_evidence_does_not_change_alias_configuration(self) -> None:
        evidence = self.summary["rate_and_label_primary_source_review"]
        self.assertEqual(evidence["findings"], [dict(item) for item in RATE_DOCUMENTATION])
        self.assertFalse(evidence["automatic_merge_performed"])
        self.assertFalse(evidence["config_unit_status_changed"])
        self.assertEqual(evidence["final_review_status"], "pending_human_review")
        registry = AliasRegistry.from_yaml(ROOT / "configs" / "track_aliases.yaml")
        self.assertTrue(all(status == "validated" for status in registry.unit_status.values()))

    def test_source_snapshot_is_metadata_only_and_matches_phase5a(self) -> None:
        phase5a = json.loads(
            (MANIFEST_DIR / "metadata_audit_source_snapshot.json").read_text(encoding="utf-8")
        )
        self.assertEqual(self.snapshot["phase"], "5B_eligibility_decision_support_audit")
        self.assertEqual(
            self.snapshot["audit_code_base_commit"],
            "1c886afa184aabb28a85dd3a6da95ae7233551eb",
        )
        self.assertEqual(self.snapshot["scope"]["queried_endpoints"], ["/trks"])
        self.assertEqual(self.snapshot["scope"]["raw_time_series_requests"], 0)
        self.assertFalse(self.snapshot["scope"]["legacy_98_ids_accessed"])
        self.assertFalse(self.snapshot["scope"]["legacy_overlap_evaluated"])
        self.assertFalse(self.snapshot["scope"]["all_unapproved_names_semantically_classified"])
        self.assertEqual(
            self.snapshot["endpoint"]["sha256"],
            phase5a["endpoints"]["tracks"]["sha256"],
        )
        self.assertTrue(self.snapshot["endpoint"]["matches_phase5a_snapshot"])
        self.assertTrue(
            all(value is False for value in self.snapshot["prohibited_execution"].values())
        )
        self.assertEqual(self.failure_rows, [])

    def test_report_boundaries_and_artifact_checksums(self) -> None:
        report = REPORT_PATH.read_text(encoding="utf-8")
        self.assertIn("not an eligibility rule", report)
        self.assertIn("Track presence does not prove", report)
        self.assertIn("No scenario was selected", report)
        self.assertIn("No raw-signal download", report)
        checksums = json.loads(CHECKSUM_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            set(checksums),
            {
                "data/manifests/research_relevant_track_presence.csv",
                "data/manifests/research_relevant_unapproved_tracks.csv",
                "data/manifests/eligibility_decision_support_summary.json",
                "data/manifests/eligibility_decision_support_source_snapshot.json",
                "data/manifests/eligibility_decision_support_failures.jsonl",
                "docs/decision_support_report.md",
            },
        )
        for relative, expected in checksums.items():
            actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)


if __name__ == "__main__":
    unittest.main()

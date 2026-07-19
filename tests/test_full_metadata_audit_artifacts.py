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

from vitaldb_state_selection.cohort.guards import (  # noqa: E402
    assert_manifest_complete,
)
from vitaldb_state_selection.cohort.metadata_audit import (  # noqa: E402
    EXPECTED_ACTIVE_ALIASES,
    sha256_path,
)
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    read_csv_manifest,
)


MANIFEST_DIR = ROOT / "data" / "manifests"
MANIFEST_PATH = MANIFEST_DIR / "all_case_eligibility_manifest.csv"
SUMMARY_PATH = MANIFEST_DIR / "metadata_audit_summary.json"
SNAPSHOT_PATH = MANIFEST_DIR / "metadata_audit_source_snapshot.json"
CANDIDATE_PATH = MANIFEST_DIR / "unapproved_alias_candidates.csv"
FAILURE_PATH = MANIFEST_DIR / "metadata_audit_failures.jsonl"
CHECKSUM_PATH = MANIFEST_DIR / "metadata_audit_artifact_checksums.json"
REPORT_PATH = ROOT / "docs" / "full_metadata_track_inventory_audit_report.md"


class FullMetadataAuditArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = load_schema(ROOT / "schemas" / "eligibility_manifest.schema.json")
        cls.records = read_csv_manifest(MANIFEST_PATH, schema)
        cls.summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        cls.snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        with CANDIDATE_PATH.open(encoding="utf-8", newline="") as stream:
            cls.candidates = list(csv.DictReader(stream))
        cls.failure_rows = [
            json.loads(line)
            for line in FAILURE_PATH.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_manifest_has_exact_full_accounting_and_pending_decisions(self) -> None:
        caseids = [int(row["caseid"]) for row in self.records]
        assert_manifest_complete(caseids)
        self.assertEqual(caseids, list(range(1, 6389)))
        self.assertEqual(len(self.records), 6388)
        self.assertTrue(all(row["audit_status"] == "complete" for row in self.records))
        self.assertTrue(all(row["legacy_98_case"] is None for row in self.records))
        self.assertTrue(all(row["tiva_candidate"] is None for row in self.records))
        self.assertTrue(
            all(row["volatile_exposure_possible"] is None for row in self.records)
        )
        self.assertTrue(
            all(row["candidate_at_metadata_stage"] is False for row in self.records)
        )
        self.assertTrue(
            all(
                "legacy_overlap_not_evaluated" in row["metadata_exclusion_flags"]
                for row in self.records
            )
        )

    def test_summary_recomputes_from_the_full_manifest(self) -> None:
        combinations: Counter[str] = Counter()
        for row in self.records:
            combinations[
                "|".join(
                    f"{concept}={int(bool(row[f'{concept}_track_available']))}"
                    for concept in ("bis", "propofol_rate", "remifentanil_rate")
                )
            ] += 1
        self.assertEqual(
            self.summary["exact_track_combination_counts"], dict(sorted(combinations.items()))
        )
        self.assertEqual(sum(combinations.values()), 6388)
        self.assertEqual(self.summary["duplicate_manifest_case_count"], 0)
        self.assertEqual(self.summary["missing_manifest_case_count"], 0)
        self.assertEqual(self.summary["audit_failed_count"], 0)
        for field, expected in self.summary["metadata_missing_counts"].items():
            self.assertEqual(
                expected,
                sum(row[field] is None for row in self.records),
                field,
            )
        self.assertEqual(self.summary["failure_log_row_count"], len(self.failure_rows))

    def test_source_snapshots_and_scope_are_phase5a_only(self) -> None:
        self.assertEqual(self.snapshot["phase"], "5A_full_metadata_and_track_inventory")
        self.assertEqual(self.snapshot["audit_code_base_commit"], "5273fc6ea1d35d3bd356d5ff52638e4e45dc719c")
        self.assertEqual(self.snapshot["scope"]["queried_endpoints"], ["/cases", "/trks"])
        self.assertEqual(self.snapshot["scope"]["raw_time_series_requests"], 0)
        self.assertFalse(self.snapshot["scope"]["legacy_98_ids_accessed"])
        self.assertFalse(self.snapshot["scope"]["legacy_overlap_evaluated"])
        self.assertTrue(
            all(value is False for value in self.snapshot["prohibited_execution"].values())
        )
        self.assertEqual(
            self.snapshot["active_exact_aliases"],
            {concept: list(names) for concept, names in EXPECTED_ACTIVE_ALIASES.items()},
        )
        endpoints = self.snapshot["endpoints"]
        self.assertEqual(endpoints["cases"]["status"], "complete")
        self.assertEqual(endpoints["cases"]["row_count"], 6388)
        self.assertEqual(endpoints["tracks"]["status"], "complete")
        self.assertEqual(
            endpoints["tracks"]["row_count"], self.summary["source_track_row_count"]
        )
        for endpoint in endpoints.values():
            self.assertRegex(endpoint["sha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(endpoint["fetched_at"], r"^2026-\d\d-\d\dT")
        expected_config_hashes = {
            "eligibility_audit_yaml_sha256": sha256_path(
                ROOT / "configs" / "eligibility_audit.yaml"
            ),
            "track_aliases_yaml_sha256": sha256_path(
                ROOT / "configs" / "track_aliases.yaml"
            ),
            "eligibility_manifest_schema_sha256": sha256_path(
                ROOT / "schemas" / "eligibility_manifest.schema.json"
            ),
        }
        self.assertEqual(self.snapshot["configuration_checksums"], expected_config_hashes)
        self.assertEqual(
            {row["source_query_timestamp"] for row in self.records},
            {self.snapshot["query_started_at"]},
        )
        self.assertEqual(
            {row["source_version"] for row in self.records},
            {self.snapshot["source_version"]},
        )

    def test_unapproved_names_are_all_pending_and_never_auto_approved(self) -> None:
        approved_names = {
            name for names in EXPECTED_ACTIVE_ALIASES.values() for name in names
        }
        reported_names = {row["track_name"] for row in self.candidates}
        self.assertFalse(approved_names & reported_names)
        self.assertEqual(len(self.candidates), self.summary["unapproved_track_name_count"])
        self.assertEqual(
            sum(int(row["row_count"]) for row in self.candidates),
            self.summary["unapproved_track_row_count"],
        )
        self.assertTrue(
            all(row["review_status"] == "pending_human_review" for row in self.candidates)
        )
        self.assertTrue(all(row["auto_approved"] == "False" for row in self.candidates))
        report = REPORT_PATH.read_text(encoding="utf-8")
        self.assertIn("No raw time-series signal was downloaded", report)
        self.assertIn("Legacy 98-case IDs were not read", report)
        self.assertTrue(all(f"`{name}`" in report for name in reported_names))

    def test_all_phase5a_artifact_checksums_match(self) -> None:
        inventory = json.loads(CHECKSUM_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            set(inventory),
            {
                "data/manifests/all_case_eligibility_manifest.csv",
                "data/manifests/metadata_audit_failures.jsonl",
                "data/manifests/metadata_audit_source_snapshot.json",
                "data/manifests/metadata_audit_summary.json",
                "data/manifests/unapproved_alias_candidates.csv",
                "docs/full_metadata_track_inventory_audit_report.md",
            },
        )
        for relative, expected in inventory.items():
            actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)


if __name__ == "__main__":
    unittest.main()

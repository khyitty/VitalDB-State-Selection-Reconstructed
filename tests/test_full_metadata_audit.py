from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.eligibility import (  # noqa: E402
    build_eligibility_records,
    load_audit_config,
)
from vitaldb_state_selection.cohort.clinical_metadata import (  # noqa: E402
    parse_clinical_row,
    time_range_is_valid,
)
from vitaldb_state_selection.cohort.guards import CohortGuardError  # noqa: E402
from vitaldb_state_selection.cohort.metadata_audit import (  # noqa: E402
    EXPECTED_ACTIVE_ALIASES,
    assert_phase5a_boundaries,
    build_unapproved_alias_candidates,
    prepare_source_rows,
    render_outcome_blind_report,
    summarize_full_metadata_audit,
)
from vitaldb_state_selection.cohort.track_inventory import (  # noqa: E402
    AliasRegistry,
)


def clinical(caseid: int) -> dict[str, object]:
    return {
        "caseid": caseid,
        "subjectid": f"subject-{caseid}",
        "age": 50,
        "sex": "M",
        "height": 170,
        "weight": 70,
        "bmi": 24.2,
        "asa": 2,
        "anetype": "General",
        "optype": "Synthetic",
        "emop": 0,
        "anestart": 10,
        "aneend": 1000,
        "opstart": 50,
        "opend": 900,
    }


def approved_tracks(caseid: int) -> list[dict[str, object]]:
    return [
        {"caseid": caseid, "tname": "BIS/BIS", "tid": f"bis-{caseid}"},
        {
            "caseid": caseid,
            "tname": "Orchestra/PPF20_RATE",
            "tid": f"prop-{caseid}",
        },
        {
            "caseid": caseid,
            "tname": "Orchestra/RFTN20_RATE",
            "tid": f"remi-{caseid}",
        },
    ]


class FullMetadataAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_audit_config(ROOT / "configs" / "eligibility_audit.yaml")
        cls.registry = AliasRegistry.from_yaml(ROOT / "configs" / "track_aliases.yaml")

    def test_phase5a_boundary_allows_exactly_three_names_after_unit_review(self) -> None:
        assert_phase5a_boundaries(self.config, self.registry)
        self.assertEqual(self.registry.active, EXPECTED_ACTIVE_ALIASES)
        expanded = AliasRegistry(
            schema_version=1,
            active={**self.registry.active, "unapproved": ("Similar/Name",)},
            unit_status={**self.registry.unit_status, "unapproved": "pending_human_review"},
            pending=self.registry.pending,
        )
        with self.assertRaisesRegex(CohortGuardError, "exactly three"):
            assert_phase5a_boundaries(self.config, expanded)

    def test_source_preparation_preserves_malformed_and_duplicate_track_events(self) -> None:
        duplicate = {"caseid": 2, "tname": "BIS/BIS", "tid": "tid-2"}
        result = prepare_source_rows(
            [
                {"caseid": "bad", "tname": "BIS/BIS", "tid": "bad"},
                {"caseid": 1, "tname": "", "tid": "tid-1"},
                duplicate,
                duplicate,
            ],
            source="tracks",
        )
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(
            [event["failure_type"] for event in result.events],
            ["invalid_caseid", "track_parse_error", "duplicate_track_row"],
        )
        self.assertIn(1, result.case_failures)
        self.assertIn(2, result.case_failures)

    def test_unapproved_names_are_reported_without_concept_assignment(self) -> None:
        rows = [
            *approved_tracks(1),
            {"caseid": 1, "tname": "BIS", "tid": "candidate-1"},
            {"caseid": 2, "tname": "BIS", "tid": "candidate-2"},
        ]
        candidates = build_unapproved_alias_candidates(rows, self.registry)
        self.assertEqual([row["track_name"] for row in candidates], ["BIS"])
        self.assertEqual(candidates[0]["row_count"], 2)
        self.assertEqual(candidates[0]["case_count"], 2)
        self.assertEqual(candidates[0]["review_status"], "pending_human_review")
        self.assertFalse(candidates[0]["auto_approved"])
        self.assertIsNone(self.registry.concept_for("BIS"))

    def test_negative_relative_event_time_is_not_assumed_invalid(self) -> None:
        row = clinical(1)
        row.update(anestart=-552, aneend=10848, opstart=1668, opend=10368)
        self.assertTrue(time_range_is_valid(parse_clinical_row(row)))

    def test_summary_accounts_for_all_cases_and_keeps_decisions_pending(self) -> None:
        track_rows = [
            *approved_tracks(1),
            {"caseid": 1, "tname": "Unapproved/Track", "tid": "unknown-1"},
        ]
        records = build_eligibility_records(
            [clinical(1)],
            track_rows,
            config=self.config,
            registry=self.registry,
            source_version="synthetic-v1",
            query_timestamp="2026-07-20T00:00:00+00:00",
            legacy_caseids=None,
        )
        candidates = build_unapproved_alias_candidates(track_rows, self.registry)
        summary = summarize_full_metadata_audit(
            records,
            track_rows=track_rows,
            source_events=[],
            candidates=candidates,
        )
        self.assertEqual(summary["record_count"], 6388)
        self.assertEqual(sum(summary["exact_track_combination_counts"].values()), 6388)
        self.assertEqual(summary["duplicate_manifest_case_count"], 0)
        self.assertEqual(summary["missing_manifest_case_count"], 0)
        self.assertFalse(summary["legacy_overlap_evaluated"])
        self.assertEqual(summary["metadata_candidate_count"], 0)
        for prohibited in (
            "quality_thresholds_finalized",
            "cohort_frozen",
            "split_created",
            "raw_signal_downloaded",
            "prediction_run",
            "feature_selection_run",
            "cpce_reconstruction_run",
            "ppo_run",
        ):
            self.assertFalse(summary[prohibited], prohibited)

    def test_report_and_entry_point_are_metadata_only(self) -> None:
        summary = {
            "record_count": 6388,
            "duplicate_manifest_case_count": 0,
            "missing_manifest_case_count": 0,
            "audit_complete_count": 6388,
            "audit_failed_count": 0,
            "clinical_metadata_missing_count": 0,
            "track_inventory_missing_count": 0,
            "metadata_missing_counts": {"age": 0, "sex": 0, "height": 0, "weight": 0},
            "exact_track_combination_counts": {
                "bis=1|propofol_rate=1|remifentanil_rate=1": 6388
            },
            "audit_failure_type_counts": {},
            "source_row_failure_type_counts": {},
            "api_failure_type_counts": {},
            "unapproved_track_name_count": 0,
        }
        snapshot = {
            "endpoints": {
                "cases": {"status": "complete", "row_count": 6388, "byte_count": 1, "sha256": "a" * 64},
                "tracks": {"status": "complete", "row_count": 1, "byte_count": 1, "sha256": "b" * 64},
            }
        }
        report = render_outcome_blind_report(summary, snapshot, [])
        self.assertIn("No raw time-series signal was downloaded", report)
        self.assertIn("Legacy 98-case IDs were not read", report)

        script = ROOT / "scripts" / "run_metadata_audit.py"
        tree = ast.parse(script.read_text(encoding="utf-8"))
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertIn("fetch_cases", called_attributes)
        self.assertIn("fetch_tracks", called_attributes)
        self.assertNotIn("fetch_track", called_attributes)
        self.assertNotIn("VitalDB-Feature-Selection", script.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

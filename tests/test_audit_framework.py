from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.eligibility import (  # noqa: E402
    build_eligibility_records,
    load_audit_config,
)
from vitaldb_state_selection.cohort.guards import CohortGuardError  # noqa: E402
from vitaldb_state_selection.cohort.track_inventory import AliasRegistry  # noqa: E402
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    read_csv_manifest,
    write_csv_manifest,
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


def tracks(caseid: int) -> list[dict[str, object]]:
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


class EligibilityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_audit_config(ROOT / "configs" / "eligibility_audit.yaml")
        cls.registry = AliasRegistry.from_yaml(ROOT / "configs" / "track_aliases.yaml")
        cls.schema = load_schema(ROOT / "schemas" / "eligibility_manifest.schema.json")

    def build(self, clinical_rows, track_rows):
        return build_eligibility_records(
            clinical_rows,
            track_rows,
            config=self.config,
            registry=self.registry,
            source_version="synthetic-v1",
            query_timestamp="2026-07-19T00:00:00+00:00",
        )

    def test_all_6388_cases_receive_exactly_one_row(self) -> None:
        clinical_rows = [clinical(caseid) for caseid in range(1, 6389)]
        track_rows = [row for caseid in range(1, 6389) for row in tracks(caseid)]
        records = self.build(clinical_rows, track_rows)
        self.assertEqual(len(records), 6388)
        self.assertEqual([record["caseid"] for record in records], list(range(1, 6389)))
        self.assertTrue(all(record["audit_status"] == "complete" for record in records))
        self.assertTrue(all(record["candidate_at_metadata_stage"] is False for record in records))
        self.assertTrue(all(record["legacy_98_case"] is None for record in records))
        self.assertTrue(
            all("tiva_classification_pending" in record["metadata_exclusion_flags"] for record in records)
        )

    def test_missing_case_is_a_failed_manifest_row_not_silently_removed(self) -> None:
        records = self.build([clinical(1)], tracks(1))
        self.assertEqual(len(records), 6388)
        missing = records[-1]
        self.assertEqual(missing["caseid"], 6388)
        self.assertEqual(missing["audit_status"], "failed")
        self.assertEqual(missing["failure_type"], "clinical_metadata_missing")

    def test_duplicate_clinical_case_is_explicit_failure(self) -> None:
        records = self.build([clinical(1), clinical(1)], tracks(1))
        first = records[0]
        self.assertEqual(first["audit_status"], "failed")
        self.assertEqual(first["failure_type"], "duplicate_clinical_rows")

    def test_out_of_range_source_case_is_rejected(self) -> None:
        with self.assertRaises(CohortGuardError):
            self.build([clinical(6389)], [])

    def test_alias_matching_is_exact_and_pending_aliases_remain_null(self) -> None:
        wrong_name = tracks(1)
        wrong_name[0] = {"caseid": 1, "tname": "BIS", "tid": "not-approved"}
        record = self.build([clinical(1)], wrong_name)[0]
        self.assertFalse(record["bis_track_available"])
        self.assertIsNone(record["bis_sqi_track_available"])
        self.assertIsNone(record["volatile_agent_track_available"])
        self.assertIn("bis_track_missing", record["metadata_exclusion_flags"])

    def test_manifest_round_trip_is_schema_validated(self) -> None:
        records = self.build([clinical(1)], tracks(1))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "eligibility.csv"
            write_csv_manifest(path, records, self.schema)
            restored = read_csv_manifest(path, self.schema)
        self.assertEqual(restored, records)

    def test_source_query_failure_still_accounts_for_every_case(self) -> None:
        records = build_eligibility_records(
            [],
            [],
            config=self.config,
            registry=self.registry,
            source_version="synthetic-failure",
            clinical_query_available=False,
            track_query_available=False,
            source_failures=["network_unavailable"],
        )
        self.assertEqual(len(records), 6388)
        self.assertTrue(all(record["audit_status"] == "failed" for record in records))
        self.assertTrue(all(record["failure_message"] for record in records))

    def test_quality_threshold_values_remain_null(self) -> None:
        payload = json.loads(json.dumps(self.config))
        thresholds = payload["quality_thresholds"]
        self.assertEqual(thresholds.pop("status"), "pending_human_review")
        self.assertTrue(all(value is None for value in thresholds.values()))

    def test_track_units_remain_pending_human_review(self) -> None:
        self.assertFalse(
            self.registry.units_validated(("propofol_rate", "remifentanil_rate"))
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.dry_run import (  # noqa: E402
    DRY_RUN_SEED,
    apply_signal_results,
    build_dry_run_metadata_records,
)
from vitaldb_state_selection.cohort.guards import fixed_seed_random_sample  # noqa: E402
from vitaldb_state_selection.cohort.track_inventory import AliasRegistry  # noqa: E402
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    validate_records,
)


def clinical(caseid: int) -> dict[str, object]:
    return {
        "caseid": caseid,
        "age": 50,
        "sex": "M",
        "height": 170,
        "weight": 70,
        "anestart": 10,
        "aneend": 100,
        "opstart": 20,
        "opend": 90,
    }


def tracks(caseid: int) -> list[dict[str, object]]:
    return [
        {"caseid": caseid, "tname": "BIS/BIS", "tid": f"b-{caseid}"},
        {"caseid": caseid, "tname": "Orchestra/PPF20_RATE", "tid": f"p-{caseid}"},
        {"caseid": caseid, "tname": "Orchestra/RFTN20_RATE", "tid": f"r-{caseid}"},
    ]


class EngineeringDryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = AliasRegistry.from_yaml(ROOT / "configs" / "track_aliases.yaml")
        cls.schema = load_schema(ROOT / "schemas" / "engineering_dry_run.schema.json")

    def test_fixed_seed_sample_and_schema_valid_metadata_records(self) -> None:
        sample = fixed_seed_random_sample(list(range(1, 6389)), seed=DRY_RUN_SEED)
        rows = [clinical(caseid) for caseid in sample]
        track_rows = [item for caseid in sample for item in tracks(caseid)]
        records, _ = build_dry_run_metadata_records(
            sample, rows, track_rows, registry=self.registry, source_version="synthetic"
        )
        validate_records(records, self.schema)
        self.assertEqual(len(records), 25)
        self.assertTrue(all(record["scientific_result"] is False for record in records))
        self.assertTrue(
            all(
                record["drug_rate_unit_status"]["propofol_rate"]
                == "validated"
                for record in records
            )
        )

    def test_signal_result_failure_is_preserved(self) -> None:
        sample = fixed_seed_random_sample(list(range(1, 6389)), seed=DRY_RUN_SEED)
        records, _ = build_dry_run_metadata_records(
            sample,
            [clinical(caseid) for caseid in sample],
            [item for caseid in sample for item in tracks(caseid)],
            registry=self.registry,
            source_version="synthetic",
        )
        downloads = [
            {
                "caseid": caseid,
                "status": "failed" if index == 0 else "complete",
                "attempt_count": 1,
                "bytes_downloaded": 0 if index == 0 else 10,
                "checksums": {} if index == 0 else {"bis.csv": "a" * 64},
                "failure_type": "SyntheticFailure" if index == 0 else None,
                "failure_message": "expected" if index == 0 else None,
            }
            for index, caseid in enumerate(sample)
        ]
        updated = apply_signal_results(records, downloads)
        validate_records(updated, self.schema)
        self.assertEqual(sum(row["signal_status"] == "failed" for row in updated), 1)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.dry_run import DRY_RUN_SEED  # noqa: E402
from vitaldb_state_selection.cohort.guards import fixed_seed_random_sample  # noqa: E402
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    read_csv_manifest,
)


ARTIFACT_DIR = ROOT / "data" / "manifests" / "engineering_dry_run_seed_20260719"


class DryRunArtifactTests(unittest.TestCase):
    def test_summary_is_fixed_random_engineering_only(self) -> None:
        summary = json.loads((ARTIFACT_DIR / "dry_run_summary.json").read_text(encoding="utf-8"))
        expected = fixed_seed_random_sample(list(range(1, 6389)), seed=DRY_RUN_SEED)
        self.assertEqual(summary["sample_caseids"], expected)
        self.assertEqual(summary["source_case_count"], 6388)
        self.assertFalse(summary["is_first_25"])
        self.assertFalse(summary["scientific_result"])
        self.assertEqual(summary["dry_run_label"], "engineering_only_not_a_scientific_result")
        for prohibited in (
            "quality_thresholds_finalized",
            "cohort_frozen",
            "split_created",
            "prediction_run",
            "feature_selection_run",
            "cpce_reconstruction_run",
            "ppo_run",
        ):
            self.assertFalse(summary[prohibited], prohibited)

    def test_all_25_signal_outcomes_and_failures_are_preserved(self) -> None:
        schema = load_schema(ROOT / "schemas" / "download_manifest.schema.json")
        rows = read_csv_manifest(ARTIFACT_DIR / "download_manifest.csv", schema)
        self.assertEqual(len(rows), 25)
        complete = [row for row in rows if row["status"] == "complete"]
        failed = [row for row in rows if row["status"] == "failed"]
        self.assertEqual(len(complete), 12)
        self.assertEqual(len(failed), 13)
        self.assertTrue(all(row["checksums"] for row in complete))
        self.assertTrue(all(row["failure_type"] for row in failed))
        self.assertEqual({row["attempt_count"] for row in rows}, {1})
        log_rows = [
            json.loads(line)
            for line in (ARTIFACT_DIR / "download_failures.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual({row["caseid"] for row in log_rows}, {row["caseid"] for row in failed})
        self.assertTrue(all(row.get("exception_summary") for row in log_rows))
        self.assertTrue(all("traceback" not in row for row in log_rows))

    def test_committed_artifact_checksums_match(self) -> None:
        inventory = json.loads(
            (ARTIFACT_DIR / "artifact_checksums.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(inventory),
            {
                "download_failures.jsonl",
                "download_manifest.csv",
                "dry_run_manifest.csv",
                "dry_run_summary.json",
            },
        )
        for relative, expected in inventory.items():
            actual = hashlib.sha256((ARTIFACT_DIR / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)


if __name__ == "__main__":
    unittest.main()

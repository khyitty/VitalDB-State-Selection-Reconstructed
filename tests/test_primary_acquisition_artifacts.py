from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
RAW_ROOT = ROOT / "data" / "raw" / "phase6a_primary_signals"
TRACKS = {
    "BIS/BIS", "BIS/SQI", "Orchestra/PPF20_RATE", "Orchestra/RFTN20_RATE"
}


def read_csv(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PrimaryAcquisitionArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cohort = read_csv("pre_quality_acquisition_cohort.csv")
        cls.downloads = read_csv("primary_signal_download_manifest.csv")
        cls.checksums = read_csv("primary_signal_checksum_manifest.csv")
        cls.summary = json.loads((MANIFESTS / "primary_signal_acquisition_summary.json").read_text(encoding="utf-8"))
        cls.preflight = json.loads((MANIFESTS / "primary_signal_preflight_summary.json").read_text(encoding="utf-8"))
        cls.source = json.loads((MANIFESTS / "primary_signal_source_snapshot.json").read_text(encoding="utf-8"))

    def test_pre_quality_cohort_accounts_for_3219_once_and_preserves_reasons(self) -> None:
        self.assertEqual(len(self.cohort), 3219)
        self.assertEqual(len({int(row["caseid"]) for row in self.cohort}), 3219)
        counts = Counter()
        included = 0
        for row in self.cohort:
            reasons = json.loads(row["exclusion_reasons"])
            expected = []
            if row["volatile_positive_run_ge_10s"] == "true":
                expected.append("volatile_positive_run_ge_10s")
                counts["volatile"] += 1
            if row["invalid_anesthesia_window"] == "true":
                expected.append("ineligible_invalid_anesthesia_window")
                counts["invalid"] += 1
            if row["legacy_98_overlap"] == "true":
                expected.append("legacy_98_overlap")
                counts["legacy"] += 1
            self.assertEqual(reasons, expected)
            is_included = row["included_for_primary_signal_acquisition"] == "true"
            self.assertEqual(is_included, not expected)
            included += is_included
            self.assertEqual(row["final_eligibility"], "pending_human_review")
            self.assertEqual(row["split_assigned"], "false")
        self.assertEqual(counts, {"volatile": 674, "invalid": 1, "legacy": 94})
        self.assertEqual(included, 2470)
        invalid = [row for row in self.cohort if row["invalid_anesthesia_window"] == "true"]
        self.assertEqual([int(row["caseid"]) for row in invalid], [4476])

    def test_legacy_provenance_is_minimal_exact_and_read_only(self) -> None:
        legacy = self.source["legacy_overlap_provenance"]
        self.assertEqual(legacy["source_commit"], "9501b16a5c4db27f06fa0d0b252a3a75f633967f")
        self.assertEqual(legacy["source_tree"], "60917f0b61ec1e6a195b9a648faa6466406aeda1")
        self.assertEqual(legacy["accessed_columns"], ["caseid"])
        self.assertEqual(legacy["total_rows"], 98)
        self.assertEqual(legacy["unique_caseids"], 98)
        self.assertFalse(legacy["split_labels_copied_to_new_cohort"])
        self.assertFalse(legacy["results_or_metrics_accessed"])
        self.assertFalse(legacy["first_100_recomputed"])
        self.assertTrue(self.source["legacy_read_only_unchanged"])
        self.assertEqual(self.source["legacy_read_only_state_before"], self.source["legacy_read_only_state_after"])

    def test_preflight_is_fixed_random_25_and_passes_both_gates(self) -> None:
        selected = self.preflight["selected_caseids"]
        included = sorted(int(row["caseid"]) for row in self.cohort if row["included_for_primary_signal_acquisition"] == "true")
        self.assertEqual(len(selected), 25)
        self.assertEqual(len(set(selected)), 25)
        self.assertNotEqual(selected, included[:25])
        self.assertEqual(self.preflight["sample_status_counts"], {"complete": 100})
        self.assertTrue(self.preflight["disk_gate_passed"])
        self.assertTrue(self.preflight["operational_gate_passed"])
        self.assertGreaterEqual(self.preflight["disk_free_bytes"], self.preflight["required_two_x_estimated_bytes"])

    def test_download_matrix_is_complete_exact_and_sqi_is_qc_only(self) -> None:
        self.assertEqual(len(self.downloads), 2470 * 4)
        keys = {(int(row["caseid"]), row["track_name"]) for row in self.downloads}
        self.assertEqual(len(keys), len(self.downloads))
        self.assertEqual({row["track_name"] for row in self.downloads}, TRACKS)
        included = {int(row["caseid"]) for row in self.cohort if row["included_for_primary_signal_acquisition"] == "true"}
        self.assertEqual({int(row["caseid"]) for row in self.downloads}, included)
        self.assertTrue(all(row["download_status"] == "complete" for row in self.downloads))
        sqi = [row for row in self.downloads if row["track_name"] == "BIS/SQI"]
        self.assertTrue(all(row["track_role"] == "qc_only" for row in sqi))
        self.assertTrue(all(row["prediction_feature_allowed"] == "false" for row in sqi))
        self.assertTrue(all(row["ppo_state_allowed"] == "false" for row in sqi))
        self.assertTrue(all(row["signal_quality_exclusion_applied"] == "false" for row in self.downloads))

    def test_every_raw_signal_checksum_matches_and_no_partial_exists(self) -> None:
        self.assertEqual(len(self.checksums), 9880)
        manifest = {(row["caseid"], row["track_name"]): row for row in self.downloads}
        total_bytes = 0
        for checksum_row in self.checksums:
            row = manifest[(checksum_row["caseid"], checksum_row["track_name"])]
            path = RAW_ROOT / checksum_row["raw_relative_path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, int(checksum_row["raw_byte_count"]))
            self.assertEqual(sha256(path), checksum_row["raw_sha256"])
            self.assertEqual(row["raw_sha256"], checksum_row["raw_sha256"])
            total_bytes += path.stat().st_size
        self.assertEqual(total_bytes, self.summary["checksum_verified_raw_bytes"])
        self.assertEqual(list(RAW_ROOT.rglob("*.part")), [])

    def test_raw_is_not_tracked_and_scope_has_no_downstream_execution(self) -> None:
        tracked = subprocess.check_output(["git", "ls-files", "data/raw"], cwd=ROOT, text=True).splitlines()
        self.assertEqual(tracked, [])
        self.assertEqual(set(self.source["allowed_exact_tracks"]), TRACKS)
        self.assertEqual(self.source["bis_sqi_role"], "qc_only_prohibited_prediction_feature_and_ppo_state")
        self.assertFalse(self.source["rftn20_rftn50_merged"])
        self.assertFalse(self.source["rftn50_used"])
        self.assertTrue(all(value is False for value in self.source["prohibited_execution"].values()))

    def test_published_artifact_checksums_match(self) -> None:
        inventory = json.loads((MANIFESTS / "primary_signal_artifact_checksums.json").read_text(encoding="utf-8"))
        for relative, expected in inventory.items():
            self.assertEqual(sha256(ROOT / relative), expected, relative)


if __name__ == "__main__":
    unittest.main()

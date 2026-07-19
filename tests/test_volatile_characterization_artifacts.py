from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.volatile_characterization import (  # noqa: E402
    ALLOWED_TRACK_NAMES,
    EXPECTED_UNIVERSE_COUNT,
    PHASE5C_SEED,
    VOLATILE_TRACKS,
    assert_no_partials,
    sha256_path,
)
from vitaldb_state_selection.cohort.track_inventory import AliasRegistry  # noqa: E402
from vitaldb_state_selection.provenance.manifests import (  # noqa: E402
    load_schema,
    read_csv_manifest,
)


MANIFEST_DIR = ROOT / "data" / "manifests"
RAW_ROOT = ROOT / "data" / "raw" / "phase5c_volatile_signals"
CASE_PATH = MANIFEST_DIR / "volatile_signal_case_manifest.csv"
TRACK_PATH = MANIFEST_DIR / "volatile_signal_track_manifest.csv"
SUMMARY_PATH = MANIFEST_DIR / "volatile_signal_characterization_summary.json"
PREFLIGHT_PATH = MANIFEST_DIR / "volatile_signal_preflight_summary.json"
SNAPSHOT_PATH = MANIFEST_DIR / "volatile_signal_source_snapshot.json"
FAILURE_PATH = MANIFEST_DIR / "volatile_signal_failures.jsonl"
CHECKSUM_PATH = MANIFEST_DIR / "volatile_signal_artifact_checksums.json"
REPORT_PATH = ROOT / "docs" / "volatile_signal_decision_support_report.md"


def _bool(value: str) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "":
        return None
    raise AssertionError(f"invalid boolean value {value!r}")


class VolatileCharacterizationArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with CASE_PATH.open(encoding="utf-8", newline="") as stream:
            cls.cases = list(csv.DictReader(stream))
        with TRACK_PATH.open(encoding="utf-8", newline="") as stream:
            cls.tracks = list(csv.DictReader(stream))
        cls.summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        cls.preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
        cls.snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        cls.failures = [
            json.loads(line)
            for line in FAILURE_PATH.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_analysis_universe_recomputes_to_exactly_3219_without_freeze(self) -> None:
        schema = load_schema(ROOT / "schemas" / "eligibility_manifest.schema.json")
        manifest = read_csv_manifest(
            MANIFEST_DIR / "all_case_eligibility_manifest.csv", schema
        )
        expected = [
            int(row["caseid"])
            for row in manifest
            if all(
                row[f"{concept}_track_available"] is True
                for concept in ("bis", "propofol_rate", "remifentanil_rate")
            )
            and row["adult_candidate"] is True
            and row["anesthesia_type"] == "General"
        ]
        actual = [int(row["caseid"]) for row in self.cases]
        self.assertEqual(len(actual), EXPECTED_UNIVERSE_COUNT)
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), len(set(actual)))
        self.assertTrue(all(row["analysis_universe_frozen"] == "false" for row in self.cases))
        self.assertTrue(
            all(row["volatile_exposure_decision"] == "pending_human_review" for row in self.cases)
        )
        self.assertTrue(all(row["tiva_decision"] == "pending_human_review" for row in self.cases))
        self.assertTrue(all(row["legacy_overlap"] == "pending_not_evaluated" for row in self.cases))

    def test_case_track_matrix_is_complete_exact_and_failure_explicit(self) -> None:
        self.assertEqual(len(self.tracks), EXPECTED_UNIVERSE_COUNT * 7)
        by_case: dict[int, list[dict[str, str]]] = defaultdict(list)
        for row in self.tracks:
            by_case[int(row["caseid"])].append(row)
        self.assertEqual(set(by_case), {int(row["caseid"]) for row in self.cases})
        for caseid, rows in by_case.items():
            self.assertEqual(len(rows), 7, caseid)
            self.assertEqual({row["track_name"] for row in rows}, set(ALLOWED_TRACK_NAMES))
        statuses = Counter(row["download_status"] for row in self.tracks)
        self.assertEqual(statuses["complete"], 9059)
        self.assertEqual(statuses["track_absent"], len(self.tracks) - 9059)
        self.assertEqual(set(statuses), {"complete", "track_absent"})
        self.assertEqual(self.failures, [])
        self.assertTrue(all(row["unit_review_status"] == "pending_human_review" for row in self.tracks))

    def test_preflight_is_fixed_seed_stratified_and_passes_two_x_disk_gate(self) -> None:
        self.assertEqual(self.preflight["seed"], PHASE5C_SEED)
        self.assertEqual(self.preflight["universe_case_count"], EXPECTED_UNIVERSE_COUNT)
        self.assertEqual(self.preflight["presence_stratum_count"], 10)
        self.assertEqual(self.preflight["sample_case_count"], 20)
        self.assertEqual(len(set(self.preflight["sample_caseids"])), 20)
        self.assertEqual(self.preflight["request_status_counts"], {"complete": 68})
        self.assertEqual(self.preflight["failure_type_counts"], {})
        self.assertTrue(self.preflight["operational_gate_passed"])
        self.assertTrue(self.preflight["disk_gate_passed"])
        self.assertGreaterEqual(
            self.preflight["disk_free_bytes"],
            2 * self.preflight["estimated_full_required_bytes"],
        )
        self.assertTrue(self.preflight["full_download_authorized_by_gate"])

    def test_every_downloaded_raw_file_matches_manifest_checksum_and_no_partials_remain(self) -> None:
        downloaded = [row for row in self.tracks if row["download_status"] == "complete"]
        self.assertEqual(len(downloaded), 9059)
        for row in downloaded:
            path = RAW_ROOT / row["raw_relative_path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, int(row["raw_byte_count"]), path)
            self.assertEqual(sha256_path(path), row["raw_sha256"], path)
        assert_no_partials(RAW_ROOT)

    def test_raw_signals_are_not_tracked_by_git(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "--", "data/raw"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "")

    def test_summary_recomputes_track_and_candidate_definition_counts(self) -> None:
        by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in self.tracks:
            by_name[row["track_name"]].append(row)
        for spec in VOLATILE_TRACKS:
            rows = by_name[spec.track_name]
            item = self.summary["track_summaries"][spec.track_name]
            self.assertEqual(item["case_count"], EXPECTED_UNIVERSE_COUNT)
            self.assertEqual(
                item["present_case_count"],
                sum(_bool(row["track_present"]) is True for row in rows),
            )
            self.assertEqual(
                item["anesthesia_window_positive_case_count"],
                sum(_bool(row["anesthesia_window_positive_observed"]) is True for row in rows),
            )
        scenarios = {
            row["definition"]: row["descriptive_case_count"]
            for row in self.summary["possible_exposure_definition_counts"]
        }
        self.assertEqual(
            scenarios["any_allowed_track_positive_in_anesthesia_window"],
            sum(row["any_positive_observed_in_anesthesia_window"] == "true" for row in self.cases),
        )
        self.assertIsNone(self.summary["selected_exposure_definition"])
        self.assertFalse(self.summary["analysis_universe"]["cohort_frozen"])
        self.assertTrue(self.summary["processing"]["original_timestamps_used"])
        for field in (
            "resampling",
            "interpolation",
            "smoothing",
            "clipping",
            "abnormal_values_deleted",
        ):
            self.assertFalse(self.summary["processing"][field])

    def test_source_scope_contains_only_allowed_raw_tracks_and_no_downstream_work(self) -> None:
        self.assertEqual(self.snapshot["stage"], "full")
        self.assertEqual(
            self.snapshot["audit_code_base_commit"],
            "a3e9d081ef9f835c3e01d797ed9f4dedbf80d885",
        )
        self.assertEqual(
            set(self.snapshot["scope"]["allowed_exact_track_names"]),
            set(ALLOWED_TRACK_NAMES),
        )
        self.assertEqual(self.snapshot["scope"]["raw_track_request_count"], 9059)
        self.assertEqual(self.snapshot["scope"]["other_raw_track_requests"], 0)
        self.assertFalse(self.snapshot["scope"]["legacy_98_ids_accessed"])
        self.assertFalse(self.snapshot["scope"]["legacy_overlap_evaluated"])
        self.assertTrue(
            all(value is False for value in self.snapshot["prohibited_execution"].values())
        )
        phase5b = json.loads(
            (MANIFEST_DIR / "eligibility_decision_support_source_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            self.snapshot["track_list_endpoint"]["sha256"],
            phase5b["endpoint"]["sha256"],
        )
        self.assertTrue(self.snapshot["track_list_endpoint"]["matches_phase5b_snapshot"])
        registry = AliasRegistry.from_yaml(ROOT / "configs" / "track_aliases.yaml")
        self.assertTrue(all(value == "pending_human_review" for value in registry.unit_status.values()))

    def test_report_and_all_tracked_artifact_checksums_match(self) -> None:
        report = REPORT_PATH.read_text(encoding="utf-8")
        self.assertIn("Track presence is not", report)
        self.assertIn("not a finalized TIVA", report)
        self.assertIn("No exposure definition or cutoff was selected", report)
        for section in (
            "## Track-level distributions of case summaries",
            "## Exact track-presence combinations",
            "## Primus agent-specific, GAS2, and MAC positive-recording combinations",
            "## Fixed-seed boundary samples",
            "## Possible exposure definitions — descriptive comparison only",
        ):
            self.assertIn(section, report)
        inventory = json.loads(CHECKSUM_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            set(inventory),
            {
                "data/manifests/volatile_signal_preflight_summary.json",
                "docs/volatile_signal_preflight_report.md",
                "data/manifests/volatile_signal_case_manifest.csv",
                "data/manifests/volatile_signal_track_manifest.csv",
                "data/manifests/volatile_signal_characterization_summary.json",
                "data/manifests/volatile_signal_source_snapshot.json",
                "data/manifests/volatile_signal_failures.jsonl",
                "docs/volatile_signal_decision_support_report.md",
            },
        )
        for relative, expected in inventory.items():
            actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)


if __name__ == "__main__":
    unittest.main()

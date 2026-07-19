from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.volatile_characterization import (  # noqa: E402
    ALLOWED_TRACK_NAMES,
    PHASE5C_SEED,
    ProgressLog,
    VolatileTask,
    assert_no_partials,
    download_one_task,
    load_verified_metadata,
    parse_numeric_track,
    remove_stale_partials,
    stratified_preflight_caseids,
    task_paths,
)


class FakeClient:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0

    def fetch_track(self, tid: str):
        self.calls += 1
        return self.payload, {
            "url": f"https://api.vitaldb.net/{tid}",
            "elapsed_seconds": 0.01,
            "byte_count": len(self.payload),
            "sha256": "source-response-sha",
        }


class VolatileCharacterizationTests(unittest.TestCase):
    def test_allowed_signal_scope_is_exactly_the_seven_requested_tracks(self) -> None:
        self.assertEqual(
            set(ALLOWED_TRACK_NAMES),
            {
                "Primus/EXP_SEVO",
                "Primus/INSP_SEVO",
                "Primus/EXP_DES",
                "Primus/INSP_DES",
                "Solar8000/GAS2_EXPIRED",
                "Solar8000/GAS2_INSPIRED",
                "Primus/MAC",
            },
        )
        self.assertNotIn("BIS/BIS", ALLOWED_TRACK_NAMES)
        self.assertFalse(any("PPF" in name or "RFTN" in name for name in ALLOWED_TRACK_NAMES))

    def test_parser_uses_original_rows_without_resampling_or_clipping(self) -> None:
        payload = (
            "Time,Primus/EXP_SEVO\n"
            "0,0\n"
            "7,0.5\n"
            "14,2.0\n"
            "21,\n"
            "28,-1.0\n"
            "35,3.0\n"
            "42,4.0\n"
        ).encode("utf-8")
        summary = parse_numeric_track(
            payload,
            expected_track_name="Primus/EXP_SEVO",
            anesthesia_start=10,
            anesthesia_end=35,
        )
        self.assertEqual(summary["sample_count"], 7)
        self.assertEqual(summary["non_missing_sample_count"], 6)
        self.assertEqual(summary["minimum"], -1.0)
        self.assertEqual(summary["maximum"], 4.0)
        self.assertEqual(summary["value_equal_zero_count"], 1)
        self.assertEqual(summary["value_positive_count"], 4)
        self.assertEqual(summary["anesthesia_window_sample_count"], 4)
        self.assertTrue(summary["anesthesia_window_positive_observed"])
        self.assertEqual(summary["positive_run_count"], 2)
        self.assertEqual(summary["longest_positive_run_seconds"], 7.0)
        self.assertIn("negative_value", summary["warning_flags"])
        self.assertEqual(
            summary["processing"],
            {
                "resampling": False,
                "interpolation": False,
                "smoothing": False,
                "clipping": False,
                "quantile_method": "nearest_rank_observed_values",
            },
        )

    def test_preflight_sample_is_fixed_seed_and_represents_every_stratum(self) -> None:
        fields = (
            "primus_exp_sevo_present",
            "primus_insp_sevo_present",
            "primus_exp_des_present",
            "primus_insp_des_present",
            "solar8000_gas2_expired_present",
            "solar8000_gas2_inspired_present",
            "primus_mac_present",
        )
        universe = []
        for caseid in range(1, 13):
            group = caseid % 3
            row = {"caseid": caseid}
            for index, field in enumerate(fields):
                row[field] = index == group
            universe.append(row)
        first = stratified_preflight_caseids(universe, seed=PHASE5C_SEED)
        second = stratified_preflight_caseids(universe, seed=PHASE5C_SEED)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertNotEqual(first, list(range(1, 7)))

    def test_download_is_atomic_checksum_verified_and_resumable(self) -> None:
        payload = b"Time,Primus/MAC\n0,0\n7,1\n"
        task = VolatileTask(1, "Primus/MAC", ("tid-1",), 0.0, 10.0, "combo")
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory)
            progress = ProgressLog(raw_root / "download_attempts.jsonl")
            client = FakeClient(payload)
            first = download_one_task(
                task,
                raw_root=raw_root,
                client=client,
                progress=progress,
                source_version="test-source",
            )
            self.assertEqual(first["status"], "complete")
            self.assertEqual(client.calls, 1)
            second = download_one_task(
                task,
                raw_root=raw_root,
                client=client,
                progress=progress,
                source_version="test-source",
            )
            self.assertEqual(second["raw_sha256"], first["raw_sha256"])
            self.assertEqual(client.calls, 1)
            signal_path, _ = task_paths(raw_root, task)
            signal_path.write_bytes(b"corrupt")
            repaired = download_one_task(
                task,
                raw_root=raw_root,
                client=client,
                progress=progress,
                source_version="test-source",
            )
            self.assertEqual(repaired["status"], "complete")
            self.assertEqual(client.calls, 2)
            self.assertIsNotNone(load_verified_metadata(raw_root, task))
            self.assertEqual(list(raw_root.rglob("*.part")), [])

    def test_stale_partial_cleanup_is_scoped_to_raw_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory) / "raw"
            partial = raw_root / "cases" / "1" / ".signal.part"
            partial.parent.mkdir(parents=True)
            partial.write_bytes(b"partial")
            removed = remove_stale_partials(raw_root)
            self.assertEqual(removed, ["cases/1/.signal.part"])
            assert_no_partials(raw_root)


if __name__ == "__main__":
    unittest.main()

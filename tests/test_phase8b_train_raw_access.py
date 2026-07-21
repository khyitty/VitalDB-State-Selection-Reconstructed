from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.train_raw_access import (  # noqa: E402
    ALLOWED_TRACKS,
    TrainRawAccessError,
    TrainRawAccessGuard,
)


class Phase8BTrainRawAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guard = TrainRawAccessGuard(ROOT)
        cls.train_case = next(key for key, value in cls.guard.split_guard.case_split.items() if value == "train")
        cls.test_case = next(key for key, value in cls.guard.split_guard.case_split.items() if value == "test")

    def test_exact_train_tracks_resolve(self) -> None:
        for track in ALLOWED_TRACKS:
            path = self.guard.resolve_train_track(self.train_case, track)
            self.assertTrue(path.is_file())
            self.assertEqual(path.suffix, ".signal")

    def test_test_and_drug_requests_fail_before_hash_or_parser(self) -> None:
        requests = (
            (self.test_case, "BIS/BIS"), (self.test_case, "BIS/SQI"),
            (self.train_case, "Orchestra/PPF20_RATE"),
            (self.test_case, "Orchestra/RFTN20_RATE"),
        )
        for caseid, track in requests:
            with self.subTest(caseid=caseid, track=track), \
                 patch("vitaldb_state_selection.cohort.train_raw_access.sha256_path") as hasher, \
                 patch("vitaldb_state_selection.cohort.train_raw_access.parse_observation_index") as parser:
                with self.assertRaises(TrainRawAccessError):
                    self.guard.parse_train_track(caseid, track, 0, 1)
                hasher.assert_not_called()
                parser.assert_not_called()

    def test_unknown_and_mixed_requests_are_rejected(self) -> None:
        for caseid in ("999999999", [self.train_case, self.test_case]):
            if isinstance(caseid, list):
                with self.assertRaises(Exception):
                    self.guard.split_guard.assert_train_cases(caseid)
            else:
                with self.assertRaises(TrainRawAccessError):
                    self.guard.resolve_train_track(caseid, "BIS/BIS")

    def test_path_traversal_and_unlisted_source_are_rejected(self) -> None:
        guard = TrainRawAccessGuard(ROOT)
        key = (self.train_case, "BIS/BIS")
        original = guard._download[key]
        guard._download[key] = {**original, "raw_relative_path": "../escape.signal"}
        with self.assertRaises(TrainRawAccessError):
            guard.resolve_train_track(*key)
        guard._download.pop(key)
        with self.assertRaises(TrainRawAccessError):
            guard.resolve_train_track(*key)

    def test_checksum_mismatch_is_rejected(self) -> None:
        guard = TrainRawAccessGuard(ROOT)
        with patch("vitaldb_state_selection.cohort.train_raw_access.sha256_path", return_value="0" * 64):
            with self.assertRaises(TrainRawAccessError):
                guard.verify_train_track_checksum(self.train_case, "BIS/BIS")
        self.assertEqual(guard.logical_accesses, [])

    def test_source_has_no_network_api_or_forbidden_raw_track_path(self) -> None:
        source = (ROOT / "src/vitaldb_state_selection/cohort/train_raw_access.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse({"requests", "urllib", "httpx", "vitaldb"} & {name.split(".")[0] for name in modules})


if __name__ == "__main__":
    unittest.main()

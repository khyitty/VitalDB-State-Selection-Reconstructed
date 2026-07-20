from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.split_guard import SplitGuard, SplitGuardError  # noqa: E402


INVENTORY = ROOT / "data" / "manifests" / "phase8a_artifact_checksums.json"


@unittest.skipUnless(INVENTORY.is_file(), "official Phase 8A artifacts not generated yet")
class SplitGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guard = SplitGuard.from_repository(ROOT)
        cls.train_subject = next(key for key, value in cls.guard.subject_split.items() if value == "train")
        cls.test_subject = next(key for key, value in cls.guard.subject_split.items() if value == "test")
        cls.train_case = next(key for key, value in cls.guard.case_split.items() if value == "train")
        cls.test_case = next(key for key, value in cls.guard.case_split.items() if value == "test")

    def test_lookup_and_train_only_guards(self) -> None:
        self.assertEqual(self.guard.split_for_subject(self.train_subject), "train")
        self.assertEqual(self.guard.split_for_case(self.train_case), "train")
        self.guard.assert_train_subjects([self.train_subject])
        self.guard.assert_train_cases([self.train_case])
        with self.assertRaises(SplitGuardError):
            self.guard.assert_train_subjects([self.test_subject])
        with self.assertRaises(SplitGuardError):
            self.guard.assert_train_cases([self.test_case])

    def test_test_only_and_mixed_contamination_guards(self) -> None:
        self.guard.assert_test_subjects([self.test_subject])
        self.guard.assert_test_cases([self.test_case])
        with self.assertRaises(SplitGuardError):
            self.guard.assert_test_subjects([self.train_subject])
        with self.assertRaises(SplitGuardError):
            self.guard.assert_test_cases([self.train_case])
        with self.assertRaises(SplitGuardError):
            self.guard.assert_train_subjects([self.train_subject, self.test_subject])
        with self.assertRaises(SplitGuardError):
            self.guard.assert_test_cases([self.train_case, self.test_case])

    def test_unknown_and_duplicate_identifiers_are_rejected(self) -> None:
        with self.assertRaises(SplitGuardError):
            self.guard.split_for_subject("999999999")
        with self.assertRaises(SplitGuardError):
            self.guard.split_for_case("999999999")
        with self.assertRaises(SplitGuardError):
            self.guard.assert_train_subjects([self.train_subject, self.train_subject])
        with self.assertRaises(SplitGuardError):
            self.guard.assert_train_cases([self.train_case, self.train_case])

    def test_subject_case_mixed_request_requires_parent_match(self) -> None:
        parent = self.guard.case_subject[self.train_case]
        self.guard.assert_subject_case_request([parent], [self.train_case], expected_split="train")
        unrelated = next(
            subject for subject, split in self.guard.subject_split.items()
            if split == "train" and subject != parent
        )
        with self.assertRaises(SplitGuardError):
            self.guard.assert_subject_case_request([unrelated], [self.train_case], expected_split="train")

    def _copy_verified_tree(self, destination: Path) -> None:
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        for entry in inventory["artifacts"]:
            source = ROOT / entry["relative_path"]
            target = destination / entry["relative_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        target_inventory = destination / INVENTORY.relative_to(ROOT)
        target_inventory.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(INVENTORY, target_inventory)

    def _tamper_and_reject(self, relative: str, mutate) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._copy_verified_tree(root)
            path = root / relative
            mutate(path)
            with self.assertRaises(SplitGuardError):
                SplitGuard.from_repository(root)

    def test_tampered_subject_case_and_id_manifests_are_rejected(self) -> None:
        def append_newline(path: Path) -> None:
            path.write_bytes(path.read_bytes() + b"\n")

        for relative in (
            "data/manifests/phase8a_subject_split_manifest.csv",
            "data/manifests/phase8a_case_split_manifest.csv",
            "data/manifests/phase8a_train_subject_ids.csv",
        ):
            with self.subTest(relative=relative):
                self._tamper_and_reject(relative, append_newline)

    def test_tampered_seal_wrong_commit_and_wrong_version_are_rejected(self) -> None:
        def change_seal(field: str, value: object):
            def mutate(path: Path) -> None:
                data = json.loads(path.read_text(encoding="utf-8"))
                data[field] = value
                path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return mutate

        for field, value in (
            ("seal_payload_sha256", "0" * 64),
            ("source_remote_commit_sha", "1" * 40),
            ("split_manifest_version", "wrong-version"),
        ):
            with self.subTest(field=field):
                self._tamper_and_reject("data/manifests/phase8a_test_seal.json", change_seal(field, value))

    def test_case_parent_split_mismatch_is_rejected_even_with_resealed_inventory(self) -> None:
        subject_rows = [{"subjectid": "1", "assigned_split": "train"}]
        case_rows = [{"caseid": "2", "subjectid": "1", "assigned_split": "test"}]
        guard = SplitGuard(subject_rows, case_rows, {})
        with self.assertRaises(SplitGuardError):
            guard.assert_subject_case_request(["1"], ["2"], expected_split="train")


if __name__ == "__main__":
    unittest.main()

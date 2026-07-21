from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.causal_grid_feasibility import ObservationIndex  # noqa: E402
from vitaldb_state_selection.cohort.test_observation_templates import (  # noqa: E402
    TestObservationTemplateStore,
    TestRawAccessGuard,
    TestTemplateError,
    extract_template,
    load_test_cases,
)
from vitaldb_state_selection.cohort.test_runtime_inputs import (  # noqa: E402
    load_test_patient_records,
    verify_train_scalers,
)


def observation(track: str, times, values) -> ObservationIndex:
    return ObservationIndex(
        track_name=track,
        timestamps=tuple(times),
        values=tuple(values),
        duplicated_timestamp=tuple(False for _ in times),
        original_row_count=len(times),
        finite_row_count=len(times),
        duplicate_timestamp_count=0,
        zero_interval_count=0,
        negative_interval_count=0,
    )


class FakeAccess:
    def __init__(self) -> None:
        self.logical_accesses = []
        self.indexes = {
            "BIS/BIS": observation("BIS/BIS", [100.0, 110.0], [50.0, 101.0]),
            "BIS/SQI": observation("BIS/SQI", [100.0, 110.0], [80.0, 40.0]),
        }

    def parse_test_track(self, caseid, track_name, start, end):
        digest = ("a" if track_name == "BIS/BIS" else "b") * 64
        self.logical_accesses.append(SimpleNamespace(observed_source_sha256=digest))
        return self.indexes[track_name]

    def record_verified_resume(self, caseid, track_name, observed):
        self.logical_accesses.append(SimpleNamespace(observed_source_sha256=str(observed)))


class Phase8ETestInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_test_cases(ROOT)

    def test_sealed_test_membership_and_patient_profiles_are_exactly_490(self) -> None:
        records = load_test_patient_records(ROOT)
        self.assertEqual(len(self.cases), 490)
        self.assertEqual(len(records), 490)
        self.assertEqual({row.caseid for row in self.cases}, {row.caseid for row in records})
        template = TestObservationTemplateStore(
            ROOT / "data/processed/phase8e_test_observation_templates_v1",
            ROOT,
        ).load_case(self.cases[0].caseid)
        self.assertEqual(template.source_type, "vitaldb_test")

    def test_train_case_is_refused_before_raw_hash_or_parse(self) -> None:
        guard = TestRawAccessGuard(ROOT)
        train_case = next(caseid for caseid, split in guard.split_guard.case_split.items() if split == "train")
        with patch("vitaldb_state_selection.cohort.test_observation_templates.sha256_path") as hasher, \
             patch("vitaldb_state_selection.cohort.test_observation_templates.parse_observation_index") as parser:
            with self.assertRaises(TestTemplateError):
                guard.parse_test_track(train_case, "BIS/BIS", 0.0, 1.0)
            hasher.assert_not_called()
            parser.assert_not_called()

    def test_template_is_deterministic_and_never_persists_raw_bis(self) -> None:
        case = self.cases[0]
        synthetic_case = type(case)(case.caseid, case.subjectid, 100.0, 200.0, case.source_cohort_protocol_version, case.study_protocol_version, case.split_manifest_version)
        with tempfile.TemporaryDirectory() as directory:
            first = extract_template(synthetic_case, access=FakeAccess(), template_root=Path(directory))
            files_before = {path.name: path.read_bytes() for path in (Path(directory) / first["template_id"]).iterdir()}
            second = extract_template(synthetic_case, access=FakeAccess(), template_root=Path(directory))
            files_after = {path.name: path.read_bytes() for path in (Path(directory) / second["template_id"]).iterdir()}
            self.assertEqual(files_before, files_after)
            self.assertNotIn("bis_value.npy", files_before)
            metadata = json.loads(files_before["metadata.json"])
            self.assertFalse(metadata["raw_bis_values_persisted"])
            self.assertEqual(metadata["assigned_split"], "test")

    def test_train_scalers_are_reused_without_test_fit(self) -> None:
        scalers, checksum = verify_train_scalers(ROOT)
        self.assertEqual(len(scalers["S0"].fields), 34)
        self.assertEqual(len(scalers["S1"].fields), 42)
        self.assertRegex(checksum, r"^[0-9a-f]{64}$")
        payload = json.loads((ROOT / "data/manifests/phase8c_scaler_registry.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["test_case_count_used"], 0)
        self.assertEqual(payload["fit_split"], "train_only")


if __name__ == "__main__":
    unittest.main()

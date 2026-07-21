from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.anesthesia import S0_FIELDS, S1_FIELDS  # noqa: E402
from vitaldb_state_selection.cohort.causal_grid_feasibility import ObservationIndex  # noqa: E402
from vitaldb_state_selection.cohort.train_runtime_inputs import (  # noqa: E402
    PHASE8B_EXPECTED_ROOT_SHA256,
    PRIVATE_ROOT_RELATIVE,
    REMIFENTANIL_TRACK,
    StateScaler,
    TrainRemifentanilAccessGuard,
    TrainRuntimeInputError,
    TrainRuntimeInputStore,
    bundle_id_for_case,
    causal_schedule_arrays,
    convert_rftn20_ml_per_hr_to_microgram_per_min,
    load_scaler_registry,
    load_train_patient_records,
)


PRIVATE = ROOT / PRIVATE_ROOT_RELATIVE
SUMMARY = ROOT / "data/manifests/phase8c_runtime_input_summary.json"
SCALERS = ROOT / "data/manifests/phase8c_scaler_registry.json"


class Phase8CTrainRuntimeInputUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = load_train_patient_records(ROOT)
        cls.guard = TrainRemifentanilAccessGuard(ROOT)
        cls.train_case = next(key for key, split in cls.guard.split_guard.case_split.items() if split == "train")
        cls.test_case = next(key for key, split in cls.guard.split_guard.case_split.items() if split == "test")

    def test_train_patient_profile_accounting_mapping_and_required_values(self) -> None:
        self.assertEqual(len(self.records), 1970)
        self.assertEqual(len({row.caseid for row in self.records}), 1970)
        for row in self.records:
            self.guard.split_guard.assert_subject_case_request([row.subjectid], [row.caseid], expected_split="train")
            self.assertGreaterEqual(row.profile.age_years, 18)
            self.assertGreater(row.profile.height_cm, 0)
            self.assertGreater(row.profile.weight_kg, 0)

    def test_rftn20_unit_conversion_is_exact_and_negative_is_rejected(self) -> None:
        self.assertEqual(convert_rftn20_ml_per_hr_to_microgram_per_min(3.0), 1.0)
        self.assertEqual(convert_rftn20_ml_per_hr_to_microgram_per_min(0.0), 0.0)
        with self.assertRaises(TrainRuntimeInputError):
            convert_rftn20_ml_per_hr_to_microgram_per_min(-0.1)

    def test_causal_schedule_is_ordered_right_continuous_and_future_free(self) -> None:
        source = ObservationIndex(
            REMIFENTANIL_TRACK,
            (105.0, 110.0, 120.0),
            (0.0, 3.0, 3.0),
            (False, False, False),
            3, 3, 0, 0, 0,
        )
        times, rates = causal_schedule_arrays(source, anesthesia_start=100.0, anesthesia_end=130.0)
        np.testing.assert_array_equal(times, np.asarray([0.0, 10.0], dtype="<f8"))
        np.testing.assert_array_equal(rates, np.asarray([0.0, 1.0], dtype="<f8"))
        self.assertTrue(np.all(np.diff(times) > 0))

    def test_test_unknown_and_nonexact_track_fail_before_raw_hash_or_parse(self) -> None:
        requests = ((self.test_case, REMIFENTANIL_TRACK), (self.train_case, "Orchestra/RFTN50_RATE"), ("99999999", REMIFENTANIL_TRACK))
        for caseid, track in requests:
            with self.subTest(caseid=caseid, track=track), \
                 patch("vitaldb_state_selection.cohort.train_runtime_inputs.sha256_path") as hasher, \
                 patch("vitaldb_state_selection.cohort.train_runtime_inputs.parse_observation_index") as parser:
                with self.assertRaises(TrainRuntimeInputError):
                    if track == REMIFENTANIL_TRACK:
                        self.guard.parse_schedule_source(caseid, 0.0, 10.0)
                    else:
                        self.guard._authorize(caseid, track)
                hasher.assert_not_called()
                parser.assert_not_called()

    def test_bundle_identifier_is_deterministic(self) -> None:
        self.assertEqual(bundle_id_for_case(self.train_case), bundle_id_for_case(self.train_case))
        self.assertNotEqual(bundle_id_for_case(self.train_case), bundle_id_for_case(str(int(self.train_case) + 1)))


@unittest.skipUnless(SUMMARY.is_file() and SCALERS.is_file() and PRIVATE.is_dir(), "official Phase 8C private store not generated")
class Phase8CRuntimeArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        cls.scaler_payload = json.loads(SCALERS.read_text(encoding="utf-8"))
        cls.scalers = load_scaler_registry(SCALERS)
        cls.store = TrainRuntimeInputStore(PRIVATE, ROOT)

    def test_private_store_complete_deterministic_and_train_only(self) -> None:
        complete = json.loads((PRIVATE / "STORE_COMPLETE.json").read_text(encoding="utf-8"))
        self.assertEqual(complete["train_bundle_count"], 1970)
        self.assertEqual(complete["test_bundle_count"], 0)
        self.assertEqual(len(self.store.rows), 1970)
        self.assertEqual(self.store.verify_all(), complete["private_runtime_root_sha256"])
        self.assertEqual(self.summary["private_runtime_root_sha256"], complete["private_runtime_root_sha256"])
        self.assertEqual(self.summary["phase8b_private_root_before"], PHASE8B_EXPECTED_ROOT_SHA256)
        self.assertEqual(self.summary["phase8b_private_root_after"], PHASE8B_EXPECTED_ROOT_SHA256)

    def test_access_ledger_is_exactly_one_train_remifentanil_access_per_case(self) -> None:
        import csv
        with (PRIVATE / "access_ledger.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1970)
        self.assertEqual(len({row["caseid"] for row in rows}), 1970)
        self.assertTrue(all(row["assigned_split"] == "train" for row in rows))
        self.assertTrue(all(row["track_name"] == REMIFENTANIL_TRACK for row in rows))
        self.assertTrue(all(row["status"] == "complete" for row in rows))
        self.assertTrue(all(row["expected_source_sha256"] == row["observed_source_sha256"] for row in rows))
        self.assertEqual(self.summary["test_raw_access_count"], 0)

    def test_s0_s1_scalers_are_train_only_and_p_invariant(self) -> None:
        self.assertEqual(self.scaler_payload["fit_case_count"], 1970)
        self.assertEqual(self.scaler_payload["test_case_count_used"], 0)
        self.assertTrue(self.scaler_payload["p0_p1_share_same_scaler_for_each_state"])
        self.assertEqual(len(self.scalers["S0"].fields), 34)
        self.assertEqual(len(self.scalers["S1"].fields), 42)
        self.assertEqual(tuple(field.field_name for field in self.scalers["S0"].fields), S0_FIELDS)
        self.assertEqual(tuple(field.field_name for field in self.scalers["S1"].fields), S1_FIELDS)
        sample0 = np.zeros(34, dtype=np.float64)
        sample1 = np.zeros(42, dtype=np.float64)
        self.assertTrue(np.isfinite(self.scalers["S0"].transform(sample0)).all())
        self.assertTrue(np.isfinite(self.scalers["S1"].transform(sample1)).all())
        for scaler in self.scalers.values():
            for index, field in enumerate(scaler.fields):
                if field.binary_unchanged:
                    sample = np.zeros(len(scaler.fields), dtype=np.float64)
                    sample[index] = 1.0
                    self.assertEqual(scaler.transform(sample)[index], 1.0)

    def test_test_case_runtime_load_is_refused(self) -> None:
        test_case = next(key for key, split in self.store.split_guard.case_split.items() if split == "test")
        with self.assertRaises(TrainRuntimeInputError):
            self.store.load_case(test_case)


if __name__ == "__main__":
    unittest.main()

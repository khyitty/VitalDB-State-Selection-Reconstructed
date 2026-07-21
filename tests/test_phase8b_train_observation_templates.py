from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.cohort.causal_grid_feasibility import ObservationIndex  # noqa: E402
from vitaldb_state_selection.cohort.train_observation_templates import (  # noqa: E402
    PAYLOAD_FILES,
    PHASE8A_SEAL_PAYLOAD_SHA256,
    TEMPLATE_FORMAT_VERSION,
    TrainCase,
    TrainTemplateError,
    extract_template,
    load_train_cases,
    template_id_for_case,
    verify_complete_template,
)


def index(track: str, timestamps, values, duplicates=0) -> ObservationIndex:
    return ObservationIndex(
        track_name=track, timestamps=tuple(timestamps), values=tuple(values),
        duplicated_timestamp=tuple(False for _ in timestamps), original_row_count=len(timestamps),
        finite_row_count=len(timestamps), duplicate_timestamp_count=duplicates,
        zero_interval_count=0, negative_interval_count=0,
    )


class FakeAccess:
    def __init__(self, bis: ObservationIndex, sqi: ObservationIndex):
        self.indexes = {"BIS/BIS": bis, "BIS/SQI": sqi}
        self.logical_accesses = []

    def parse_train_track(self, caseid, track_name, start, end, *, access_purpose):
        digest = ("a" if track_name == "BIS/BIS" else "b") * 64
        self.logical_accesses.append(SimpleNamespace(observed_source_sha256=digest))
        return self.indexes[track_name]


def case() -> TrainCase:
    return TrainCase("1", "1", "100.0", "200.0", 100.0, 200.0, "1.2", "1.3.2", "phase8a-v1")


class Phase8BTrainObservationTemplateTests(unittest.TestCase):
    def test_approved_timing_lineage_is_exact_for_all_train_cases(self) -> None:
        cases = load_train_cases(ROOT)
        self.assertEqual(len(cases), 1970)
        self.assertEqual(len({item.caseid for item in cases}), 1970)
        self.assertTrue(all(math.isfinite(item.anesthesia_start) and item.anesthesia_end > item.anesthesia_start for item in cases))

    def test_template_id_uses_exact_pinned_null_delimited_payload(self) -> None:
        import hashlib
        expected = hashlib.sha256(
            "\0".join((TEMPLATE_FORMAT_VERSION, PHASE8A_SEAL_PAYLOAD_SHA256, "1")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(template_id_for_case("1"), expected)
        self.assertRegex(expected, r"^[0-9a-f]{64}$")

    def test_exact_extraction_semantics_and_no_raw_bis_values(self) -> None:
        bis = index("BIS/BIS", (100.0, 110.0, 120.0, 130.0, 140.0), (0.0, 10.0, 100.0, -1.0, 101.0))
        sqi = index("BIS/SQI", (100.0, 109.999, 110.0, 130.0), (50.0, 99.0, 49.0, 120.0))
        with tempfile.TemporaryDirectory() as directory:
            extracted = extract_template(case(), access=FakeAccess(bis, sqi), template_root=Path(directory))
            metadata = json.loads((extracted.directory / "metadata.json").read_text(encoding="utf-8"))
            bis_t = np.load(extracted.directory / "bis_timestamp_seconds.npy", allow_pickle=False)
            available = np.load(extracted.directory / "bis_available.npy", allow_pickle=False)
            sqi_t = np.load(extracted.directory / "sqi_timestamp_seconds.npy", allow_pickle=False)
            sqi_v = np.load(extracted.directory / "sqi_value.npy", allow_pickle=False)
            np.testing.assert_array_equal(bis_t, [0.0, 10.0, 20.0, 30.0, 40.0])
            np.testing.assert_array_equal(available, [True, True, True, False, False])
            np.testing.assert_array_equal(sqi_t, [0.0, 10.0, 30.0])
            np.testing.assert_array_equal(sqi_v, [50.0, 49.0, 120.0])
            self.assertFalse(np.signbit(bis_t[0]))
            self.assertEqual(metadata["p1_event_acceptance_count"], 1)
            self.assertFalse(metadata["raw_bis_values_persisted"])
            self.assertFalse(any("bis_value" in name for name in PAYLOAD_FILES))
            self.assertIs(metadata["raw_bis_values_persisted"], False)
            self.assertFalse(any(key in metadata for key in ("bis_values", "raw_bis_values", "bis_value_array")))

    def test_fixed_dtypes_fingerprint_resume_and_tamper_rejection(self) -> None:
        bis = index("BIS/BIS", (100.0, 110.0), (50.0, 60.0))
        sqi = index("BIS/SQI", (100.0,), (80.0,))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            access = FakeAccess(bis, sqi)
            first = extract_template(case(), access=access, template_root=root)
            before = {path.name: path.read_bytes() for path in first.directory.iterdir()}
            resumed = extract_template(case(), access=FakeAccess(bis, sqi), template_root=root)
            after = {path.name: path.read_bytes() for path in resumed.directory.iterdir()}
            self.assertEqual(before, after)
            self.assertEqual(first.payload_tree_sha256, resumed.payload_tree_sha256)
            self.assertEqual(np.load(first.directory / "bis_timestamp_seconds.npy", allow_pickle=False).dtype, np.dtype("<f8"))
            self.assertEqual(np.load(first.directory / "bis_available.npy", allow_pickle=False).dtype, np.dtype(np.bool_))
            with (first.directory / "bis_timestamp_seconds.npy").open("ab") as stream:
                stream.write(b"tamper")
            with self.assertRaises(TrainTemplateError):
                verify_complete_template(first.directory)

    def test_collision_count_is_zero_for_production_train_cases(self) -> None:
        identifiers = [template_id_for_case(item.caseid) for item in load_train_cases(ROOT)]
        self.assertEqual(len(identifiers), len(set(identifiers)))


if __name__ == "__main__":
    unittest.main()

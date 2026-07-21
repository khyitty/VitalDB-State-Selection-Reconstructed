from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.anesthesia.recorded_observation import (  # noqa: E402
    RecordedObservationError,
    load_recorded_template,
)
from vitaldb_state_selection.cohort.causal_grid_feasibility import ObservationIndex  # noqa: E402
from vitaldb_state_selection.cohort.split_guard import SplitGuard  # noqa: E402
from vitaldb_state_selection.cohort.train_observation_templates import (  # noqa: E402
    extract_template,
    load_train_cases,
    payload_tree,
    write_json,
)


def observation(track, times, values):
    return ObservationIndex(track, tuple(times), tuple(values), tuple(False for _ in times), len(times), len(times), 0, 0, 0)


class FakeAccess:
    def __init__(self, bis, sqi):
        self.values = {"BIS/BIS": bis, "BIS/SQI": sqi}
        self.logical_accesses = []

    def parse_train_track(self, caseid, track_name, start, end, *, access_purpose):
        self.logical_accesses.append(SimpleNamespace(observed_source_sha256=("c" if track_name == "BIS/BIS" else "d") * 64))
        return self.values[track_name]


class RecordedObservationTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.guard = SplitGuard.from_repository(ROOT)
        cls.case = load_train_cases(ROOT)[0]

    def make_template(self, root: Path):
        start = self.case.anesthesia_start
        bis = observation("BIS/BIS", (start, start + 10, start + 20), (50, 101, 60))
        sqi = observation("BIS/SQI", (start, start + 20), (80, 40))
        return extract_template(self.case, access=FakeAccess(bis, sqi), template_root=root)

    def reseal(self, directory: Path) -> None:
        fingerprint, entries = payload_tree(directory)
        write_json(directory / "COMPLETE.json", {
            "complete": True, "payload_files": entries,
            "template_payload_tree_sha256": fingerprint,
        })

    def test_load_and_runtime_interface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            extracted = self.make_template(Path(directory))
            template = load_recorded_template(extracted.directory, split_guard=self.guard)
            self.assertEqual(template.source_type, "vitaldb_train")
            self.assertEqual(len(template.bis_events), 3)
            self.assertFalse(template.bis_events[1].available)
            self.assertEqual(len(template.bis_between(-1, 10)), 2)
            self.assertEqual(len(template.sqi_between(-1, 10)), 1)
            self.assertEqual(template.sqi_exact(0), 80)
            self.assertIsNone(template.sqi_exact(10))

    def test_missing_complete_and_tampered_array_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            extracted = self.make_template(Path(directory))
            (extracted.directory / "COMPLETE.json").unlink()
            with self.assertRaises(RecordedObservationError):
                load_recorded_template(extracted.directory, split_guard=self.guard)
        with tempfile.TemporaryDirectory() as directory:
            extracted = self.make_template(Path(directory))
            with (extracted.directory / "bis_available.npy").open("ab") as stream:
                stream.write(b"x")
            with self.assertRaises(RecordedObservationError):
                load_recorded_template(extracted.directory, split_guard=self.guard)

    def test_malformed_dtype_and_object_pickle_are_rejected(self) -> None:
        for array in (np.asarray([0, 10, 20], dtype=np.int64), np.asarray([object(), object(), object()], dtype=object)):
            with self.subTest(dtype=str(array.dtype)), tempfile.TemporaryDirectory() as directory:
                extracted = self.make_template(Path(directory))
                with (extracted.directory / "bis_timestamp_seconds.npy").open("wb") as stream:
                    np.save(stream, array)
                self.reseal(extracted.directory)
                with self.assertRaises(RecordedObservationError):
                    load_recorded_template(extracted.directory, split_guard=self.guard)

    def test_unsorted_duplicate_out_of_horizon_and_length_mismatch_rejected(self) -> None:
        mutations = (
            ("bis_timestamp_seconds.npy", np.asarray([0.0, 20.0, 10.0], dtype="<f8")),
            ("bis_timestamp_seconds.npy", np.asarray([0.0, 10.0, 10.0], dtype="<f8")),
            ("bis_timestamp_seconds.npy", np.asarray([0.0, 10.0, self.case.anesthesia_end - self.case.anesthesia_start + 1], dtype="<f8")),
            ("bis_available.npy", np.asarray([True, False], dtype=np.bool_)),
        )
        for filename, array in mutations:
            with self.subTest(filename=filename, values=array.tolist()), tempfile.TemporaryDirectory() as directory:
                extracted = self.make_template(Path(directory))
                with (extracted.directory / filename).open("wb") as stream:
                    np.save(stream, array, allow_pickle=False)
                self.reseal(extracted.directory)
                with self.assertRaises(RecordedObservationError):
                    load_recorded_template(extracted.directory, split_guard=self.guard)

    def test_sqi_outside_bis_set_and_non_train_metadata_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            extracted = self.make_template(Path(directory))
            with (extracted.directory / "sqi_timestamp_seconds.npy").open("wb") as stream:
                np.save(stream, np.asarray([1.0, 20.0], dtype="<f8"), allow_pickle=False)
            self.reseal(extracted.directory)
            with self.assertRaises(RecordedObservationError):
                load_recorded_template(extracted.directory, split_guard=self.guard)
        with tempfile.TemporaryDirectory() as directory:
            extracted = self.make_template(Path(directory))
            metadata_path = extracted.directory / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["assigned_split"] = "test"
            write_json(metadata_path, metadata)
            self.reseal(extracted.directory)
            with self.assertRaises(RecordedObservationError):
                load_recorded_template(extracted.directory, split_guard=self.guard)


if __name__ == "__main__":
    unittest.main()

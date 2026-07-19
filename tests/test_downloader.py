from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.data.downloader import (  # noqa: E402
    DownloadManifestStore,
    DownloadOrchestrator,
    RetryableDownloadError,
    TrackRequest,
)
from vitaldb_state_selection.provenance.manifests import load_schema  # noqa: E402


class FakeClient:
    def __init__(self, failures: dict[str, int] | None = None) -> None:
        self.failures = dict(failures or {})
        self.calls: Counter[str] = Counter()

    def fetch_track(self, tid: str):
        self.calls[tid] += 1
        if self.calls[tid] <= self.failures.get(tid, 0):
            raise RetryableDownloadError(f"transient synthetic failure for {tid}")
        payload = f"time,value\n0,{tid}\n".encode()
        return payload, {"tid": tid, "synthetic": True}


def request(caseid: int, *, missing: str | None = None) -> TrackRequest:
    tracks = {
        "bis": {"tname": "BIS/BIS", "tid": f"bis-{caseid}"},
        "propofol_rate": {"tname": "Orchestra/PPF20_RATE", "tid": f"prop-{caseid}"},
        "remifentanil_rate": {"tname": "Orchestra/RFTN20_RATE", "tid": f"remi-{caseid}"},
    }
    if missing:
        tracks.pop(missing)
    return TrackRequest(caseid=caseid, clinical={"caseid": caseid}, tracks=tracks)


class DownloaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.schema = load_schema(ROOT / "schemas" / "download_manifest.schema.json")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def orchestrator(self, client: FakeClient) -> DownloadOrchestrator:
        store = DownloadManifestStore(self.root / "download_manifest.csv", self.schema)
        return DownloadOrchestrator(
            client=client,
            raw_root=self.root / "raw",
            manifest=store,
            failure_log=self.root / "failures.jsonl",
            source_version="synthetic-v1",
        )

    def test_failure_case_remains_in_manifest(self) -> None:
        client = FakeClient()
        rows = self.orchestrator(client).run(
            [request(1), request(2, missing="remifentanil_rate")]
        )
        self.assertEqual([row["caseid"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["status"], "complete")
        self.assertEqual(rows[1]["status"], "failed")
        self.assertFalse(rows[1]["retryable"])
        failures = [
            json.loads(line)
            for line in (self.root / "failures.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(failures[0]["caseid"], 2)

    def test_retryable_failure_uses_at_most_three_attempts(self) -> None:
        client = FakeClient({"bis-1": 2})
        row = self.orchestrator(client).run([request(1)])[0]
        self.assertEqual(row["status"], "complete")
        self.assertEqual(row["attempt_count"], 3)
        self.assertEqual(client.calls["bis-1"], 3)

    def test_persistent_retryable_failure_remains_explicit_after_three_attempts(self) -> None:
        client = FakeClient({"bis-1": 10})
        row = self.orchestrator(client).run([request(1)])[0]
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["attempt_count"], 3)
        self.assertTrue(row["retryable"])
        self.assertEqual(client.calls["bis-1"], 3)

    def test_completed_checksum_causes_resume_skip(self) -> None:
        first_client = FakeClient()
        first = self.orchestrator(first_client).run([request(1)])[0]
        self.assertEqual(first["status"], "complete")
        second_client = FakeClient()
        second = self.orchestrator(second_client).run([request(1)])[0]
        self.assertEqual(second["status"], "complete")
        self.assertEqual(sum(second_client.calls.values()), 0)

    def test_corrupt_completed_artifact_is_not_silently_skipped(self) -> None:
        self.orchestrator(FakeClient()).run([request(1)])
        (self.root / "raw" / "cases" / "1" / "bis.csv").write_bytes(b"corrupt")
        client = FakeClient()
        row = self.orchestrator(client).run([request(1)])[0]
        self.assertEqual(row["status"], "complete")
        self.assertEqual(row["attempt_count"], 2)
        self.assertEqual(sum(client.calls.values()), 3)

    def test_duplicate_requests_are_rejected_before_download(self) -> None:
        with self.assertRaisesRegex(Exception, "duplicate"):
            self.orchestrator(FakeClient()).run([request(1), request(1)])


if __name__ == "__main__":
    unittest.main()

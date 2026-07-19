"""Failure-explicit, checksum-verified, resumable signal download orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from vitaldb_state_selection.provenance.manifests import (
    read_csv_manifest,
    write_csv_manifest,
)


class RetryableDownloadError(RuntimeError):
    """A transient error that may be retried within the declared budget."""


class NonRetryableDownloadError(RuntimeError):
    """A structural or semantic error that must remain an explicit failure."""


@dataclass(frozen=True)
class TrackRequest:
    caseid: int
    clinical: Mapping[str, object]
    tracks: Mapping[str, Mapping[str, str]]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".part", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


class DownloadManifestStore:
    def __init__(self, path: Path, schema: Mapping[str, object]) -> None:
        self.path = path
        self.schema = schema
        self.rows: dict[int, dict[str, object]] = {}
        if path.exists():
            existing = read_csv_manifest(path, schema)
            caseids = [int(row["caseid"]) for row in existing]
            if len(caseids) != len(set(caseids)):
                raise NonRetryableDownloadError("download manifest contains duplicate caseids")
            self.rows = {int(row["caseid"]): row for row in existing}

    def initialize(self, requests_: Sequence[TrackRequest], source_version: str) -> None:
        caseids = [request.caseid for request in requests_]
        if len(caseids) != len(set(caseids)):
            raise NonRetryableDownloadError("download request contains duplicate caseids")
        requested_set = set(caseids)
        stale = set(self.rows) - requested_set
        if stale:
            raise NonRetryableDownloadError(
                f"download manifest has rows outside current request: {sorted(stale)[:10]}"
            )
        for request in requests_:
            self.rows.setdefault(
                request.caseid,
                {
                    "caseid": request.caseid,
                    "status": "pending",
                    "attempt_count": 0,
                    "started_at": None,
                    "completed_at": None,
                    "tracks_requested": sorted(request.tracks),
                    "tracks_downloaded": [],
                    "bytes_downloaded": 0,
                    "checksums": {},
                    "failure_type": None,
                    "failure_message": None,
                    "retryable": False,
                    "source_version": source_version,
                },
            )
        self.flush()

    def flush(self) -> None:
        write_csv_manifest(
            self.path,
            [self.rows[caseid] for caseid in sorted(self.rows)],
            self.schema,
        )


class DownloadOrchestrator:
    REQUIRED_CONCEPTS = ("bis", "propofol_rate", "remifentanil_rate")

    def __init__(
        self,
        *,
        client: object,
        raw_root: Path,
        manifest: DownloadManifestStore,
        failure_log: Path,
        source_version: str,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self.client = client
        self.raw_root = raw_root
        self.manifest = manifest
        self.failure_log = failure_log
        self.source_version = source_version
        self.max_attempts = max_attempts

    def _case_root(self, caseid: int) -> Path:
        return self.raw_root / "cases" / str(caseid)

    def _complete_and_verified(self, row: Mapping[str, object]) -> bool:
        if row.get("status") != "complete":
            return False
        checksums = row.get("checksums")
        if not isinstance(checksums, dict) or not checksums:
            return False
        case_root = self._case_root(int(row["caseid"]))
        return all(
            (case_root / relative).is_file()
            and sha256_file(case_root / relative) == expected
            for relative, expected in checksums.items()
        )

    def _log_failure(
        self, *, caseid: int, attempt: int, error: BaseException, retryable: bool
    ) -> None:
        self.failure_log.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "caseid": caseid,
            "attempt": attempt,
            "timestamp": datetime.now(UTC).isoformat(),
            "failure_type": type(error).__name__,
            "failure_message": str(error),
            "retryable": retryable,
            "exception_summary": "".join(
                traceback.format_exception_only(error)
            ).strip(),
        }
        with self.failure_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def _validate_request(self, request: TrackRequest) -> None:
        missing = sorted(set(self.REQUIRED_CONCEPTS) - set(request.tracks))
        if missing:
            raise NonRetryableDownloadError(f"required tracks missing: {missing}")
        for concept in self.REQUIRED_CONCEPTS:
            track = request.tracks[concept]
            if not track.get("tid") or not track.get("tname"):
                raise NonRetryableDownloadError(
                    f"case {request.caseid} {concept} track lacks exact tname or tid"
                )

    def _download_case(self, request: TrackRequest) -> tuple[list[str], int, dict[str, str]]:
        self._validate_request(request)
        case_root = self._case_root(request.caseid)
        artifacts: dict[str, bytes] = {
            "clinical.json": _json_bytes(dict(request.clinical)),
            "track_inventory.json": _json_bytes(
                {concept: dict(track) for concept, track in sorted(request.tracks.items())}
            ),
        }
        source_tracks: dict[str, object] = {}
        downloaded: list[str] = []
        for concept in self.REQUIRED_CONCEPTS:
            track = request.tracks[concept]
            payload, metadata = self.client.fetch_track(str(track["tid"]))
            if not payload:
                raise NonRetryableDownloadError(f"empty payload for {concept}")
            suffix = ".csv.gz" if payload.startswith(b"\x1f\x8b") else ".csv"
            relative = f"{concept}{suffix}"
            artifacts[relative] = payload
            source_tracks[concept] = metadata
            downloaded.append(concept)
        artifacts["source_metadata.json"] = _json_bytes(
            {
                "caseid": request.caseid,
                "source_version": self.source_version,
                "downloaded_at": datetime.now(UTC).isoformat(),
                "tracks": source_tracks,
            }
        )
        checksums: dict[str, str] = {}
        for relative, payload in artifacts.items():
            path = case_root / relative
            _atomic_bytes(path, payload)
            checksums[relative] = hashlib.sha256(payload).hexdigest()
        return downloaded, sum(len(payload) for payload in artifacts.values()), checksums

    @staticmethod
    def _retryable(error: BaseException) -> bool:
        return isinstance(error, (RetryableDownloadError, requests.RequestException))

    def run(self, requests_: Sequence[TrackRequest]) -> list[dict[str, object]]:
        ordered = sorted(requests_, key=lambda item: item.caseid)
        self.manifest.initialize(ordered, self.source_version)
        for request in ordered:
            row = self.manifest.rows[request.caseid]
            if self._complete_and_verified(row):
                continue
            if row.get("status") == "failed" and row.get("retryable") is False:
                continue
            if row["status"] == "complete":
                row.update(
                    status="pending",
                    completed_at=None,
                    failure_type="checksum_mismatch",
                    failure_message="completed artifacts failed checksum verification",
                    retryable=True,
                )
                self.manifest.flush()
            while int(row["attempt_count"]) < self.max_attempts:
                row["attempt_count"] = int(row["attempt_count"]) + 1
                row["status"] = "in_progress"
                row["started_at"] = datetime.now(UTC).isoformat()
                row["completed_at"] = None
                row["failure_type"] = None
                row["failure_message"] = None
                row["retryable"] = False
                self.manifest.flush()
                try:
                    downloaded, byte_count, checksums = self._download_case(request)
                except Exception as error:
                    retryable = self._retryable(error)
                    row["status"] = "failed"
                    row["failure_type"] = type(error).__name__
                    row["failure_message"] = str(error)
                    row["retryable"] = retryable
                    row["completed_at"] = datetime.now(UTC).isoformat()
                    self._log_failure(
                        caseid=request.caseid,
                        attempt=int(row["attempt_count"]),
                        error=error,
                        retryable=retryable,
                    )
                    self.manifest.flush()
                    if retryable and int(row["attempt_count"]) < self.max_attempts:
                        continue
                    break
                else:
                    row.update(
                        status="complete",
                        completed_at=datetime.now(UTC).isoformat(),
                        tracks_downloaded=downloaded,
                        bytes_downloaded=byte_count,
                        checksums=checksums,
                        failure_type=None,
                        failure_message=None,
                        retryable=False,
                    )
                    self.manifest.flush()
                    break
        return [self.manifest.rows[caseid] for caseid in sorted(self.manifest.rows)]

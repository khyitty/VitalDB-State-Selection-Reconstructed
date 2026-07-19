"""Minimal client for the official VitalDB Open Dataset Web API."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests


API_BASE = "https://api.vitaldb.net"
API_DOCUMENTATION = "https://vitaldb.net/docs/?documentId=API%2FWeb_API_OpenDataset.md"


@dataclass(frozen=True)
class CsvSnapshot:
    rows: list[dict[str, str]]
    sha256: str
    byte_count: int
    elapsed_seconds: float
    url: str
    fetched_at: str


class VitalDBOpenAPI:
    def __init__(
        self,
        *,
        base_url: str = API_BASE,
        timeout_seconds: float = 120.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent", "VitalDB-State-Selection eligibility-audit/0.1"
        )

    @staticmethod
    def _decompress(payload: bytes) -> bytes:
        return gzip.decompress(payload) if payload.startswith(b"\x1f\x8b") else payload

    def _get_bytes(self, url: str) -> tuple[bytes, float]:
        started = time.perf_counter()
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.content
        elapsed = time.perf_counter() - started
        if not payload:
            raise ValueError(f"empty response from {url}")
        return payload, elapsed

    def fetch_csv(self, endpoint: str) -> CsvSnapshot:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        payload, elapsed = self._get_bytes(url)
        decoded = self._decompress(payload).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(decoded)))
        if not rows:
            raise ValueError(f"CSV endpoint returned no rows: {url}")
        return CsvSnapshot(
            rows=rows,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
            elapsed_seconds=elapsed,
            url=url,
            fetched_at=datetime.now(UTC).isoformat(),
        )

    def fetch_cases(self) -> CsvSnapshot:
        return self.fetch_csv("cases")

    def fetch_tracks(self) -> CsvSnapshot:
        return self.fetch_csv("trks")

    def fetch_track(self, tid: str) -> tuple[bytes, dict[str, Any]]:
        url = f"{self.base_url}/{tid}"
        payload, elapsed = self._get_bytes(url)
        decoded = self._decompress(payload)
        if b"\n" not in decoded:
            raise ValueError(f"track response has no CSV rows: {url}")
        return payload, {
            "url": url,
            "elapsed_seconds": elapsed,
            "byte_count": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "content_encoding": "gzip" if payload.startswith(b"\x1f\x8b") else "identity",
        }

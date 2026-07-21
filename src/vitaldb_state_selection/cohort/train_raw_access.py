"""Train-only, checksum-pinned access to Phase 6A BIS and SQI signals."""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from .causal_grid_feasibility import ObservationIndex, parse_observation_index
from .split_guard import SplitGuard, SplitGuardError


ALLOWED_TRACKS = ("BIS/BIS", "BIS/SQI")
EXPECTED_TRAIN_CASES = 1970
EXPECTED_LOGICAL_ACCESSES = 3940
RAW_ROOT_RELATIVE = Path("data/raw/phase6a_primary_signals")


class TrainRawAccessError(RuntimeError):
    """Raised before any forbidden or unverifiable raw access."""


@dataclass(frozen=True, slots=True)
class LogicalAccess:
    sequence_number: int
    caseid: str
    assigned_split: str
    track_name: str
    expected_source_sha256: str
    observed_source_sha256: str
    access_purpose: str
    status: str


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _caseid(value: object) -> str:
    text = str(value).strip()
    if not text or not text.isdecimal():
        raise TrainRawAccessError("caseid must be an exact decimal identifier")
    return text


class TrainRawAccessGuard:
    """Resolve, hash, and parse only sealed-train BIS/BIS and BIS/SQI files."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.raw_root = (self.root / RAW_ROOT_RELATIVE).resolve()
        self.split_guard = SplitGuard.from_repository(self.root)
        manifests = self.root / "data" / "manifests"
        eligible_rows = _read_csv(manifests / "final_eligible_cohort_manifest.csv")
        self.eligible_caseids = {
            row["caseid"] for row in eligible_rows if row.get("final_eligible") == "true"
        }
        if len(self.eligible_caseids) != 2460:
            raise TrainRawAccessError("frozen eligible cohort accounting mismatch")

        download_rows = _read_csv(manifests / "primary_signal_download_manifest.csv")
        checksum_rows = _read_csv(manifests / "primary_signal_checksum_manifest.csv")
        self._download = self._unique_rows(download_rows, "download")
        self._checksum = self._unique_rows(checksum_rows, "checksum")
        self.logical_accesses: list[LogicalAccess] = []

    @staticmethod
    def _unique_rows(rows: list[dict[str, str]], source: str) -> dict[tuple[str, str], dict[str, str]]:
        result: dict[tuple[str, str], dict[str, str]] = {}
        for row in rows:
            key = (row.get("caseid", ""), row.get("track_name", ""))
            if key in result:
                raise TrainRawAccessError(f"duplicate {source} manifest row: {key}")
            result[key] = row
        return result

    def _authorize(self, caseid: object, track_name: str) -> tuple[str, dict[str, str], dict[str, str]]:
        cid = _caseid(caseid)
        # Membership and track checks deliberately precede all raw-path work.
        try:
            self.split_guard.assert_train_cases([cid])
        except SplitGuardError as error:
            raise TrainRawAccessError(str(error)) from error
        if track_name not in ALLOWED_TRACKS:
            raise TrainRawAccessError(f"track is outside the Phase 8B allowlist: {track_name}")
        if cid not in self.eligible_caseids:
            raise TrainRawAccessError(f"case is absent from the frozen eligible cohort: {cid}")
        key = (cid, track_name)
        try:
            download = self._download[key]
            checksum = self._checksum[key]
        except KeyError as error:
            raise TrainRawAccessError(f"unlisted source for {key}") from error
        if download.get("download_status") != "complete":
            raise TrainRawAccessError(f"source download is not complete: {key}")
        if checksum.get("checksum_verified") != "true":
            raise TrainRawAccessError(f"source checksum is not versioned as verified: {key}")
        fields = ("raw_relative_path", "raw_byte_count", "raw_sha256")
        if any(download.get(field) != checksum.get(field) for field in fields):
            raise TrainRawAccessError(f"download/checksum manifest disagreement: {key}")
        return cid, download, checksum

    def resolve_train_track(self, caseid: object, track_name: str) -> Path:
        _, download, _ = self._authorize(caseid, track_name)
        relative_text = download.get("raw_relative_path", "")
        relative = PurePosixPath(relative_text)
        if (
            not relative_text
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.suffix != ".signal"
        ):
            raise TrainRawAccessError(f"unsafe or unknown raw path: {relative_text!r}")
        candidate = self.raw_root.joinpath(*relative.parts)
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(self.raw_root)
        except ValueError as error:
            raise TrainRawAccessError("raw path or symlink escapes the approved root") from error
        if not resolved.is_file():
            raise TrainRawAccessError("approved raw source is not a regular file")
        return resolved

    def verify_train_track_checksum(self, caseid: object, track_name: str) -> tuple[Path, str]:
        cid, download, checksum = self._authorize(caseid, track_name)
        path = self.resolve_train_track(cid, track_name)
        expected_bytes = int(checksum["raw_byte_count"])
        if path.stat().st_size != expected_bytes:
            raise TrainRawAccessError(f"source byte-count mismatch: {(cid, track_name)}")
        observed = sha256_path(path)
        expected = checksum["raw_sha256"]
        if observed != expected:
            raise TrainRawAccessError(f"source checksum mismatch: {(cid, track_name)}")
        return path, observed

    def parse_train_track(
        self,
        caseid: object,
        track_name: str,
        anesthesia_start: float,
        anesthesia_end: float,
        *,
        access_purpose: str = "phase8b_train_template_extraction",
    ) -> ObservationIndex:
        cid, _, checksum = self._authorize(caseid, track_name)
        start, end = float(anesthesia_start), float(anesthesia_end)
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise TrainRawAccessError("anesthesia window must be finite and positive")
        path, observed = self.verify_train_track_checksum(cid, track_name)
        try:
            index = parse_observation_index(
                path,
                expected_track_name=track_name,
                anesthesia_start=start,
                anesthesia_end=end,
            )
        except Exception:
            self._record(cid, track_name, checksum["raw_sha256"], observed, access_purpose, "parse_failed")
            raise
        self._record(cid, track_name, checksum["raw_sha256"], observed, access_purpose, "complete")
        return index

    def _record(
        self,
        caseid: str,
        track_name: str,
        expected: str,
        observed: str,
        purpose: str,
        status: str,
    ) -> None:
        self.logical_accesses.append(LogicalAccess(
            sequence_number=len(self.logical_accesses) + 1,
            caseid=caseid,
            assigned_split="train",
            track_name=track_name,
            expected_source_sha256=expected,
            observed_source_sha256=observed,
            access_purpose=purpose,
            status=status,
        ))

    def ledger_rows(self) -> list[dict[str, object]]:
        return [asdict(entry) for entry in self.logical_accesses]

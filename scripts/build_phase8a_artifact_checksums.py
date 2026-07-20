"""Build or verify the self-excluded Phase 8A artifact checksum inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "manifests" / "phase8a_artifact_checksums.json"
ARTIFACTS = tuple(sorted(
    (
        "src/vitaldb_state_selection/cohort/subject_split.py",
        "src/vitaldb_state_selection/cohort/split_guard.py",
        "scripts/run_phase8a_subject_split.py",
        "scripts/build_phase8a_artifact_checksums.py",
        "scripts/verify_phase8a_no_first_n_limit.py",
        "tests/test_phase8a_subject_split.py",
        "tests/test_phase8a_artifacts.py",
        "tests/test_split_guard.py",
        "docs/phase8a_split_decision_record.md",
        "docs/phase8a_report.md",
        "data/manifests/phase8a_split_human_decisions.json",
        "data/manifests/phase8a_stratum_allocation.csv",
        "data/manifests/phase8a_subject_split_manifest.csv",
        "data/manifests/phase8a_case_split_manifest.csv",
        "data/manifests/phase8a_train_subject_ids.csv",
        "data/manifests/phase8a_test_subject_ids.csv",
        "data/manifests/phase8a_train_case_ids.csv",
        "data/manifests/phase8a_test_case_ids.csv",
        "data/manifests/phase8a_metadata_balance_table.csv",
        "data/manifests/phase8a_metadata_balance_summary.json",
        "data/manifests/phase8a_test_seal.json",
        "data/manifests/phase8a_source_snapshot.json",
    )
))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 8A artifact checksums")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_inventory() -> dict[str, object]:
    entries = []
    for relative in ARTIFACTS:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing Phase 8A artifact: {relative}")
        entries.append({"relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256_path(path)})
    return {"artifacts": entries, "self_excluded": True}


def payload(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    args = parse_args()
    expected = payload(expected_inventory())
    if args.verify_only:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
            raise RuntimeError("Phase 8A artifact checksum inventory mismatch")
        print(f"Phase 8A artifact checksum inventory verified: {len(ARTIFACTS)} artifacts")
        return 0
    if OUTPUT.exists():
        raise RuntimeError("Phase 8A artifact checksum inventory already exists; generation refused")
    atomic_write(OUTPUT, expected)
    print(f"Phase 8A artifact checksum inventory created: {len(ARTIFACTS)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

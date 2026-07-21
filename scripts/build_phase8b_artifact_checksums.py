"""Build or verify the self-excluded Phase 8B public artifact inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/phase8b_artifact_checksums.json"
ARTIFACTS = tuple(sorted((
    "src/vitaldb_state_selection/cohort/train_raw_access.py",
    "src/vitaldb_state_selection/cohort/train_observation_templates.py",
    "src/vitaldb_state_selection/anesthesia/recorded_observation.py",
    "scripts/run_phase8b_train_template_extraction.py",
    "scripts/build_phase8b_artifact_checksums.py",
    "scripts/verify_phase8b_no_first_n_limit.py",
    "tests/test_phase8b_train_raw_access.py",
    "tests/test_phase8b_train_observation_templates.py",
    "tests/test_recorded_observation_template.py",
    "tests/test_phase8b_artifacts.py",
    "docs/phase8b_train_template_decision_record.md",
    "docs/phase8b_train_template_report.md",
    "data/manifests/phase8b_train_template_human_decisions.json",
    "data/manifests/phase8b_private_template_schema.json",
    "data/manifests/phase8b_private_tree_summary.json",
    "data/manifests/phase8b_template_qc_summary.json",
    "data/manifests/phase8b_access_summary.json",
    "data/manifests/phase8b_source_snapshot.json",
)))


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
            raise RuntimeError(f"missing Phase 8B artifact: {relative}")
        entries.append({"relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256_path(path)})
    return {"artifacts": entries, "self_excluded": True}


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    expected = canonical(expected_inventory())
    if args.verify_only:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
            raise RuntimeError("Phase 8B artifact checksum inventory mismatch")
        print(f"Phase 8B artifact checksum inventory verified: {len(ARTIFACTS)} artifacts")
        return 0
    if OUTPUT.exists():
        raise RuntimeError("Phase 8B artifact checksum inventory already exists; generation refused")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{OUTPUT.name}.", suffix=".tmp", dir=OUTPUT.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(expected); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, OUTPUT)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    print(f"Phase 8B artifact checksum inventory created: {len(ARTIFACTS)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

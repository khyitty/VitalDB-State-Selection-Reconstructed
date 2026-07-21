"""Build or verify the self-excluded Phase 8C public artifact inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/phase8c_artifact_checksums.json"
ARTIFACTS = tuple(sorted((
    "src/vitaldb_state_selection/cohort/train_runtime_inputs.py",
    "src/vitaldb_state_selection/rl_integration/train_runtime.py",
    "scripts/run_phase8c_train_runtime_inputs.py",
    "scripts/verify_phase8c_no_first_n_limit.py",
    "scripts/build_phase8c_artifact_checksums.py",
    "tests/test_phase8c_train_runtime_inputs.py",
    "tests/test_phase8c_rl_integration.py",
    "tests/test_phase8c_artifacts.py",
    "docs/phase8c_train_runtime_input_design.md",
    "docs/phase8c_train_runtime_input_report.md",
    "docs/compliance_matrix.csv",
    "data/manifests/phase8c_runtime_input_summary.json",
    "data/manifests/phase8c_scaler_registry.json",
    "data/manifests/phase8c_smoke_summary.json",
    "data/manifests/phase8c_source_snapshot.json",
    "data/manifests/phase8c_human_decisions.json",
)))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected() -> dict[str, object]:
    entries = []
    for relative in ARTIFACTS:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing Phase 8C artifact: {relative}")
        entries.append({"relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"artifacts": entries, "self_excluded": True}


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    content = canonical(expected())
    if args.verify_only:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != content:
            raise RuntimeError("Phase 8C artifact checksum inventory mismatch")
        print(f"Phase 8C artifact checksum inventory verified: {len(ARTIFACTS)} artifacts")
        return 0
    if OUTPUT.exists():
        raise RuntimeError("Phase 8C artifact checksum inventory already exists; generation refused")
    descriptor, name = tempfile.mkstemp(prefix=f".{OUTPUT.name}.", suffix=".tmp", dir=OUTPUT.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, OUTPUT)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    print(f"Phase 8C artifact checksum inventory created: {len(ARTIFACTS)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build or verify the self-excluded Phase 8D public artifact inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/phase8d_artifact_checksums.json"
ARTIFACTS = tuple(sorted((
    "src/vitaldb_state_selection/rl_integration/final_training.py",
    "scripts/prepare_phase8d_final_training.py",
    "scripts/run_phase8d_final_training.py",
    "scripts/verify_phase8d_no_first_n_limit.py",
    "scripts/build_phase8d_artifact_checksums.py",
    "tests/test_phase8d_training_protocol.py",
    "tests/test_phase8d_final_training.py",
    "docs/phase8d_final_training_protocol.md",
    "docs/phase8d_parallel_training_runbook.md",
    "docs/phase8d_training_infrastructure_report.md",
    "docs/compliance_matrix.csv",
    "data/manifests/phase8d_final_ppo_config.json",
    "data/manifests/phase8d_training_protocol.json",
    "data/manifests/phase8d_shard_definition.json",
    "data/manifests/phase8d_sampling_summary.json",
    "data/manifests/phase8d_preflight_summary.json",
    "data/manifests/phase8d_source_snapshot.json",
)))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected() -> dict[str, object]:
    rows = []
    for relative in ARTIFACTS:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing Phase 8D artifact: {relative}")
        rows.append({"relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"artifacts": rows, "self_excluded": True}


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    content = canonical(expected())
    if args.verify_only:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != content:
            raise RuntimeError("Phase 8D artifact checksum inventory mismatch")
        print(f"Phase 8D artifact checksum inventory verified: {len(ARTIFACTS)} artifacts")
        return 0
    if OUTPUT.exists():
        raise RuntimeError("Phase 8D artifact checksum inventory already exists; generation refused")
    descriptor, name = tempfile.mkstemp(prefix=f".{OUTPUT.name}.", suffix=".partial", dir=OUTPUT.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, OUTPUT)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    print(f"Phase 8D artifact checksum inventory created: {len(ARTIFACTS)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

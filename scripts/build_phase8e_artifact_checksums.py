"""Build or verify the self-excluded Phase 8E public artifact inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/phase8e_artifact_checksums.json"
ARTIFACTS = tuple(sorted((
    "src/vitaldb_state_selection/anesthesia/recorded_observation.py",
    "src/vitaldb_state_selection/cohort/test_observation_templates.py",
    "src/vitaldb_state_selection/cohort/test_runtime_inputs.py",
    "src/vitaldb_state_selection/rl_integration/final_evaluation.py",
    "src/vitaldb_state_selection/statistics/paired_evaluation.py",
    "scripts/run_phase8e_test_inputs.py",
    "scripts/run_phase8e_final_evaluation.py",
    "scripts/prepare_phase8e_evaluation.py",
    "scripts/verify_phase8e_no_first_n_limit.py",
    "scripts/build_phase8e_artifact_checksums.py",
    "tests/test_phase8e_test_inputs.py",
    "tests/test_phase8e_evaluation.py",
    "tests/test_phase8e_artifacts.py",
    "docs/phase8e_sealed_test_input_report.md",
    "docs/phase8e_final_evaluation_protocol.md",
    "docs/phase8e_statistics_plan.md",
    "docs/phase8e_evaluation_runbook.md",
    "docs/compliance_matrix.csv",
    "data/manifests/phase8e_test_input_summary.json",
    "data/manifests/phase8e_source_snapshot.json",
    "data/manifests/phase8e_evaluation_config.json",
    "data/manifests/phase8e_metric_manifest.json",
    "data/manifests/phase8e_statistics_plan.json",
    "data/manifests/phase8e_synthetic_validation.json",
)) )


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
            raise RuntimeError(f"missing Phase 8E artifact: {relative}")
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
            raise RuntimeError("Phase 8E artifact inventory mismatch")
        print(f"Phase 8E artifact inventory verified: {len(ARTIFACTS)} artifacts")
        return 0
    if OUTPUT.exists():
        raise RuntimeError("Phase 8E artifact inventory already exists; generation refused")
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
    print(f"Phase 8E artifact inventory created: {len(ARTIFACTS)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

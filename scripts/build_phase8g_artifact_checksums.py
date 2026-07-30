"""Build or verify the public Phase 8G artifact checksum inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/manifests/phase8g_artifact_checksums.json"
ARTIFACTS = (
    "README.md",
    "data/manifests/phase8g_multiseed_evaluation_config.json",
    "data/manifests/phase8g_multiseed_config.json",
    "data/manifests/phase8g_seed_definition.json",
    "data/manifests/phase8g_shard_definition.json",
    "data/manifests/phase8g_source_snapshot.json",
    "docs/phase8g_multiseed_robustness_protocol.md",
    "docs/phase8g_parallel_training_runbook.md",
    "docs/phase8g_training_infrastructure_report.md",
    "docs/compliance_matrix.csv",
    "docs/superpowers/plans/2026-07-25-phase8g-multiseed.md",
    "docs/superpowers/specs/2026-07-25-phase8g-multiseed-design.md",
    "scripts/build_phase8g_artifact_checksums.py",
    "scripts/freeze_phase8g_multiseed_results.py",
    "scripts/run_phase8e_final_evaluation.py",
    "scripts/run_phase8g_multiseed_training.py",
    "src/vitaldb_state_selection/publication/final_results.py",
    "src/vitaldb_state_selection/rl_integration/final_evaluation.py",
    "src/vitaldb_state_selection/rl_integration/multiseed_training.py",
    "tests/test_phase8e_evaluation.py",
    "tests/test_phase8e_final_results.py",
    "tests/test_phase8f_renderer.py",
    "tests/test_phase8g_multiseed_training.py",
    "tests/test_phase8g_protocol.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload() -> dict[str, object]:
    rows = []
    for relative in ARTIFACTS:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"required Phase 8G artifact is missing: {relative}")
        rows.append(
            {
                "bytes": path.stat().st_size,
                "relative_path": relative,
                "sha256": sha256(path),
            }
        )
    return {"artifacts": rows, "phase": "Phase 8G", "self_excluded": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    expected = payload()
    if args.verify_only:
        if not OUTPUT.is_file():
            raise RuntimeError("Phase 8G checksum inventory is missing")
        observed = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if observed != expected:
            raise RuntimeError("Phase 8G checksum inventory mismatch")
    else:
        OUTPUT.write_text(
            json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps({"artifact_count": len(ARTIFACTS), "verified": args.verify_only}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

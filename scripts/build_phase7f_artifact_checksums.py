"""Build the self-excluding Phase 7F content checksum inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "manifests" / "phase7f_artifact_checksums.json"
ARTIFACTS = (
    "data/manifests/phase7f_stage_i_human_decisions.json",
    "data/manifests/phase7f_pkpd_constant_registry.json",
    "data/manifests/phase7f_pkpd_unit_contract.json",
    "data/manifests/phase7f_pkpd_equation_provenance.csv",
    "data/manifests/phase7f_synthetic_profiles.json",
    "data/manifests/phase7f_f12_sensitivity_config.json",
    "data/manifests/phase7f_source_snapshot.json",
    "data/manifests/phase7f_pkpd_validation_summary.json",
    "docs/phase7f_stage_i_decision_record.md",
    "docs/phase7f_pkpd_scientific_validation_report.md",
    "docs/phase7f_report.md",
    "scripts/run_phase7f_pkpd_validation.py",
    "scripts/build_phase7f_artifact_checksums.py",
    "src/vitaldb_state_selection/pkpd/__init__.py",
    "src/vitaldb_state_selection/pkpd/bis.py",
    "src/vitaldb_state_selection/pkpd/core.py",
    "src/vitaldb_state_selection/pkpd/dynamics.py",
    "src/vitaldb_state_selection/pkpd/errors.py",
    "src/vitaldb_state_selection/pkpd/parameters.py",
    "src/vitaldb_state_selection/pkpd/profiles.py",
    "src/vitaldb_state_selection/pkpd/registry.py",
    "tests/test_governance.py",
    "tests/test_pkpd_parameters.py",
    "tests/test_pkpd_dynamics.py",
    "tests/test_pkpd_core.py",
    "tests/test_phase7f_artifacts.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    rows = []
    for relative_path in ARTIFACTS:
        path = ROOT / relative_path
        rows.append(
            {
                "relative_path": relative_path,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    payload = {"artifacts": rows, "self_excluded": True}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=OUTPUT.parent, delete=False) as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

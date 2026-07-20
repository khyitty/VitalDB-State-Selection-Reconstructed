"""Build the self-excluding Phase 7H content checksum inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "manifests" / "phase7h_artifact_checksums.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    paths = [
        ROOT / ".gitignore",
        ROOT / "requirements/phase7h_rl_direct.txt",
        ROOT / "requirements/phase7h_rl_lock.txt",
        ROOT / "scripts/run_phase7h_validation.py",
        ROOT / "scripts/build_phase7h_artifact_checksums.py",
        ROOT / "tests/test_phase7h_rl_integration.py",
        ROOT / "tests/test_phase7h_smoke.py",
        ROOT / "tests/test_phase7h_artifacts.py",
        *sorted((ROOT / "src/vitaldb_state_selection/rl_integration").glob("*.py")),
        *sorted((ROOT / "docs").glob("phase7h_*.md")),
        *sorted((ROOT / "data/manifests").glob("phase7h_*.json")),
    ]
    paths = [path for path in paths if path != OUT]
    payload = {
        "artifacts": [
            {"relative_path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in paths
        ],
        "self_excluded": True,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""Read-only Phase 7C probe for legacy PPO/simulator reuse evidence.

The probe never imports or reads VitalDB data.  Its only execution is a single
synthetic simulator reset/advance and import checks for the existing environment
and PPO modules.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


INSPECTED_FILES = (
    "requirements.txt",
    "scripts/run_ppo_smoke.py",
    "src/pkpd/simulator.py",
    "src/pkpd/parameters.py",
    "src/pkpd/compartment.py",
    "src/pkpd/bis_response.py",
    "src/rl_env/environment.py",
    "src/rl_env/reward.py",
    "src/rl_env/action.py",
    "src/rl_env/state_adapters.py",
    "src/rl_env/config.py",
    "src/rl_training/training.py",
    "src/rl_training/evaluation.py",
    "src/rl_training/smoke.py",
    "src/rl_training/config.py",
)

PHASE_ARTIFACTS = (
    "data/manifests/phase7c_component_reuse_audit.csv",
    "data/manifests/phase7c_missing_encoding_options.csv",
    "data/manifests/phase7c_source_snapshot.json",
    "data/manifests/phase7c_state_feasibility.csv",
    "docs/phase7c_drug_rate_semantics_report.md",
    "docs/phase7c_excluded_scope_changes.md",
    "docs/phase7c_implementation_path_comparison.md",
    "docs/phase7c_lab_code_request_checklist.md",
    "docs/phase7c_minimal_implementation_roadmap.md",
    "docs/phase7c_observation_quality_minimum_plan.md",
    "docs/phase7c_ppo_simulator_reuse_audit.md",
    "scripts/audit_phase7c_reuse.py",
    "tests/test_phase7c_reuse_audit.py",
)


def _run(arguments: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _git(legacy_root: Path, *arguments: str) -> str:
    result = _run(
        ["git", "-c", f"safe.directory={legacy_root.as_posix()}", *arguments],
        cwd=legacy_root,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(legacy_root: Path) -> dict[str, object]:
    legacy_root = legacy_root.resolve()
    missing = [name for name in INSPECTED_FILES if not (legacy_root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing legacy audit sources: {missing}")
    dependencies = {
        name: importlib.util.find_spec(name) is not None
        for name in ("numpy", "scipy", "torch", "gymnasium", "stable_baselines3")
    }
    simulator_code = (
        "from src.pkpd.simulator import PKPDSimulator; "
        "from src.pkpd.demographics import PatientDemographics; "
        "p=PatientDemographics(age_years=40,sex='male',height_cm=175,weight_kg=70); "
        "s=PKPDSimulator(); a=s.reset(p,42); "
        "b=s.advance(propofol_rate_mg_per_min=1.0,"
        "remifentanil_rate_micrograms_per_min=0.1,duration_seconds=10); "
        "print(a.time_seconds,b.time_seconds,b.observed_bis)"
    )
    simulator = _run([sys.executable, "-c", simulator_code], cwd=legacy_root)
    environment = _run(
        [sys.executable, "-c", "from src.rl_env import PropofolControlEnv"],
        cwd=legacy_root,
    )
    ppo = _run(
        [sys.executable, "-c", "from src.rl_training.training import create_ppo"],
        cwd=legacy_root,
    )
    return {
        "phase": "7C_reuse_audit",
        "execution_scope": "read_only_imports_and_one_synthetic_simulator_step",
        "legacy_repository": {
            "relative_path": "../VitalDB-Feature-Selection",
            "commit_sha": _git(legacy_root, "rev-parse", "HEAD"),
            "tree_sha": _git(legacy_root, "rev-parse", "HEAD^{tree}"),
            "status_porcelain": _git(legacy_root, "status", "--short").splitlines(),
        },
        "dependency_available": dependencies,
        "probes": {
            "simulator_reset_and_one_step": {
                "returncode": simulator.returncode,
                "stdout": simulator.stdout.strip(),
                "stderr_last_line": simulator.stderr.strip().splitlines()[-1:] or [],
            },
            "environment_import": {
                "returncode": environment.returncode,
                "stderr_last_line": environment.stderr.strip().splitlines()[-1:] or [],
            },
            "ppo_import": {
                "returncode": ppo.returncode,
                "stderr_last_line": ppo.stderr.strip().splitlines()[-1:] or [],
            },
        },
        "inspected_sources": [
            {
                "path": name,
                "sha256": _sha256(legacy_root / name),
                "bytes": (legacy_root / name).stat().st_size,
            }
            for name in INSPECTED_FILES
        ],
        "raw_vitaldb_accessed": False,
        "checkpoint_created": False,
        "ppo_training_run": False,
    }


def artifact_checksums(repository_root: Path) -> dict[str, object]:
    rows = []
    for relative in PHASE_ARTIFACTS:
        path = repository_root / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        rows.append({"path": relative, "sha256": _sha256(path), "bytes": path.stat().st_size})
    return {
        "phase": "7C_reuse_audit",
        "artifact_count": len(rows),
        "artifacts": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "VitalDB-Feature-Selection",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checksum-output", type=Path)
    arguments = parser.parse_args()
    result = probe(arguments.legacy_root)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload, encoding="utf-8")
    if arguments.checksum_output is not None:
        checksum_payload = json.dumps(
            artifact_checksums(Path(__file__).resolve().parents[1]), indent=2, sort_keys=True
        ) + "\n"
        arguments.checksum_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.checksum_output.write_text(checksum_payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

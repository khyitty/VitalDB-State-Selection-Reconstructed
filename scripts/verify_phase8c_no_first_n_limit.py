"""Apply the production first-N guard to Phase 8C sources."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.provenance.source_guard import scan_production_sources  # noqa: E402


SOURCES = (
    ROOT / "src/vitaldb_state_selection/cohort/train_runtime_inputs.py",
    ROOT / "src/vitaldb_state_selection/rl_integration/train_runtime.py",
    ROOT / "scripts/run_phase8c_train_runtime_inputs.py",
)


def main() -> int:
    violations = scan_production_sources(SOURCES)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    runner = SOURCES[-1].read_text(encoding="utf-8")
    required = ("for record in records:", "EXPECTED_TRAIN_CASES", 'choices=("build", "verify-only", "smoke")')
    if any(value not in runner for value in required):
        print("Phase 8C full path does not visibly enumerate the sealed train set", file=sys.stderr)
        return 1
    forbidden = ("--max-cases", "--limit", "max_cases", "DEFAULT_N_CASES")
    if any(value in runner for value in forbidden):
        print("Phase 8C runner contains a hidden production cap", file=sys.stderr)
        return 1
    print(f"Phase 8C first-N guard passed for {len(SOURCES)} production sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

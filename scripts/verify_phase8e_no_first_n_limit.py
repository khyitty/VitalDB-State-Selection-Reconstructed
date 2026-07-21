"""Apply the production first-N guard to all Phase 8E execution sources."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.provenance.source_guard import scan_production_sources  # noqa: E402


SOURCES = (
    ROOT / "src/vitaldb_state_selection/cohort/test_observation_templates.py",
    ROOT / "src/vitaldb_state_selection/cohort/test_runtime_inputs.py",
    ROOT / "src/vitaldb_state_selection/rl_integration/final_evaluation.py",
    ROOT / "src/vitaldb_state_selection/statistics/paired_evaluation.py",
    ROOT / "scripts/run_phase8e_test_inputs.py",
    ROOT / "scripts/run_phase8e_final_evaluation.py",
    ROOT / "scripts/prepare_phase8e_evaluation.py",
)


def main() -> int:
    violations = scan_production_sources(SOURCES)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    joined = "\n".join(path.read_text(encoding="utf-8") for path in SOURCES)
    required = ("EXPECTED_TEST_CASES", "assert_test_cases", "for case in cases", "for record in records", "CONDITIONS")
    if any(token not in joined for token in required):
        print("Phase 8E does not visibly cover the complete sealed-test universe", file=sys.stderr)
        return 1
    forbidden = ("--max-cases", "--limit-cases", "max_cases", "DEFAULT_N_CASES", "case_limit")
    if any(token in joined for token in forbidden):
        print("Phase 8E contains a hidden case cap", file=sys.stderr)
        return 1
    print(f"Phase 8E first-N guard passed for {len(SOURCES)} production sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

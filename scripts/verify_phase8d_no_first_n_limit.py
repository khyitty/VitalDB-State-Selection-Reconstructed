"""Apply the production first-N guard to Phase 8D sources."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.provenance.source_guard import scan_production_sources  # noqa: E402


SOURCES = (
    ROOT / "src/vitaldb_state_selection/rl_integration/final_training.py",
    ROOT / "scripts/prepare_phase8d_final_training.py",
    ROOT / "scripts/run_phase8d_final_training.py",
)


def main() -> int:
    violations = scan_production_sources(SOURCES)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    joined = "\n".join(path.read_text(encoding="utf-8") for path in SOURCES)
    required = ("1970", "FINAL_TOTAL_TIMESTEPS", "DeterministicTrainCaseSequence", "for condition in conditions")
    if any(value not in joined for value in required):
        print("Phase 8D does not visibly cover the complete sealed train universe and requested shard", file=sys.stderr)
        return 1
    forbidden = ("--max-cases", "--limit-cases", "max_cases", "DEFAULT_N_CASES", "seed_sweep")
    if any(value in joined for value in forbidden):
        print("Phase 8D contains a hidden case cap or seed sweep", file=sys.stderr)
        return 1
    print(f"Phase 8D first-N guard passed for {len(SOURCES)} production sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

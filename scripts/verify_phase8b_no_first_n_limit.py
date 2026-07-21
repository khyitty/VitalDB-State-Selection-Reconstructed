"""Apply the production first-N AST guard only to Phase 8B sources."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.provenance.source_guard import scan_production_sources  # noqa: E402


PHASE8B_SOURCES = (
    ROOT / "src/vitaldb_state_selection/cohort/train_raw_access.py",
    ROOT / "src/vitaldb_state_selection/cohort/train_observation_templates.py",
    ROOT / "src/vitaldb_state_selection/anesthesia/recorded_observation.py",
    ROOT / "scripts/run_phase8b_train_template_extraction.py",
)


def main() -> int:
    violations = scan_production_sources(PHASE8B_SOURCES)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    runner = PHASE8B_SOURCES[-1].read_text(encoding="utf-8")
    required_full_path = (
        "for position, case in enumerate(cases, start=1)",
        'choices=("preflight", "full", "verify-only")',
        "EXPECTED_TRAIN_CASES",
    )
    if any(text not in runner for text in required_full_path):
        print("Phase 8B full path does not visibly enumerate the complete sealed train set", file=sys.stderr)
        return 1
    forbidden = ("--max-cases", "--limit", "--sample", "max_cases", "DEFAULT_N_CASES")
    if any(text in runner for text in forbidden):
        print("Phase 8B runner contains a hidden production case cap", file=sys.stderr)
        return 1
    print(f"Phase 8B first-N guard passed for {len(PHASE8B_SOURCES)} production sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

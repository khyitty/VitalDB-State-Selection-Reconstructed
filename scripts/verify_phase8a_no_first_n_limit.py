"""Apply the production first-N AST guard to the Phase 8A sources."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.provenance.source_guard import scan_production_sources  # noqa: E402


PHASE8A_SOURCES = (
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "subject_split.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "split_guard.py",
    ROOT / "scripts" / "run_phase8a_subject_split.py",
)


def main() -> int:
    violations = scan_production_sources(PHASE8A_SOURCES)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print(f"Phase 8A first-N guard passed for {len(PHASE8A_SOURCES)} production sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

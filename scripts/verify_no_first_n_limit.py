"""Fail if production audit sources contain first-N selection constructs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.provenance.source_guard import (  # noqa: E402
    scan_production_sources,
)


PRODUCTION_SOURCES = (
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "clinical_metadata.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "causal_grid_feasibility.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "decision_support.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "eligibility.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "metadata_audit.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "primary_acquisition.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "primary_signal_quality.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "track_inventory.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "volatile_characterization.py",
    ROOT / "src" / "vitaldb_state_selection" / "cohort" / "volatile_sensitivity.py",
    ROOT / "src" / "vitaldb_state_selection" / "data" / "downloader.py",
    ROOT / "src" / "vitaldb_state_selection" / "data" / "vitaldb_api.py",
    ROOT / "src" / "vitaldb_state_selection" / "provenance" / "manifests.py",
    ROOT / "scripts" / "run_metadata_audit.py",
    ROOT / "scripts" / "run_causal_grid_feasibility_audit.py",
    ROOT / "scripts" / "run_primary_signal_acquisition.py",
    ROOT / "scripts" / "run_primary_signal_quality_characterization.py",
    ROOT / "scripts" / "run_eligibility_decision_support.py",
    ROOT / "scripts" / "run_volatile_characterization.py",
    ROOT / "scripts" / "run_volatile_sensitivity_audit.py",
    ROOT / "scripts" / "download_candidate_signals.py",
)


def main() -> int:
    violations = scan_production_sources(PRODUCTION_SOURCES)
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print(f"first-N guard passed for {len(PRODUCTION_SOURCES)} production sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

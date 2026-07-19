# VitalDB State Selection — Confirmatory Reset

This repository builds the governance and audit foundation for a new confirmatory
VitalDB cohort. It does **not** continue the legacy 98-case analysis and does not
claim an exact reproduction of unpublished source code.

## Current scope

The authorized work stops after:

1. repository governance and provenance;
2. read-only legacy migration inventory;
3. full-case eligibility/download audit infrastructure;
4. synthetic and fixed-seed random 25-case engineering dry runs.

The following are deliberately not authorized: full signal download, final quality
thresholds, final cohort freeze, train/validation/test splitting, Cp/Ce reconstruction,
prediction or feature selection, full model training, and PPO training.

## Non-negotiable safeguards

- Production inventory must account for all case IDs 1–6388 exactly once.
- Production code rejects case limits, first-N slicing, duplicates, and missing rows.
- Failed downloads remain explicit manifest rows and are never silently excluded.
- Track aliases are accepted only from versioned, human-reviewed configuration.
- Quality thresholds remain unset until an outcome-blind human review of metadata
  and missingness distributions.
- Legacy 98-case IDs, splits, scalers, checkpoints, metrics, figures, and model
  artifacts are prohibited inputs.

## Quick checks

```powershell
python -m unittest discover -s tests -v
python scripts/verify_no_first_n_limit.py
python scripts/run_metadata_audit.py --help
python scripts/download_candidate_signals.py --help
```

Dry-run output is engineering evidence only. It is not a scientific result and must
not be used to set eligibility thresholds.

See [Research Reset Protocol v1](docs/research_reset_protocol_v1.md),
[Repository Migration Plan](docs/repository_migration_plan.md), and
[Eligibility Audit Plan](docs/eligibility_audit_plan.md).


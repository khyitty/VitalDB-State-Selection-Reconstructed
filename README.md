# VitalDB State Selection — Confirmatory Reset

This repository builds the governance and audit foundation for a new confirmatory
VitalDB cohort. It does **not** continue the legacy 98-case analysis and does not
claim an exact reproduction of unpublished source code.

## Current scope

The authorized work stops after:

1. repository governance and provenance;
2. read-only legacy migration inventory;
3. full-case eligibility/download audit infrastructure;
4. synthetic and fixed-seed random 25-case engineering dry runs;
5. Phase 5A full 1–6388 `/cases` metadata and `/trks` inventory audit;
6. Phase 5B outcome-blind eligibility decision-support audit.

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

The Phase 3 framework independently implements full-range metadata accounting,
exact track inventory, schema-validated manifests, explicit failures, and
checksum-based download resume. `download_candidate_signals.py` is production
blocked until a human authorization file exists and drug-rate units are marked
validated in the versioned alias configuration. Neither condition is satisfied in
this phase.

The authorized Phase 4 run is fixed at seed `20260719` and 25 random cases:

```powershell
python scripts/run_engineering_dry_run.py
python scripts/run_engineering_dry_run.py --with-signals
```

Its committed report and manifests are engineering evidence only. Raw signals stay
Git-ignored; no threshold, cohort, split, prediction, feature-selection, Cp/Ce, or
PPO step is performed.

Dry-run output is engineering evidence only. It is not a scientific result and must
not be used to set eligibility thresholds.

Phase 5A was executed with:

```powershell
python scripts/run_metadata_audit.py
```

It queried metadata endpoints only and produced the full manifest, source snapshot,
failure log, checksums, and unapproved-name report. New track names were not mapped
to concepts. Legacy 98-case IDs were not accessed, and all scientific eligibility
decisions remain pending.

Phase 5B was executed with:

```powershell
python scripts/run_eligibility_decision_support.py
```

It rechecked the complete `/trks` metadata snapshot, reviewed only the explicitly
requested research-relevant names, and generated descriptive crosstabs and
unselected eligibility scenarios. Track presence is not treated as exposure, the
official documentary unit findings do not approve the versioned unit status, and
RFTN20/RFTN50 remain separate. The machine-readable summary is paired with
`docs/decision_support_report.md`.

See [Research Reset Protocol v1](docs/research_reset_protocol_v1.md),
[Repository Migration Plan](docs/repository_migration_plan.md), and
[Eligibility Audit Plan](docs/eligibility_audit_plan.md).

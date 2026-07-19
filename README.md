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
6. Phase 5B outcome-blind eligibility decision-support audit;
7. Phase 5C outcome-blind characterization of seven exact volatile tracks in the
   unfrozen 3,219-case decision-support universe;
8. Phase 5D outcome-blind volatile-rule sensitivity audit; and
9. Phase 6A Protocol v1.1 pre-quality cohort accounting and checksum-resumable
   acquisition of exactly `BIS/BIS`, `BIS/SQI`, `Orchestra/PPF20_RATE`, and
   `Orchestra/RFTN20_RATE` after a fixed-seed 25-case preflight.

The following are deliberately not authorized: full signal download outside the seven
Phase 5C volatile tracks and four Phase 6A exact tracks, final quality thresholds,
final cohort freeze, train/validation/test splitting, Cp/Ce reconstruction, dose
calculation, prediction or feature selection, full model training, and PPO training.

## Non-negotiable safeguards

- Production inventory must account for all case IDs 1–6388 exactly once.
- Production code rejects case limits, first-N slicing, duplicates, and missing rows.
- Failed downloads remain explicit manifest rows and are never silently excluded.
- Track aliases are accepted only from versioned, human-reviewed configuration.
- Quality thresholds remain unset until an outcome-blind human review of metadata
  and missingness distributions.
- The exact legacy actual-use 98 case IDs may be read only for Phase 6A overlap
  exclusion. Split assignments, scalers, checkpoints, metrics, figures, and model
  artifacts remain prohibited inputs.

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

Phase 5C used a fixed-seed, presence-stratified 20-case engineering preflight before
the bounded full-universe characterization:

```powershell
python scripts/run_volatile_characterization.py --stage preflight
python scripts/run_volatile_characterization.py --stage full
```

Only the seven exact volatile tracks named in the Phase 5C protocol were requested.
The analysis universe remains unfrozen, track presence and positive values are not
treated as exposure or TIVA decisions, and every alias, unit, cutoff, and eligibility
decision remains pending human review. Raw signals are Git-ignored; only manifests,
machine-readable summaries, provenance, and decision-support reports are published.

Protocol v1.1 then fixed the 10-second Phase 5D duration scenario as the primary
volatile exclusion and approved the exact Phase 6A units and roles. Phase 6A uses:

```powershell
python scripts/run_primary_signal_acquisition.py --stage preflight
python scripts/run_primary_signal_acquisition.py --stage full
```

The 3,219-case manifest is explicitly pre-quality and unfrozen. Case 4476 retains
its invalid anesthesia window and is excluded without repair. `BIS/SQI` remains
QC-only and is prohibited as a prediction feature or PPO state. No acquired value
creates a new exclusion, and no signal-quality threshold is selected.

See [Research Reset Protocol v1](docs/research_reset_protocol_v1.md),
[Repository Migration Plan](docs/repository_migration_plan.md), and
[Eligibility Audit Plan](docs/eligibility_audit_plan.md).

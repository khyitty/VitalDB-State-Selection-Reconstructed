# Phase 7D Online Observation Contract Amendment Report

## Outcome

Protocol v1.3.1 amends the online P0/P1 contrast while preserving Protocol v1.2's 2,460-case, 2,415-subject cohort and every prior retrospective artifact. P0/P1 now differ only as a bundled BIS observation preprocessing contrast: no SQI gate plus 30-second freshness versus exact-timestamp SQI at least 50 plus 20-second freshness.

Online drug-rate staleness was removed. Both conditions use identical applied internal propofol-action and remifentanil-schedule histories with no artificial drug missingness, mask, or age.

Option B-minimal is human-selected for BIS: value, availability mask, and age. It distinguishes genuine BIS 0 from missing. The no-prior flag remains audit-only. The numeric fixed age clipping maximum was not supplied and is explicitly pending before implementation.

S0 and S1 are frozen at 34 and 42 conceptual fields respectively. This phase creates no tensor adapter or real value. The future template contract contains only observation timing/SQI patterns and split-scoped pseudonymous provenance; no real template was extracted.

Path A laboratory-code reuse is primary, Path B legacy refactor is fallback, and Path C reconstruction is not approved. The concise handoff package and Korean request draft are ready.

## Execution boundary

No split, subject allocation, test seal, raw VitalDB read, raw BIS use, observation-template extraction, modeling array, normalization fit, real dose/Cp/Ce calculation, simulator/environment/PPO implementation, package installation, PPO execution, checkpoint, control metric, statistic, prediction, or Phase 7E work occurred.

## Workspace resolution

All 14 excluded scaffold changes were recoverably backed up and selectively removed. The backup is external to Git and is referenced only by a non-sensitive identifier and checksums. The repository returned to a clean baseline before amendment work began.

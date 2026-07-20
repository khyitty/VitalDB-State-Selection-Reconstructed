# Phase 8A Outcome-Blind Subject Split Report

## Result

- Subjects: 2415 total; 1932 train;
  483 test.
- Cases: 2460 total; 1970 train;
  490 test.
- Subject overlap: 0; case overlap: 0; case-to-parent split mismatch: 0.
- Allocation: `hamilton_stratified_sha256_rank_v1`, seed `20260720`.
- Maximum absolute primary continuous SMD:
  `0.029963981155984278`.
- Balance warnings: 0.
- Test seal payload SHA-256: `6083be99567d5d7d4989ef3c9e35fc51255f614098697f289daac756d643f9af`.

Membership was fixed before balance calculation. Warnings did not trigger a
retry, alternate seed, changed strata, or changed membership. Secondary
case-level metadata is descriptive only.

## Boundary

No raw signal, outcome, observation template, preprocessing array, scaler,
real-subject simulator, PPO training/evaluation, model, or checkpoint was read or
created. Phase 8B and later work did not begin.

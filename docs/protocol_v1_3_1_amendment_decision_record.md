# Protocol v1.3.1 Online Observation Contract Amendment

Status: human-approved amendment; observation implementation, split, and PPO execution remain unauthorized.

## Decision

Protocol v1.3.1 amends only the online observation contract of Protocol v1.3. The Protocol v1.2 cohort remains frozen at 2,460 cases and 2,415 subjects. Existing Phase 6C artifacts, retrospective candidate IDs, and Protocol v1.3 artifacts remain unchanged.

The online confirmatory contrast is now a BIS-observation preprocessing bundle:

- P0-online (`P0_online_bis_permissive_v1`): no SQI gate and a 30-second BIS staleness cap.
- P1-online (`P1_online_bis_quality_v1`): exact-observation-timestamp SQI at least 50 and a 20-second BIS staleness cap.

Both use causal lookup, the inclusive BIS range 0–100, admissible BIS 0–10, no future observation, no interpolation, no backward fill, a 10-second grid, and history at t−50 through t in 10-second increments. The confirmatory interpretation is the complete P0/P1 bundle effect; no SQI-only or freshness-only component effect is claimed and no component ablation is defined.

## Removed online contrast

The Phase 6C drug-rate hold caps (120 versus 60 seconds) are retrospective logged-track alignment rules. They are not online controller observation rules. Protocol v1.3.1 removes this difference from the online comparison.

Both pipelines use the same applied internal propofol command history and the same applied exogenous remifentanil schedule history. Neither rate receives artificial missingness, staleness, availability masks, or observation-age channels. No undocumented monitor/log delay is assumed.

## Missing encoding decision

Option B-minimal is selected for BIS history only. Every BIS history point has value, binary availability mask, and observation age in seconds. Unavailable BIS uses value 0 and mask 0; available genuine BIS 0 uses value 0 and mask 1. Detailed rejection/no-prior reasons remain audit-only, and no Option C no-prior state flag is added.

Age is nonnegative and will be clipped by a fixed, predeclared maximum that is never fit from train or test data. The human instruction did not supply its numeric value, so `age_clip_maximum_seconds` remains explicitly pending before implementation. This does not reopen the selected channel structure, but it blocks implementation until the numeric constant is approved.

## State schemas

S0 has 34 conceptual scalar fields: four demographics, six BIS values, six BIS masks, six BIS ages, six propofol command rates, and six remifentanil environment rates. SQI numeric values are absent. Physical tensor dimension remains separate until sex encoding is specified.

S1 is a strict conceptual superset of S0 and adds eight pharmacology fields, for 42 conceptual fields. No S0/S1 tensor adapter or real value is created in this phase.

## Future observation template

The future template contains BIS observation timestamps, exact BIS/SQI timestamps and SQI values, anesthesia-relative timing, a pseudonymous key, and a split label only after split creation. It excludes raw observed BIS values, future targets, real propofol outcomes, predictions, and PPO results. The layer will sample latent true BIS according to that timestamp/SQI pattern.

P0 and P1 must receive the same latent trajectory, observation template, and disturbances. Reward and scientific outcomes use latent true BIS. Future training may use train-subject templates only and test evaluation may use test-subject templates only. No template was extracted in Phase 7D.

## Implementation path

Path A—laboratory code reuse—is approved as the primary path. Path B—small legacy refactor—is a fallback only if authoritative laboratory code is unavailable or non-executable. Path C full reconstruction is not approved.

No dependency was installed or changed. No simulator, environment, observation adapter, PPO trainer, split, test seal, modeling array, real dose/Cp/Ce value, checkpoint, training, evaluation, or statistic was created.

# Phase 7B Control-Focused Design Report

## Outcome

Protocol v1.3 freezes a control-focused 2×2 design with P0/P1 preprocessing and S0/S1 state representation. The frozen Protocol v1.2 cohort remains 2,460 cases across 2,415 subjects. P0 and P1 each have 2,470 source-case rows in Phase 6C and each links to all 2,460 frozen cases; none of the ten excluded cases is authorized to re-enter.

## Feasibility finding

The inspected legacy simulator supplies an observed BIS at every simulator advance but has no SQI, BIS missingness, delayed-observation, or drug-rate-staleness layer. Its history mask represents episode-start padding, not signal availability. A new observation replay/corruption layer is therefore required before P0/P1 can produce meaningfully different controller views of one latent trajectory. Fixed-shape missing encoding is unresolved and requires human approval. Protocol v1.3 is not implementation-ready and PPO execution remains prohibited.

## State and policy boundary

S0 is the observable-history state; S1 is its strict conceptual superset with eight pharmacology candidates. Legacy dose and Cp/Ce interfaces are reference-only and require refactor plus primary-source revalidation. No value was calculated. Four future policies are named PPO_P0S0, PPO_P1S0, PPO_P0S1, and PPO_P1S1. Exact architecture, budget, reward profile, action bounds, and missing encoding remain pending human review but must be identical across conditions when frozen.

## Planned design

The future split unit is subjectid with target counts 1,932 train and 483 test subjects and no formal validation split. No membership or seal was created. Smoke seed 42 and final seeds 7, 42, and 84 are predeclared; no PPO was run. Outcomes and repeated-measures statistics are specifications only.

## Execution boundary

No raw signal, API, outcome, split, test seal, modeling array, normalization, imputation, dose, Cp/Ce, prediction, feature selection, PPO, checkpoint, evaluation, control metric, or statistical test was executed. Legacy checkpoints, configs, splits, scalers, selected features, metrics, and results were not read.

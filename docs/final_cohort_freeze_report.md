# Phase 6D Final Cohort Freeze Report

## Frozen decision

- Protocol: `1.2`.
- Selected candidate: `sqi_ge_50__bis20s__drug60s`.
- Minimum usable prediction endpoints: `120`.
- Source cases: `2470`.
- Final eligible: `2460`.
- Final excluded: `10`.
- Sorted eligible-ID SHA-256: `f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd`.

## Inherited exclusions

Legacy overlap, Phase 6A volatile exclusion, and invalid-anesthesia-window overlap are all zero in the 2,470-case source and frozen eligible cohort. Demographic and warning fields are preserved but do not add an unapproved clinical cutoff.

## Interpretation boundary

This is a human-approved preprocessing and cohort-freeze record based only on outcome-blind Phase 6B/6C feasibility. Alternative counts are robustness references, not additional final cohorts. The minimum is an endpoint count, not a continuous-duration claim.

## Prohibited work

No raw signal was read or downloaded. No API request, split, stratification, test sealing, modeling array, normalization, imputation fit, unit conversion, dose, Cp/Ce, persistence baseline, prediction, metric, Elastic Net, GRU, Attention-GRU, feature selection, target inspection, or PPO execution occurred.

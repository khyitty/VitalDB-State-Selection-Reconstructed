# Phase 6C Causal Grid and Prediction-Window Feasibility Audit

## Scope and accounting

- Source cases: `2470`; exact candidate combinations: `60`.
- Case×candidate rows: `148200`.
- Only checksum-verified Phase 6A BIS/BIS, BIS/SQI, PPF20_RATE, and RFTN20_RATE files were read.
- No API request, new raw file, modeling array, outcome, split, model, Cp/Ce, dose, feature selection, or PPO execution occurred.

## Fixed causal structure

The 10-second grid is anchored to each case's anesthesia start. History is t-50 through t in 10-second steps and the target is t+30. Every lookup requires timestamp <= grid time; all eight time points remain inside the same case, anesthesia window, and inherited common observed span.
BIS uses the descriptive 0-100 range, including 0-10. Required SQI is joined only at the exact BIS timestamp and remains QC-only. Drug rates use the most recent finite observation, never assume pre-observation zero, never use negative values, and apply only the candidate finite hold caps.

Raw rows were not sorted, deduplicated, averaged, resampled, interpolated, smoothed, clipped, or filled. A derived chronological lookup index preserves the last finite raw-row value at duplicated timestamps; duplicate-derived grid uses are flagged.

## Candidate comparison — descriptive only

The smallest usable-case count among the 60 unselected candidates was `2465` (`sqi_ge_80__bis10s__drug30s`); the largest was `2468` (`sqi_not_required__bis10s__drug30s`).
These extrema are feasibility descriptions, not recommendations or a selected preprocessing rule.

## Minimum-window sensitivity

The 30, 60, 120, 300, and 600 endpoint counts are compared independently. Their approximate minute labels do not assert continuous usable duration.

## Phase 6B scenario comparison

Permissive, moderate, and strict Phase 6B flags are compared with actual causal-window counts for every candidate and minimum-window threshold. Cases failing moderate/strict because of BIS 10-100 fractions are separately counted; BIS 0-10 remains admissible in this audit.

## Static demographics and PK-input feasibility

All-four-demographics-present: `2470`; Schnider/Minto basic-input feasibility flag: `2470`.
No clinical plausibility cutoff, PK parameter, lean-body-mass value, Cp/Ce value, or demographic exclusion was calculated.

## Boundary review

Fixed seed `20260720` supplies at most five IDs per requested boundary category. Samples do not change inclusion or exclusion.

## Decision boundary

No SQI rule, BIS staleness cap, drug hold cap, minimum-window threshold, Phase 6B scenario, preprocessing rule, quality threshold, or final cohort was selected. Protocol v1.2, cohort freeze, split, and modeling remain outside Phase 6C.

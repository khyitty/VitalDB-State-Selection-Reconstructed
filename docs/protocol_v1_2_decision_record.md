# Protocol v1.2 Decision Record

Status: human-approved and frozen on 2026-07-20.

## Provenance

### Fact

- Source Phase 6C commit: `b8f010dcc67497f77e26cee53094819f2f5d6cd9`.
- Verified Phase 6C publication follow-up: `624e5eaf9f5919ae94fa4d344478af85563ee622`.
- The decision used only outcome-blind Phase 6B/6C feasibility artifacts. No test outcome, target distribution, model result, prediction metric, or control result was inspected.
- Source accounting is 2,470 cases. The selected rule retains 2,460 and excludes 10.

### Human decision

- Selected candidate: `sqi_ge_50__bis20s__drug60s`.
- Grid: 10 seconds, anchored at each case anesthesia start.
- History: `t-50, t-40, t-30, t-20, t-10, t`; target: `t+30`.
- Every history and target stays inside the same case, anesthesia window, and inherited common observed span.
- Final eligibility requires at least 120 usable prediction endpoints under the selected candidate.

### Interpretation

The 120 endpoints are a count of usable 10-second prediction endpoints. They are not described as 20 continuous minutes. This record freezes preprocessing eligibility only; it does not authorize a split, modeling array, model, dose, Cp/Ce, feature selection, or PPO.

## Selected BIS and SQI rule

### Fact

- Finite BIS in the inclusive numerical range 0–100 is admissible. BIS below 0 or above 100 is unavailable and values are not clipped.
- SQI is joined only at the exact BIS raw timestamp. Usable BIS requires SQI >=50.
- At a requested history or target time, the most recent usable BIS at or before that time is allowed only when staleness is <=20 seconds.

### Human decision

BIS 0–10 remains admissible because Phase 6B/6C supplied no outcome-blind evidence that these in-range values are automatically erroneous. The Phase 6B BIS 10–100 fractions are not used for exclusion. SQI 50 was selected as the QC threshold; SQI 80, which retains 2412 cases at the 120-endpoint rule, remains a stricter sensitivity reference rather than the primary rule.

### Interpretation

SQI is QC-only and is prohibited from the prediction feature universe and PPO state. There is no case-level SQI-fraction threshold, nearest SQI match, SQI interpolation, or future BIS/SQI use.

## Selected drug-rate rule

### Fact

- Propofol and remifentanil are aligned independently using the most recent finite, nonnegative observation at or before each grid time.
- The hold cap is <=60 seconds. Zero is valid; negative rate is unavailable and remains a warning.
- The period before the first observation is not filled with zero. There is no future use, interpolation, backward fill, unlimited hold, unit conversion, dose, or Cp/Ce calculation.

### Human decision

The 60-second cap was selected to limit the temporal age of carried rate observations. The 120-, 300-, and 600-second candidates each retain 2460, 2460, and 2460 cases at the same 120-endpoint rule, but their longer stale holds are preserved only as sensitivity analyses.

### Interpretation

Equal case counts do not make longer holds equivalent. This is a temporal-fidelity decision made without model performance.

## Duplicate timestamps

### Human decision

For duplicated raw timestamps, the derived lookup uses the last finite value in original payload order. Raw rows are not deleted, averaged, sorted in place, or modified. Duplicate-derived grid use remains flagged.

## Minimum-window decision

### Fact

For the selected candidate, thresholds 30, 60, 120, 300, and 600 retain 2464, 2462, 2,460, 2286, and 1528 cases, respectively.

### Human decision

The minimum is 120 usable prediction endpoints. The 300 and 600 thresholds were not selected because they would impose substantially longer endpoint-count requirements and exclude additional cases without an outcome-blind necessity established by Phase 6B/6C.

### Interpretation

All unselected SQI, BIS-staleness, drug-hold, and minimum-window alternatives remain machine-readable robustness references. They are not additional frozen cohorts.

## Explicitly unused case-level rules

Phase 6B permissive/moderate/strict scenarios, BIS 10–100 fraction, case-level SQI fraction, common-span ratio, anesthesia-duration 60/120-minute thresholds, longest raw timestamp gap, minimum 300/600 windows, and clinical-plausibility demographic cutoffs do not control final eligibility.

## Freeze boundary

There is exactly one primary final cohort. No train/validation/test split, stratification, test sealing, normalization, imputation fit, modeling array, persistence baseline, prediction, Elastic Net, GRU, Attention-GRU, feature selection, Cp/Ce reconstruction, dose calculation, or PPO is authorized or performed in Phase 6D.

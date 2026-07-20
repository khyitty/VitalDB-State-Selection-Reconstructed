# Phase 7C Observation-Quality Minimum-Layer Plan

## Required empirical layer

The legacy simulator produces a latent/noiseless BIS and an observed BIS but no empirical VitalDB SQI, device timestamp, or missingness process. The smallest future P0/P1 layer is therefore an observation adapter placed between one shared latent simulator trajectory and the controller-visible state.

Its later, separately approved replay-template contract should contain causal grid timestamps, BIS observation timestamps/availability, exact-timestamp SQI values, and a template/version identifier. The same template and latent trajectory must feed P0 and P1. P0 would omit SQI gating and apply a 30-second BIS cap; P1 would require exact-timestamp SQI at least 50 and apply a 20-second BIS cap. No interpolation or future timestamp may be introduced.

No replay layer or real template was implemented or extracted in Phase 7C. Synthetic corruption may be useful for software tests but cannot support the main empirical interpretation by itself, because its result is conditional on investigator-chosen corruption assumptions.

## Drug-rate boundary

No drug-rate missingness layer should be implemented under current evidence. The legacy environment directly knows the applied propofol action and the exogenous remifentanil schedule. Treating those internal values as delayed monitor observations would introduce an unsupported error mechanism. P0/P1 therefore cannot retain the Phase 6C 120/60-second drug-hold contrast as an online operational factor without a new human protocol decision or primary evidence that the controller receives delayed logged rates.

## Missing-encoding options

All three candidates distinguish a genuine BIS/rate value of zero from missing through an availability mask. Option A adds 18 dimensions to the 18 dynamic history values, Option B adds 36, and Option C adds 54, assuming three signals and six history points. Their full comparison is in `data/manifests/phase7c_missing_encoding_options.csv`.

Option C is the engineering recommendation because it can distinguish “never observed” from stale or rejected observations without conflating that state with an age sentinel. Its status is `recommended_pending_human_approval`; it is not selected, frozen, or implemented. A human decision must also freeze whether reason codes are controller-visible or audit-only and define the age convention before implementation.

## Minimal future implementation files

A later approved implementation should add only:

1. one replay-template schema and loader;
2. one causal P0/P1 BIS observation adapter;
3. one fixed-order state adapter implementing the approved missing encoding;
4. synthetic contract tests plus approved empirical-template tests;
5. a paired-latent invariant test proving that only controller observations differ.

The existing simulator/environment should be reused if its dependency and primary-source gates pass. A new simulator or PPO trainer is not part of this minimum layer.

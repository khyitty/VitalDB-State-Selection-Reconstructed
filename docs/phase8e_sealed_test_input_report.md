# Phase 8E Sealed-Test Input Report

Phase 8E built a separate ignored store for all 490 sealed-test cases. The Phase 8A split gate was applied before parsing any source row or resolving any raw path. Test BIS, SQI, and exact `Orchestra/RFTN20_RATE` were each logically accessed 490 times; train-case and propofol raw access counts were zero.

The test observation-template root is `c2375f7a762a0e2a4d5492edad95214e9bb582b7a81b8db9ade4e336bceb55e1`. P0 and P1 share each case's same raw event template. P0 applies no SQI gate and a 30-second BIS staleness limit; P1 requires exact-timestamp SQI at least 50 and a 20-second staleness limit. Raw BIS values are not persisted, while SQI and event timing remain private.

The test runtime root is `beec96ac880397bcfdf8f4987af2641791a841e398b5ef2c61aa7ba48eeb5dfe`. Every bundle contains the validated patient profile, private template reference, causal RFTN20 schedule, sealed split identity, and source checksums. Missing and invalid required profiles were zero and no fallback or imputation was used.

The unchanged train-only scaler registry SHA-256 is `0311e6ca6542592893e81f7a6949eb2f50997e6d5d53aef9dd1e64bfe7794503`. S0 has 34 fields and S1 has 42. The frozen scaler was applied to 1,960 condition-case initial states without fitting or non-finite output. Phase 8B and 8C train roots matched before and after extraction.

No policy was loaded and no model episode, condition comparison, ranking, or best-model selection was performed.

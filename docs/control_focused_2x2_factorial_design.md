# Control-Focused 2×2 Factorial Design

The four confirmatory conditions are P0S0, P1S0, P0S1, and P1S1. Each future policy must be trained independently from scratch and evaluated on the same test subjects. Preprocessing and state are the only intended factors; simulator, reward, action, PPO framework, capacity, budget, seeds, and evaluation must be invariant.

P0 is the Phase 6C `sqi_not_required__bis30s__drug120s` bundle. P1 is `sqi_ge_50__bis20s__drug60s`. The design estimates bundle-level preprocessing effects only; it defines no SQI-only, BIS-staleness-only, or drug-hold-only ablation.

S0 contains age, sex, height, weight and six 10-second samples each of BIS, propofol rate, and remifentanil rate. S1 is a strict conceptual superset adding recent and cumulative doses plus propofol/remifentanil Cp and Ce. SQI is quality control only and is absent from both states.

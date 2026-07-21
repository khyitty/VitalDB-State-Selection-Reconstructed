# Phase 8E Final Evaluation Protocol

Final evaluation is blocked until P0S0, P1S0, P0S1, and P1S1 all have a checksum-valid final model at exactly 1,000,000 timesteps, seed 42, training implementation `b782b5e4a9d418f6b907a87d046c4e9789a3e5f0`, and the frozen PPO configuration. The runner accepts only `final_model.zip` whose checksum matches both `OUTPUT_COMPLETE.json` and the 1,000,000-step checkpoint. It does not offer checkpoint selection.

The safe default is verify-only. Policy episodes require the explicit `--execute` flag and a private output root. Verify-only validates the 490-case runtime store, common case order, train scaler dimensions, and all four model completion records without importing or loading an SB3 model.

Each condition must use the same ordered 490 cases, patient profile, remifentanil schedule, episode timing, simulator constants, reward and action bounds, and deterministic seed. Inference is deterministic. Learning, optimizer steps, scaler updates, exploration noise, test-derived subset changes, and silent episode exclusion are prohibited. Failures remain explicit paired rows.

Control metrics use simulator latent BIS, not observation visibility. The target is 50 and the already established safe range is 40–60. Exact definitions and units are frozen in `phase8e_metric_manifest.json`.

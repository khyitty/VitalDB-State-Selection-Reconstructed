# Phase 8C Train Runtime Input Report

Phase 8C built 1,970 private train runtime bundles and zero test bundles. All required patient profiles were present and valid; no fallback or imputation was used. Exactly 1,970 checksum-matched logical accesses were made to the approved train `Orchestra/RFTN20_RATE` source, with zero test, propofol, or test-template access.

The private runtime store root is `25ad8a860f6c9b0b45febec7ff7d0d0edf88c0f1953229c8d95e207508d3a606`. It contains per-case patient profiles and derived causal schedules plus references to, rather than copies of, the Phase 8B templates. The Phase 8B root remained `96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2`. There were no partial directories, and both stores remain ignored and untracked.

S0 and S1 contain 34 and 42 ordered fields. Twelve preflight reset/step checks across three distinct train subjects and four conditions passed with finite observations and rewards, deterministic seed-42 reset, unchanged action bounds, and no future remifentanil exposure. The same S-specific scaler is shared by each P pair.

The isolated SB3/Gymnasium runtime then completed P0S0, P1S0, P0S1, and P1S1 correctness smoke runs. Every condition passed the environment checker, VecEnv construction, PPO initialization, and exactly 128 CPU timesteps with finite parameters, available gradients, and logged losses. No model, optimizer, checkpoint, trajectory, monitor, or TensorBoard output was persisted. Rewards were not compared, conditions were not ranked, and these smoke runs are not final training or evaluation.

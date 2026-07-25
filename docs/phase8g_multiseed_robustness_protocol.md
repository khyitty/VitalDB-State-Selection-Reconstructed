# Phase 8G — Prespecified Multi-Seed Robustness Extension

## Amendment status

The original confirmatory training and sealed-test result used seed 42. On
2026-07-25, before inspecting any additional-seed result, seeds 43 and 44 were
prespecified as a robustness extension for training stochasticity. This is a new
phase and does not retrospectively alter Phase 8D, Phase 8E, or Phase 8F.

All three seeds will be reported without seed selection or exclusion. The primary
research question, four conditions, metrics, contrasts, cohort, subject-level
split, state scalers, simulator, reward, action bounds, episode horizon, and
train-case universe remain unchanged.

## Fixed execution contract

- Conditions: `P0S0`, `P1S0`, `P0S1`, `P1S1`
- Extension seeds: exactly 43 and 44
- Budget: exactly 1,000,000 environment timesteps per condition and seed
- Checkpoints: exactly every 100,000 timesteps through 1,000,000
- PPO architecture and hyperparameters: identical to frozen Phase 8D
- Shard A / Laptop A: `P0S0`, then `P1S0`
- Shard B / Laptop B: `P0S1`, then `P1S1`
- No early stopping, hyperparameter search, best-checkpoint selection, or
  performance-based seed inclusion

For one seed, all four conditions begin from the same independent NumPy PCG64
train-case stream. Seeds 43 and 44 use different streams over the same ordered,
checksum-verified 1,970-case train universe.

Python `random`, NumPy global RNG, PyTorch CPU RNG, SB3 initialization,
Gymnasium resets, simulator resets, and the PCG64 train-case stream all use the
requested extension seed.

## Immutable and private boundaries

The four existing `seed_42` directories are immutable. The Phase 8D runner
continues to reject every non-42 seed. Phase 8G writes only to
`data/processed/phase8d_final_training_v1/<condition>/seed_<43|44>`.

Models, optimizer states, checkpoints, RNG states, private episode sequences,
progress logs, patient bundles, and private stores remain Git-ignored. Training
must record zero test access and zero future-remifentanil leakage.

Sealed-test evaluation is not authorized by this protocol. It may begin only
after all four conditions for both additional seeds have completed and passed
checksum verification, and only under a separate explicit approval.

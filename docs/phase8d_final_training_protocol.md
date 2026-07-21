# Phase 8D Final PPO Training Protocol

## Scope

Phase 8D freezes and publishes the execution infrastructure for four train-only PPO conditions. It does not open test artifacts, evaluate a policy, compare conditions, select a best checkpoint, or make a statistical claim. Training remains in progress until the exact 1,000,000-timestep checkpoint exists for all four conditions.

## Equal-compute protocol

- Conditions: `P0S0`, `P1S0`, `P0S1`, `P1S1`
- Seed: 42 for every condition; no seed sweep or alternate-seed search
- Budget: 1,000,000 SB3 environment timesteps per condition
- Checkpoints: exactly every 100,000 environment timesteps and at 1,000,000
- Same PPO hyperparameters, optimizer, reward, action bounds, episode timing, patient/remifentanil universe, and deterministic case sequence across conditions
- The S0/S1 observation input dimensions are 34/42; the hidden network depth and width are identical
- No early stopping, best-checkpoint selection, hyperparameter search, conditional extension, or test-based selection

The source paper reports a training epoch count of `10^6`. This reconstruction uses 1,000,000 environment timesteps per condition as a pragmatic, equal-compute, paper-aligned budget. It does not claim exact epoch, rollout, minibatch, or optimizer-update equivalence.

## Sampling and resume boundary

The sampler draws uniformly over all 1,970 sealed train cases using an independent NumPy PCG64 stream with master seed 42. Every condition starts from the same stream state. Public artifacts contain only the train-universe and ordered-sequence checksums; the episode sequence is stored only in private checkpoint state.

Each private checkpoint contains the SB3 model archive including optimizer state, Python/NumPy/Torch RNG state, next-episode sampler state, configuration and runtime-root metadata, and per-file checksums. Resume restores those states and rejects condition, seed, configuration, implementation SHA, state-schema, runtime-root, and budget mismatches. SB3's partially collected rollout buffer is not serialized, so interrupted mid-rollout resume is best-effort rather than claimed bit-identical to an uninterrupted optimizer trajectory.

## Publication boundary

Only protocol/configuration, checksum, shard, aggregate preflight, runner, test, and runbook artifacts are public. Models, optimizer state, checkpoints, episode sequences, progress logs, patient identifiers, event-level data, and private stores remain under ignored `data/processed/` paths.

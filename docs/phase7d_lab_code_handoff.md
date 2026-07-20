# Phase 7D Laboratory Code Handoff Package

## Goal

Please provide the smallest authoritative package needed to reuse the laboratory's existing PPO and simulator implementation. The preferred integration adds only the Protocol v1.3.1 BIS observation layer and S0/S1 adapter; it does not reconstruct PPO or the simulator.

## Required package

- source repository or archive with commit/version identifier and reuse permission;
- executable PPO training and evaluation entry points;
- dependency lock or environment definition with Python, Gymnasium, Stable-Baselines3, NumPy, SciPy, and PyTorch versions;
- patient simulator and PK/PD implementation with equation/unit provenance;
- exact reward equation, coefficients, timing, and safety terms;
- propofol action definition, physical unit, bounds, hold interval, and clipping behavior;
- PPO architecture, hyperparameters, training steps, seeds, and stopping rule;
- patient/episode sampling rule and repeated-subject handling;
- remifentanil schedule source, unit, timing, and controller visibility;
- episode and safety termination rules;
- checkpoint schema, clean example config/command, and expected output schemas;
- existing state schema and exact normalization rules, including whether any transform is fit.

Each item is classified in `data/manifests/protocol_v1_3_1_lab_handoff_checklist.csv` as `already_available`, `available_but_unverified`, `missing_request_from_lab`, `conflicting`, or `not_needed`.

## Acceptance probe for a later approved phase

Before training, the supplied package should support a clean install, checkpoint-free initialization, one synthetic environment reset and step, one actor/critic forward pass, and—only if already implemented—one synthetic update batch. That later probe must create no retained checkpoint or performance claim.

Phase 7D installs nothing and runs none of these environment/PPO operations.

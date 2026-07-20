# Phase 7C Recommended Minimal Implementation Roadmap

## Gate 1 — obtain authoritative materials

Complete the laboratory checklist, establish reuse permission, record the source SHA, and create an exact dependency lock. Do not use legacy checkpoints, results, splits, scalers, or frozen data-dependent configurations.

## Gate 2 — bounded executable verification

In an isolated environment, import the supplied simulator/environment/PPO modules, initialize without a checkpoint, run one synthetic reset and one step, run one actor and critic forward pass, and—only if an update already exists—run one synthetic batch update. Create no retained checkpoint and no performance result.

## Gate 3 — scientific contract review

Revalidate PK/PD equations and units, then obtain human approval for action semantics/bounds, reward equation/coefficients, PPO constants, remifentanil schedule, termination, normalization, and observation encoding. Resolve the Case A drug-rate conflict by amending P0/P1 or documenting a real delayed-observation interface.

## Gate 4 — minimum observation implementation

Implement only the approved BIS/SQI replay adapter and fixed-shape state adapter. Preserve one latent trajectory across P0/P1, keep reward/scientific outcomes on latent true BIS, and test causal/no-future behavior. Empirical replay extraction requires separate approval and happens only after its schema is frozen.

## Gate 5 — later research execution

Subject split, test seal, real replay arrays, training, checkpointing, four-condition evaluation, and statistics remain later phases with separate authorization. None is part of Phase 7C.

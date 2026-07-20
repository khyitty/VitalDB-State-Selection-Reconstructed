# Phase 7H determinism report

P0S0 was executed twice in the same isolated environment with the same synthetic profile, observation template, remifentanil schedule, seed 42, CPU device, one Torch CPU thread, and smoke configuration. Both repetitions completed 128 transitions without exception. Initial observations and first deterministic predictions matched, and the final in-memory policy parameter SHA-256 checksums were identical.

This check did not retain a checkpoint or select either repetition. It is an engineering reproducibility check, not evidence of policy quality or control performance.

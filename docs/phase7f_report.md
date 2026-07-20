# Phase 7F — Stage I Paper-Grounded Deterministic PK/PD Reconstruction

## Outcome

Stage I is implemented as a new scientific core inside `vitaldb_state_selection.pkpd`. The implementation is derived from the versioned Protocol v1.3.2 evidence inventory and the explicit MC-001 through MC-009 approvals. No legacy source file is copied or imported.

The public boundary comprises a validated `PatientProfile` and `Sex` model category, James LBM, Schnider and Minto parameters, an immutable amount/Ce state, exact zero-order-hold transitions, a pure dual-drug simulator, one-second diagnostic snapshots, and the deterministic combined BIS response. Public infusion arguments carry drug-specific units in their names.

## Validation outcome

All dedicated parameter, dynamics, causality, unit, BIS, source-integrity, and artifact tests pass. Exact 10-second transitions agree with two 5-second and ten 1-second transitions within numerical roundoff, and with a test-only high-accuracy solve_ivp configuration within the prespecified tolerance. The sole sensitivity implementation is the closed, non-default Minto `f12=0.030` comparison.

## Research boundary

The frozen cohort remains 2,460 cases and 2,415 subjects, and the P0/P1 × S0/S1 design remains unchanged. Phase 7F does not read VitalDB raw signals or subject metadata and creates no split, test seal, modeling array, environment, observation adapter, reward, action adapter, PPO component, checkpoint, training run, or evaluation result. MC-010 through MC-034 remain pending. Phase 7G is not started.

# Phase 7F Stage I Human Decision Record

## Authority and scope

This record applies only to the paper-grounded deterministic PK/PD scientific core. It does not approve an anesthesia environment, an observation adapter, a reward, an action adapter, a subject split, or PPO.

## Approved MC-001 through MC-009

- MC-001: the James lean-body-mass term uses `(weight_kg / height_cm)^2`. This is recorded as a primary-source-informed typography correction to the Yun print.
- MC-002: Minto Cl1 uses `f18=55`; the undefined `h18` print is not implemented.
- MC-003: primary Minto `f12` is `0.0301`. The Yun `0.030` value exists only as the named, non-default `sensitivity_yun_0.030` configuration.
- MC-004: propofol uses mg, mg/min, and mg/L. Remifentanil uses microgram, microgram/min, and microgram/L. The drugs are not coerced to one mass unit.
- MC-005: constant-infusion transitions use an exact zero-order-hold augmented matrix exponential. Forward Euler is not a primary method.
- MC-006: the core accepts any finite positive duration, converts seconds to the minute-based model explicitly, supports an exact 10-second transition, and provides exact one-second diagnostic snapshots without requiring substeps for the 10-second result.
- MC-007: Stage I synthetic validation starts A1, A2, A3, and Ce at zero. This is an induction-oriented engineering reset, not a disclosed Yun reset and not a maintenance initializer.
- MC-008: Gaussian BIS noise is disabled. No noise interface is created.
- MC-009: random effect-site concentration drop is disabled. No drop sensitivity implementation is created.

## Still pending

MC-010 through MC-034 remain `recommended_pending_human_approval`. In particular, the `Sex` enum used by the published LBM equations is not the MC-032 PPO tensor encoding.

## Claim boundary

The authorized description is “paper-grounded deterministic PK/PD reconstruction” with “synthetic numerical validation.” This component is research-only. It is not an exact laboratory or unpublished implementation reproduction, a clinical validator, a safety claim, a patient dosing recommendation, or a reproduction of Yun figures.

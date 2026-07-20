# Phase 7F Deterministic PK/PD Scientific Validation

## Implemented equations and units

The scientific core implements the Schnider propofol and Minto remifentanil three-compartment amount equations, `Cp=A1/V1`, the first-order effect-site equation, and the Yun/Bouillon combined deterministic BIS equation. Exact symbols, constants, units, source IDs, approved corrections, and implementation paths are recorded in the versioned constant, unit, and equation-provenance registries.

The minute-based system matrix contains A1, A2, A3, and Ce. For a constant infusion over `duration_seconds`, the duration is divided by 60 and an augmented matrix exponential advances the state exactly. No Euler method or mandatory one-second substep is used. Negative values below `-1e-10` are rejected; roundoff values within that numerical tolerance are set to zero.

## Synthetic profiles and tolerances

Three fixed engineering profiles were used: an adult male reference, an adult female reference, and an older-adult reference. They are explicitly synthetic and are neither VitalDB subjects nor clinical standards.

- Semigroup tolerance: maximum absolute error `1e-11`.
- Independent ODE comparison: SciPy DOP853, `rtol=1e-12`, `atol=1e-14`, accepted maximum absolute error `1e-9`.
- Observed maximum 10-second semigroup error: `4.440892098500626e-16`.
- Observed maximum exact-ZOH versus solve_ivp error: `3.3306690738754696e-16`.
- BIS monotonic-grid violations: `0`.
- Deliberate remifentanil 1000-fold unit regression ratio: `999.9999999999999`.

The independent ODE solver is test/validation-only and is not the primary transition implementation.

## f12 sensitivity

For the synthetic older-adult profile under a 600-second constant input, primary `f12=0.0301` produced remifentanil Ce `2.0928507042206266 microgram/L` and BIS `46.68564811060758`. The named sensitivity-only `f12=0.030` produced Ce `2.0922197150432895 microgram/L` and BIS `46.6869476505385`. The absolute differences were `0.0006309891773370602 microgram/L` and `0.0012995399309190248` BIS units. This comparison does not replace the primary value.

## Known limitations

The reset is synthetic and induction-oriented. No noise, effect-site random drop, maintenance initialization, environment transition order, reward, action adapter, remifentanil schedule, observation layer, subject split, training, or evaluation is implemented. The existing NumPy and SciPy runtime was used without dependency installation or dependency-file modification.

## Claim boundary

This is a paper-grounded deterministic PK/PD reconstruction with synthetic numerical validation and primary-source-informed corrections. It is research-only and is not clinically validated, clinically safe, a patient dosing recommendation, an exact laboratory implementation reproduction, an unpublished-code reproduction, or an exact reproduction of published figures.

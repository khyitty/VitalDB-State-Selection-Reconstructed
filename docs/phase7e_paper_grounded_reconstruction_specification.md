# Phase 7E — Paper-Grounded Reconstruction Specification

## Outcome

The implementation path is corrected from unavailable laboratory-code reuse to an independent reconstruction governed by public primary literature. This is a design specification, not an implementation or reproduction claim.

The machine-readable evidence inventory separates what Yun et al. (2023) explicitly discloses, what is explicit in cited primary sources, what can be derived without a new assumption, and what is missing, conflicting, or requires a human decision. Exact paper locations and source identifiers are retained for every row.

## Material source findings

- Yun 2023 provides the three-compartment and effect-site equations, Schnider and Minto parameter equations, h1–h17 and f1–f18, the combined BIS response, a Gaussian policy, a 10-second control interval, a target BIS of 50, a typical safe range of 40–60, a reward form, PPO/GAE loss structure, network descriptions, Adam, learning rate 0.001, a reported training epoch count of 10^6, and loss/L2 coefficients.
- The paper does not disclose the numerical integration step or method, reward α, LOWESS span and causal edge handling, cumulative-history window W, full reset state, termination rule, or Yun-study γ, λ, PPO clip ε, batch size, and rollout length.
- The printed Yun LBM equations omit the square in the James term, whereas the directly cited models use `(weight/height)^2`.
- Yun uses `h18` in one remifentanil clearance term although only f1–f18 exist; the surrounding Minto equation identifies the centering constant as f18.
- Yun reports f12 as 0.030, while the cited Minto parameterization reports 0.0301.
- Yun describes both drugs in mg/mg·min⁻¹ while its remifentanil half-effect concentration is 19.3 µg/L. The future implementation unit contract therefore requires approval.
- Yun 2023 names Gaussian BIS noise without parameters. Yun 2024 states `N(10, 0.4)` and an approximately 10% effect-site drug drop, but does not fully define the distribution parameter semantics or update rule. Neither is silently completed.

## Claim boundary

The future simulator may be described as a paper-grounded independent reconstruction only after its unresolved constants are approved and its synthetic scientific validation gates pass. It must not be described as the laboratory implementation, an exact unpublished-code reproduction, a clinical validator, or an exact reproduction of paper figures.

Phase 7E reads no raw VitalDB signal and does not access prediction outcomes. The source PDFs are external public references and are not copied into Git. Legacy repository access remains read-only and is limited to equation cross-checking; its artifacts and results are not reused.

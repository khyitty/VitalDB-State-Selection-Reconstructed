# Prespecified figures and tables plan

No interpretive result graphic is generated in Phase 8F. The tables below were
populated only from checksum-frozen aggregate results, without highlighting or
selecting a condition.

## Figures

1. **Study workflow.** Outcome-blind cohort audit → subject-level split and test seal → train-only templates/scalers → four equal-compute policies → four-model gate → paired sealed-test evaluation → aggregate freeze → publication renderer.
2. **2 × 2 experimental design.** Rows P0/P1 and columns S0/S1, with causal BIS visibility rules and 34/42 dimensions. No cell is highlighted.
3. **Observation and state flow.** Recorded BIS/SQI enters only the causal visibility processor; policy-applied propofol and exogenous remifentanil update the simulator and state; latent BIS supplies reward and evaluation outcomes.
4. **Final metric comparison.** Available as the checksum-frozen condition and contrast tables under `paper/generated/tables`; the fixed condition order is P0S0, P1S0, P0S1, P1S1.

## Tables

1. **Cohort and split.** Frozen totals, subject-level train/test counts, and zero-overlap checks.
2. **Experimental conditions.** P0/P1 rules, S0/S1 contents, common training configuration, and fixed evaluation contract.
3. **Training completeness.** Final timestep, seed, implementation SHA, four final-model checksums, explicit completion status, and zero test access during training; recorded in the frozen integrity and aggregate artifacts.
4. **Condition summaries for the 11 frozen metrics.** Units, subject count, mean, standard deviation, median, quartiles, minimum, and maximum; rendered in Markdown, CSV, LaTeX, and JSON.
5. **Five paired contrasts for each frozen metric.** Mean and median paired difference, paired bootstrap 95% CI, sign-flip p-value, Holm-adjusted p-value, and Cohen's dz; rendered without condition selection.

## Supplement

- Protocol, split seal, cohort, training-configuration, implementation, final-model, aggregate-source, and rendered-artifact hashes.
- Exact metric definitions and contrast coefficient table.
- Explicit case-accounting and failure-handling summary without public case-level rows.
- Software and environment versions.
- Renderer schema and synthetic validation record.

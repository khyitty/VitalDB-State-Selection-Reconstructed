# Observation Quality and State Representation in PPO-Based Propofol Infusion Control: A Prespecified 2 × 2 Simulation Study

## Abstract

**Background:** Automated propofol control must act on intermittently available, sometimes unreliable depth-of-anesthesia observations while accounting for patient and drug dynamics. The separate contributions of observation-quality preprocessing and controller state representation are not established by studies that alter both together.

**Objective:** To evaluate whether BIS observation-quality preprocessing and an enriched pharmacokinetic state affect PPO-based propofol control in a prespecified factorial simulation study.

**Methods:** We reconstructed a patient-specific propofol-remifentanil PK/PD simulator from published sources and derived frozen train and sealed-test cohorts from VitalDB. Four equal-compute conditions crossed two causal BIS preprocessing rules (P0 and P1) with two state representations (S0 and S1). Each policy used seed 42 and 1,000,000 environment timesteps. Final deterministic evaluation was prespecified on the same 490 sealed-test cases, with latent-BIS outcomes, case pairing, subject-level aggregation, paired bootstrap confidence intervals, paired sign-flip permutation tests, Cohen's dz, and Holm adjustment.

**Results:** All 490 sealed-test cases completed under each condition with no failed episode or silent exclusion. Subject-level mean absolute BIS deviation was 12.781, 5.421, 7.673, and 6.954 BIS points for P0S0, P1S0, P0S1, and P1S1, respectively; all 11 frozen outcomes and five paired contrasts are reported without condition selection.

**Conclusion:** The four prespecified policies were evaluated in the reconstructed simulator without selecting a best condition; the estimates apply to one fixed training seed and require external validation before clinical interpretation.

## Introduction

Propofol has a narrow practical control objective: inadequate dosing can leave hypnosis too light, whereas excessive dosing can deepen anesthesia unnecessarily and contribute to hemodynamic risk. Closed-loop systems seek to adjust infusion repeatedly in response to an electroencephalographic depth indicator. In this study, the control target was BIS 50 and the prespecified safety-range summary was the proportion of simulated time within BIS 40–60. These quantities are evaluation targets rather than claims of clinical deployment readiness.

Propofol does not act in isolation. Remifentanil changes the hypnotic response through pharmacodynamic interaction, and its exogenous clinical infusion history therefore represents a relevant disturbance in a propofol controller simulation. Published PK/PD models provide a mechanistic way to connect patient covariates, infusion histories, plasma and effect-site concentrations, and simulated BIS [@schnider1998; @minto1997; @bouillon2004]. Prior reinforcement-learning work has emphasized simulator construction, policy learning, and controller architecture [@yun2023; @yun2024].

A different problem occurs at the controller boundary: recorded BIS observations can be missing, stale, or accompanied by low signal quality. Changing the rule that makes BIS visible may alter the information available to a policy independently of changing the contents of the state vector. Conversely, adding recent-dose, cumulative-dose, and concentration features may affect policy behavior without changing BIS visibility. Combining these interventions in one condition would not identify their separate contributions.

We therefore prespecified a 2 × 2 design crossing a baseline causal observation rule with a signal-quality-aware rule and a 34-variable state with a 42-variable enriched state. The research question was whether BIS observation-quality preprocessing and added state features affect PPO-based propofol control, separately or jointly. The design, metrics, contrasts, compute budget, test cohort, and analysis plan were frozen before final evaluation.

## Methods

### Study source, cohort, and governance

VitalDB was used as the retrospective source of deidentified case metadata and physiological recordings [@vitaldb]. Eligibility was constructed through versioned, outcome-blind audits. The frozen cohort contained 2,460 cases from 2,415 subjects. A subject-level split made before modeling assigned 1,932 subjects (1,970 cases) to training and 483 subjects (490 cases) to testing, using split seed 20260720. Subject and case overlap were both zero. Test membership was sealed, and test-derived information was not used for training, scaler fitting, hyperparameter selection, checkpoint selection, or condition selection.

The earlier 98-case convenience sample and all artifacts derived from it were excluded. Its code and results were not used to determine eligibility, preprocessing, split membership, scaling, features, policies, or evaluation. Versioned manifests, source checksums, explicit failure rows, and Git exclusion rules separated scientific metadata from raw and private event-level data.

### PK/PD simulator

The simulator was independently reconstructed from the equations and parameters documented by Yun et al. and the cited primary PK/PD models [@yun2023; @schnider1998; @minto1997; @bouillon2004]. Patient covariates parameterized three-compartment propofol and remifentanil models and their effect sites. The pharmacodynamic layer combined propofol and remifentanil effect-site concentrations to generate latent BIS. This was a paper-grounded reconstruction, not a reuse of laboratory code, a legacy trained policy, or a claim of exact reproduction.

At each control step, the policy supplied a physical propofol action. The action was bounded by the frozen environment contract and applied to the simulator for a 10-second interval. Recorded remifentanil infusion was introduced as an exogenous, causal zero-order-hold disturbance. Actual clinical propofol infusion history was not injected into the online state or substituted for the policy action. Consequently, controller behavior after episode initialization arose from the policy-applied propofol history under a common patient and remifentanil scenario.

### Factorial observation and state conditions

The four conditions were evaluated in the fixed order P0S0, P1S0, P0S1, and P1S1. P0 applied no SQI gate and allowed the most recent causal BIS sample to remain visible for at most 30 seconds. P1 required an exact-timestamp SQI value of at least 50 and used a 20-second BIS staleness limit. Neither rule used a future BIS or SQI sample, nearest-time substitution, interpolation, smoothing, or retrospective filling.

S0 comprised 34 ordered features: age, binary sex, height, weight; six 10-second BIS-history positions with visibility masks and observation ages; six policy-applied propofol dose-history positions; and six exogenous remifentanil-rate-history positions. S1 preserved S0 as a strict prefix and added eight features: 60-second recent propofol and remifentanil doses, cumulative propofol and remifentanil doses, and propofol and remifentanil plasma and effect-site concentrations. SQI itself, rejection reason codes, and target BIS were not state-vector features. Separate S0 and S1 scalers were fitted on training data only; P0 and P1 reused the same scaler for a given state representation.

### PPO training

All conditions used the same PPO implementation and frozen hyperparameters [@schulman2017; @schulman2015]. The policy and value networks each had one 128-unit Tanh hidden layer, with a diagonal Gaussian continuous-action distribution. The common configuration used Adam, learning rate 0.001, rollout length 2,048, batch size 64, 10 optimization epochs per rollout, discount 0.99, GAE lambda 0.95, clipping 0.2, value coefficient 0.1, entropy coefficient 0, gradient-norm limit 0.5, and optimizer weight decay 0.001.

Training used seed 42 only and exactly 1,000,000 environment timesteps per condition. The same deterministic sequence over the 1,970 sealed training cases was used for all conditions. There was no early stopping, hyperparameter search, alternate-seed search, or performance-based checkpoint selection. Only the final 1,000,000-timestep model was eligible for final evaluation. The source study's report of 10^6 training epochs is not asserted to be exactly equivalent to 1,000,000 Stable-Baselines3 environment timesteps or to an identical number of optimizer updates.

### Sealed-test evaluation and outcomes

All four final policies were required to pass implementation-SHA, seed, timestep, configuration, and checksum gates before evaluation. Each policy was to be evaluated deterministically on the same ordered 490 sealed-test cases using identical patient profiles, remifentanil schedules, episode horizons, simulator constants, action bounds, and reward. Evaluation allowed no optimizer step, policy update, exploration noise, normalization fitting, or scaler update. Failed episodes were to remain explicit; silent exclusion was prohibited.

Control outcomes used simulator latent BIS rather than the controller's visible BIS observation. The 11 frozen metrics were: mean absolute BIS deviation; root mean squared BIS deviation; time in BIS 40–60; time below BIS 40; time above BIS 60; integrated absolute BIS error; maximum absolute BIS deviation; cumulative propofol amount; mean propofol infusion rate; mean absolute change between consecutive propofol rates; and cumulative episode reward. No additional outcome was introduced for this manuscript pipeline.

### Statistical analysis

Case-level metrics preserve the within-case four-condition pairing. For subjects with multiple cases, the prespecified analysis aggregates case metrics to the subject level before inference. The five frozen contrasts are P1S0−P0S0 and P1S1−P0S1 for preprocessing effects within state level; P0S1−P0S0 and P1S1−P1S0 for state effects within preprocessing level; and the factorial interaction `(P1S1−P1S0)−(P0S1−P0S0)`. Each contrast reports mean and median paired differences, a paired subject-level 95% bootstrap confidence interval, a two-sided paired sign-flip permutation p-value, Cohen's dz, and the prespecified Holm multiplicity adjustment. Condition order and contrast direction are fixed; the publication renderer does not rank conditions or select an interpretation.

### Software, reproducibility, and privacy

The repository versions protocols, schemas, implementation code, aggregate audit artifacts, and checksum inventories. Models, checkpoints, raw signals, private observation templates, runtime inputs, access ledgers, event-level evaluation rows, and local filesystem paths are Git-ignored and excluded from publication. A strict schema validates the final aggregate before rendering deterministic Markdown, CSV, LaTeX, and JSON outputs. The renderer rejects missing or duplicate conditions, metrics, or contrasts; wrong seed, timestep, or test accounting; nonfinite values; silent failure exclusion; and case-, event-, trajectory-, or private-path payloads.

## Results

No final four-condition evaluation result had been generated when this manuscript shell was frozen. Tokens below are machine-replaceable only after the aggregate checksum and primary tables have been frozen.

### Cohort integrity

The frozen cohort contained 2,460 cases from 2,415 subjects. The subject-level split assigned 1,970 cases from 1,932 subjects to training and 490 cases from 483 subjects to sealed testing, with zero subject and case overlap. Final evaluation accounting was `490` completed and `0` explicitly retained failures per condition.

### Training completeness

Final-model checksum verification was `verified for all four final models`. The four eligible final-model checksums are recorded in the frozen aggregate and supplement; no intermediate checkpoint was selected. Training completion details appear in Table 3.

### Primary 2 × 2 comparison

Mean absolute BIS deviation was `12.781`, `5.421`, `7.673`, and `6.954` BIS points for P0S0, P1S0, P0S1, and P1S1, respectively. Full descriptive statistics for all 11 frozen metrics are shown in Table 4.

### Preprocessing main-effect contrasts

Within S0, the P1−P0 paired difference in mean absolute BIS deviation was `-7.360` with 95% CI `-7.608 to -7.110`, Holm-adjusted p `0.002499`, and Cohen's dz `-2.6055`. The corresponding within-S1 quantities were `-0.719`, `-0.826 to -0.619`, `0.002499`, and `-0.5985`.

### State main-effect contrasts

Within P0, the S1−S0 paired difference in mean absolute BIS deviation was `-5.108` with 95% CI `-5.469 to -4.733`. Within P1, it was `1.533` with 95% CI `1.369 to 1.693`. Adjusted tests and effect sizes are reported in Table 5.

### Interaction

The prespecified interaction for mean absolute BIS deviation was `6.641`, 95% CI `6.289 to 6.979`, Holm-adjusted p `0.002499`, and Cohen's dz `1.7305`. Its direction, interval, and component cell estimates are reported without selecting a condition.

### Safety-range outcomes

Time within BIS 40–60 was `6888.8`, `10318.4`, `10080.5`, and `10174.8` seconds. Below-range, above-range, integrated-error, and maximum-deviation summaries are provided in Table 4 and their paired contrasts in Table 5.

### Propofol utilization and action smoothness

Cumulative propofol amount and mean infusion rate are reported for each condition in Table 4. The prespecified action-change metric was `0.0044`, `0.2409`, `0.0087`, and `0.0128` mg/min. These measures are presented alongside BIS-control outcomes without forming a composite optimization target.

### Robustness and completeness

Silent exclusions numbered `0`. The final aggregate contained `44` condition-metric rows and `55` contrast rows. Sensitivity to the single fixed training seed was not evaluated and is retained as a limitation.

## Discussion

This study was designed to separate two controller-design choices that are often changed together: which causal BIS observations are exposed to the policy and which patient/drug-history variables are represented in its state. The factorial contrasts therefore address intervention effects within the other factor's level, while the interaction assesses whether their joint effect departs from additivity. Interpretation must follow the frozen contrast directions and uncertainty estimates, not a post hoc ordering of four condition means.

Any observed change in latent-BIS control would describe behavior inside the reconstructed simulator under the sealed test scenarios. It would not by itself demonstrate bedside safety, clinical benefit, or robustness to institutions, devices, artifacts, or workflows outside VitalDB. Propofol utilization and action smoothness should be considered alongside error and range metrics because a controller may exchange one property for another.

The result-contingent paragraphs were written before results and are stored separately in `discussion_scenarios.md`. They are alternative interpretation aids, not hypotheses to select by convenience. Only the scenario consistent with the frozen aggregate, full uncertainty estimates, and clinical context may later be adapted, and unused scenarios remain part of the transparent prespecification record.

### Limitations

First, training used one seed, so the experiment does not quantify between-seed optimization variability. Second, the PK/PD environment is an independent paper-grounded reconstruction rather than a laboratory-authoritative implementation. Third, this is not clinical deployment validation. Fourth, 1,000,000 SB3 environment timesteps are not known to be exactly equivalent to the source paper's 10^6 epochs or optimizer updates. Fifth, VitalDB is a single-center retrospective source, limiting transportability. Sixth, outcomes use simulated latent BIS rather than observed clinical outcomes. Seventh, SQI ≥50 and the 20- and 30-second staleness limits are one frozen operational definition, not an established universal optimum. Eighth, no external dataset validation was performed. Finally, statistical significance, if present, must not be equated with clinical significance.

## Conclusion

The four prespecified policies were evaluated in the reconstructed simulator without selecting a best condition; the estimates apply to one fixed training seed and require external validation before clinical interpretation.

## Data, code, and reproducibility statement

Public repository content is limited to code, protocols, aggregate-safe manifests, schemas, tests, reports, and deterministic table-rendering tools. Raw physiological signals, private templates, runtime inputs, case-level and event-level evaluation outputs, models, checkpoints, and local paths are excluded. The public result tables passed their aggregate source-checksum, fixed-condition-order, complete-accounting, and privacy gates before release.

## References

Citation keys resolve through `references.bib`. Only sources already verified in the repository source registry are included; incomplete web-resource bibliography is marked TODO rather than inferred.

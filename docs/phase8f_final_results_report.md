# Phase 8E/8F final-results publication report

This outcome-reporting step used the already completed deterministic sealed-test
evaluation. It did not rerun an episode, alter a policy, refit a scaler, or select
a condition.

## Evaluation accounting

- Frozen condition order: P0S0, P1S0, P0S1, P1S1.
- Sealed-test cases: 490 per condition.
- Sealed-test subjects after prespecified within-subject case aggregation: 483.
- Complete case-condition rows consumed privately: 1,960.
- Failed episodes: 0 per condition.
- Silent exclusions: 0.
- Public case-level and event-level rows: 0.

All four final policies were deterministic seed-42 policies trained for exactly
1,000,000 environment timesteps. Their model SHA-256 values are recorded in the
frozen integrity artifact.

## Frozen statistical contract

The publication aggregate contains 44 condition-metric rows (four conditions by
11 frozen metrics) and 55 contrast rows (11 metrics by five prespecified paired
contrasts). Repeated cases were averaged within subject before inference. Each
contrast uses 2,000 subject-level paired bootstrap replicates, 2,000 two-sided
paired sign-flip replicates, Cohen's dz, and Holm adjustment within metric. No
metric, contrast, subgroup, seed, or favorable-condition rule was added after
evaluation.

Post-freeze verify-only initially exposed that contrast terms had been accumulated
by Python `set` iteration, making last-bit floating-point output dependent on the
process hash seed. The implementation now records the fixed accumulation order
P0S0, P0S1, P1S1, P1S0. This reproduces the already frozen aggregate and statistics
checksums exactly, changes no coefficient or result artifact, and makes independent
verify-only runs byte-identical.

## Integrity and privacy

- Private case-result SHA-256: `8fda4cb70251c319255251601c39d58205ccf62ac88a6a6a96b9d2b0cf8d1167`.
- Public aggregate SHA-256: `2939f9580a992ef8f43d9f57bc2c7c5a1159b147d3739a6a8809932ac81fcae1`.
- Public statistics SHA-256: `681926cb34830cf11391994dbc7d7c14352e94527c2f36549a6fe86547def6ff`.
- Private case rows published: false.
- Results interpreted: false.
- Best condition selected: false.

The aggregate passed the frozen Phase 8F schema. Its deterministic renderer
produced mutually consistent Markdown, CSV, LaTeX, and JSON tables, and the
manuscript population step replaced 37 placeholder occurrences through 36 exact
token mappings. Raw signals, private templates, runtime inputs, access ledgers,
case or subject identifiers, timestamps, models, checkpoints, and local paths are
not publication artifacts.

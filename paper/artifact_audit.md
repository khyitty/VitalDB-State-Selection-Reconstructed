# Final artifact audit

- Audited repository HEAD: `02291582a3c0668d983edcefa85afc78ed865854`
- Final-result freeze commit: `71156050465e64892032b475974787b196eb2c3f`
- Freeze commit timestamp: `2026-07-22T18:43:15+09:00`
- Public aggregate: `paper/generated/phase8e_aggregate_results.json`
  (`2939f9580a992ef8f43d9f57bc2c7c5a1159b147d3739a6a8809932ac81fcae1`)
- Public paired statistics: `paper/generated/phase8e_statistics_results.json`
  (`681926cb34830cf11391994dbc7d7c14352e94527c2f36549a6fe86547def6ff`)
- Finality evidence: 490 completed and 0 failed evaluations per condition,
  1,960 complete case-condition rows, four final models at exactly 1,000,000
  timesteps, fixed seed 42, frozen model hashes, and matching aggregate/statistics
  hashes in `phase8e_final_results_integrity.json`.
- Conditions: P0S0, P1S0, P0S1, and P1S1. P0 is permissive causal preprocessing;
  P1 is quality-aware causal preprocessing. S0 is the 34-dimensional observable
  history state; S1 is its 42-dimensional pharmacology-enriched superset.
- Evaluation cases: the same sealed 490 cases (483 subjects after prespecified
  within-subject aggregation) under all four configurations.
- Metrics: the 11 names frozen in `phase8e_metric_manifest.json`; figures use only
  mean absolute BIS deviation and time above BIS 60.
- Uncertainty: aggregate figure uses case-level IQR from the public aggregate;
  paired figure uses the implemented subject-paired bootstrap 95% confidence
  interval (2,000 replicates).
- Privacy boundary: public case-level rows = 0, public event-level rows = 0, and
  private case-result publication = false. No case rows or trajectories are
  copied into figure data.

The older Phase 8E readiness configuration and source snapshot retain
pre-execution flags (`actual_evaluation_started: false` and zero episode counts);
they document the pre-evaluation gate, not final outcome status. Finality is
instead established by the later final-results integrity and Phase 8F source
snapshot artifacts listed above.


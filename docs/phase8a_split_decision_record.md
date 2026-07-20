# Phase 8A Split Decision Record

## Authority and lineage

This human-approved decision uses the frozen Protocol v1.2 cohort while the
current reconstruction study protocol remains v1.3.2. The split artifact has
its own version, `phase8a-v1`; neither prior protocol artifact is modified.

## Fixed allocation

- Unit: exact public VitalDB `subjectid`.
- Targets: 1,932 train and 483 test subjects; no validation split.
- Strata: sex × repository-defined subject age group × subject case-count band.
- Quotas: exact 1/5 Hamilton largest remainder with canonical stratum tie order.
- Rank: SHA-256 of `20260720\0{stratum_key}\0{exact_subjectid}`.
- All cases follow their parent subject and all four P0/P1 × S0/S1 conditions
  use the same membership.

No alternate seed, balance optimization, outcome, signal, observation template,
normalization, simulator run, PPO run, or checkpoint is permitted. Membership
changes require a new human-approved protocol amendment. The public test seal is
an integrity mechanism, not secrecy.

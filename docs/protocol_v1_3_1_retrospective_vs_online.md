# Retrospective versus Online Preprocessing

Phase 6C answers whether logged VitalDB signals can be aligned causally on a retrospective grid. Its exact candidates remain immutable evidence:

- P0 source: `sqi_not_required__bis30s__drug120s`
- P1 source: `sqi_ge_50__bis20s__drug60s`

Protocol v1.3.1 answers what an online controller is allowed to observe. Its identifiers are deliberately different:

- P0 online: `P0_online_bis_permissive_v1`
- P1 online: `P1_online_bis_quality_v1`

SQI gating and BIS freshness carry forward as one bundled contrast. Drug-rate holds do not. Propofol history is the action actually applied by the controller; remifentanil history is the exogenous schedule actually applied by the environment. Both are invariant across P0 and P1.

The retrospective candidate counts do not imply online episode counts, online missingness, or a new cohort freeze. Protocol v1.2 remains the only frozen cohort definition. No existing Phase 6C or Protocol v1.3 file is overwritten by this amendment.

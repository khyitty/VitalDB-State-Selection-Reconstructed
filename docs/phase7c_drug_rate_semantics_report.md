# Phase 7C Drug-Rate Semantics Decision Support

## Decision-support conclusion

Status: `retrospective_only_not_valid_for_online_control`.

The inspected legacy environment defines propofol as the sole policy action, holds it for each 10-second environment interval, and records the applied internal rate in simulator state and history. Remifentanil is supplied by an environment-owned exogenous schedule and its internal rate is likewise recorded. No source inspected in this audit implements a monitor-derived delay, missingness process, or asynchronous observation for either rate.

Phase 6C's 120/60-second drug hold caps were retrospective causal alignment rules for logged VitalDB tracks. They do not establish that a future online controller fails to know its own applied propofol command or the environment's remifentanil schedule.

## Consequence

Applying retrospective hold caps to those controller-known internal rates would manufacture missingness and would not represent the audited legacy online control interface. Phase 7C therefore does not implement drug-rate staleness. The planned P0/P1 contrast must either:

- restrict the observation-quality difference to BIS/SQI and BIS staleness; or
- receive new documented evidence and human approval defining delayed rate observations available to the controller.

This is decision support, not a final Protocol v1.3 amendment. PPO execution remains blocked until the contrast is resolved.

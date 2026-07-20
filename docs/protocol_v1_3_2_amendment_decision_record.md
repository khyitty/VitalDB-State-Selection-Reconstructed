# Protocol v1.3.2 — Paper-Grounded Reconstruction Amendment

Status: human-directed amendment; specification only. Simulator implementation, dependency installation, split creation, and PPO execution remain unauthorized.

## Authority correction

Protocol v1.3.2 supersedes only the implementation-path decision in Protocol v1.3.1. It does not edit or erase the historical v1.3.1 record.

The former primary path, “laboratory code reuse / Path A,” is retired because no PPO, environment, simulator, configuration, training, or evaluation code can be obtained from the laboratory or professor. Work must not wait for or imply a future laboratory handoff.

The new primary path is **paper-grounded independent reconstruction** inside this repository. The implementation authority order is:

1. Yun et al. (2023), DOI `10.1016/j.compbiomed.2023.106739`.
2. Directly cited primary sources: Schnider propofol PK/PD, Minto remifentanil PK/PD, Bouillon interaction modeling, PPO, and GAE.
3. Yun et al. (2024), DOI `10.1109/TNNLS.2022.3190379`, only as auxiliary parameter or safety interpretation.
4. The legacy repository, read-only, only to detect implementation questions and compare equations.
5. Human decision for every value not publicly disclosed or affected by unresolved conflict.

Legacy source, checkpoints, trained policies, splits, scalers, selected features, prediction results, PPO metrics, best seeds, and 98-case results are not implementation authority and cannot be reused.

## Preserved design

- The confirmatory design remains P0/P1 × S0/S1.
- The frozen cohort remains 2,460 cases and 2,415 subjects.
- No cohort is regenerated or refrozen in Phase 7E.
- Prediction remains outside the confirmatory scope.
- Protocol v1.3.1 observation contracts remain unchanged unless a later versioned, human-approved amendment explicitly changes them.

## Missing-value rule

No undisclosed constant may be presented as a paper value. Every missing or conflicting value is recorded with its publication status, current Stable-Baselines3 default where applicable, legacy candidate as reference-only, a proposed study value, sensitivity risk, and `recommended_pending_human_approval` status.

## Phase 7E boundary

This phase creates only the amendment, evidence inventory, missing-constant register, staged implementation sequence, synthetic scientific-validation plan, tests, checksums, and status evidence. It creates no PK/PD implementation, Gymnasium environment, PPO wrapper, dependency lock, subject allocation, split, observation template, raw-data derivative, modeling array, checkpoint, training run, or evaluation result.

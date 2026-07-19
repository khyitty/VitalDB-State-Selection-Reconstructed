# Phase Status

This file records gate outcomes. A phase may advance only after its tests pass, its
diff and generated files are reviewed, no new scientific assumption is introduced,
no legacy 98-case artifact is used, and no model/feature-selection/PPO run occurs.

| Phase | Status | Evidence |
|---|---|---|
| 1 — Governance and skeleton | complete | 5 governance tests passed; schemas and protocol-source equivalence verified |
| 2 — Migration inventory | pending | — |
| 3 — Eligibility audit framework | pending | — |
| 4 — Random 25-case dry run | pending | — |
| Full cohort and later research | blocked by protocol | Human review required |

## Publication constraint

The GitHub CLI (`gh`) was not available in the execution environment at project
initialization. It is not required for this work. Each phase uses ordinary `git
push`; publication is complete only when that command succeeds and the remote ref
is verified.

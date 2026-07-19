# Phase Status

This file records gate outcomes. A phase may advance only after its tests pass, its
diff and generated files are reviewed, no new scientific assumption is introduced,
no legacy 98-case artifact is used, and no model/feature-selection/PPO run occurs.

| Phase | Status | Evidence |
|---|---|---|
| 1 — Governance and skeleton | complete | 13 governance tests passed; remote `main` verified at `02ea9d3` |
| 2 — Migration inventory | complete | 352/352 paths classified; 18 tests passed; remote `main` verified at `4a89b4d` |
| 3 — Eligibility audit framework | complete | 38 tests passed; remote `main` verified at `0246e77`; thresholds, units, TIVA, volatile aliases, and legacy overlap remain pending |
| 4 — Random 25-case dry run | complete | Fixed seed `20260719`; all 25 metadata rows and signal outcomes preserved; 12 checksum-complete and 13 explicit non-retryable failures; 44 tests passed; raw data remains ignored; remote phase commit verified at `2f0b0c8` |
| 5A — Full metadata and track inventory audit | complete | 56 tests passed; actual `/cases` and `/trks` snapshots; 6,388/6,388 manifest rows; zero API/parsing failures; 193 unapproved names remain pending; no legacy IDs or signals accessed; remote phase commit verified at `9456fe4` |
| 5B — Eligibility decision-support audit | complete | 67 tests passed; full 6,388-case descriptive accounting; 21 narrowly scoped research-relevant names; 3,289 exact-primary cases; no scenario selected; documentary units remain pending human review; remote phase commit verified at `4aaa585` |
| 5C — Targeted volatile-signal characterization | complete | 80 tests and the 13-source production first-N guard passed; unfrozen 3,219-case universe and 22,533 case×track rows complete; 9,059 raw files checksum-verified, partial-free, and Git-ignored; no rule selected; remote phase commit verified at `af0764b` |
| 5D — Volatile exposure rule sensitivity audit | validated; publication pending | 94 tests and the 15-source production first-N guard passed; 3,219 cases and 9,059 Phase 5C raw checksums verified; 18,119-file raw tree unchanged; one inverted anesthesia window preserved as an explicit warning; no rule or candidate selected |
| Full signal cohort and later research | blocked by protocol | Human review required |

## Publication constraint

The GitHub CLI (`gh`) was not available in the execution environment at project
initialization. It is not required for this work. Each phase uses ordinary `git
push`; publication is complete only when that command succeeds and the remote ref
is verified.

The Phase 1 root commit `d9e6cb7` was created immediately before the compliance
matrix instruction arrived. To honor the no-history-rewrite rule, the matrix and
stronger tests are recorded in a separate Phase 1 follow-up commit before the first
push.

The Phase 4 phase commit
`2f0b0c8f0124ed053dedb75656502953123448d1` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this status
follow-up was created.

The Phase 5A phase commit
`9456fe4c286ccca85f8a9b29cdc0f3389d84cac9` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this status
follow-up was created.

The Phase 5B phase commit
`4aaa585ce23493bc39f2d0c1c8647f1e40a87078` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this status
follow-up was created. The legacy repository remained at commit `9501b16` and tree
`60917f0`; its sole pre-existing untracked `debug.log` entry was unchanged.

The Phase 5C phase commit
`af0764baa189ef9f26d306de488cca450f903eeb` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this status
follow-up was created. The legacy repository remained at commit `9501b16` and tree
`60917f0`; its sole pre-existing untracked `debug.log` entry was unchanged.

## Failure record template

Fill this section for any failed phase gate or push. Do not delete a failed record.

- `failed_gate`:
- `failure_reason`:
- `commands`:
- `generated_files`:
- `remaining_work`:
- `local_commit_sha`:
- `push_error`:

## Failure records

### 2026-07-19 — Phase 2 independent commit gate

- `failed_gate`: Phase 2 staging before independent commit
- `failure_reason`: The required escalated Git index write was rejected because the execution environment reached its approval usage limit; retry is unavailable until 2026-07-25 18:54.
- `commands`: `git add -- PHASE_STATUS.md docs/compliance_matrix.csv docs/legacy_source_snapshot.json docs/migration_inventory_summary.md docs/migration_provenance.csv tests/test_governance.py tests/test_migration_inventory.py`
- `generated_files`: `docs/legacy_source_snapshot.json`, `docs/migration_inventory_summary.md`, `tests/test_migration_inventory.py`; modified inventory, compliance matrix, governance test, and this status file
- `remaining_work`: Stage the seven Phase 2 files, review the cached diff, commit as `Inventory legacy migration candidates`, push `origin main`, verify the remote SHA, and only then begin Phase 3.
- `local_commit_sha`: `02ea9d39a785e8cbb24918555771937e3dda416d` (Phase 1 tip; Phase 2 remains uncommitted)
- `push_error`: Not attempted because the commit gate failed; Phase 3 was not started.
- `resolution`: Approval capacity was restored. Commit `4a89b4da88003beced9dce082358b4ef5a634a66` was pushed and independently verified on `origin/main` before Phase 3 began.

### 2026-07-19 — Phase 4 publication follow-up gate

- `failed_gate`: Compliance-matrix test before the Phase 4 publication-status follow-up commit
- `failure_reason`: The external push requirement was marked `implemented` without an automated test. `GovernanceTests.test_compliance_matrix_does_not_overclaim_pending_requirements` correctly rejected that overclaim.
- `commands`: `python -m unittest discover -s tests -v`
- `generated_files`: Modified `PHASE_STATUS.md` and `docs/compliance_matrix.csv` only
- `remaining_work`: Return the external push requirement to `pending`, retain the manually verified remote SHA in this status file, rerun all tests, and publish only the corrected status follow-up.
- `local_commit_sha`: `2f0b0c8f0124ed053dedb75656502953123448d1`
- `push_error`: Not attempted for the invalid follow-up state; the Phase 4 phase commit itself had already pushed successfully.
- `resolution`: The external-state row was returned to `pending` while retaining the manually verified SHA as evidence; all 44 tests then passed.

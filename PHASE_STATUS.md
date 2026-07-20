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
| 5D — Volatile exposure rule sensitivity audit | complete | 94 tests and the 15-source production first-N guard passed; 3,219 cases and 9,059 Phase 5C raw checksums verified; 18,119-file raw tree unchanged; one inverted anesthesia window preserved as an explicit warning; no rule or candidate selected; remote phase commit independently verified at `34b7eb4` |
| 6A - Protocol v1.1 freeze and primary signal acquisition | complete | 106 tests and the 17-source production first-N guard passed; 3,219 pre-quality rows with 2,470 acquisition inclusions; fixed-seed 25-case preflight passed; 9,880/9,880 exact-track requests complete and checksum-verified; raw data remains ignored; no quality threshold cohort freeze split model Cp/Ce dose or PPO execution; remote phase commit verified at `15d35da` |
| 6B - Outcome-blind primary signal quality characterization | complete | 121 tests and the 19-source production first-N guard passed; 2,470 case rows and 9,880 case-track rows complete; all Phase 6A raw checksums and raw-tree state match before/after; permissive moderate and strict pass counts are 2,464 2,333 and 1,723 with no scenario selected; no API raw rewrite quality-rule selection cohort freeze split prediction Cp/Ce dose feature selection or PPO execution; remote phase commit verified at `d3bc24f` |
| 6C - Causal grid and prediction-window feasibility audit | complete | 138 tests and the 21-source production first-N guard passed; 2,470 cases by all 60 candidates yield 148,200 complete rows; usable-case counts range from 2,465 to 2,468 with no rule selected; all 9,880 source raw checksums and the 19,761-file raw tree match before/after; peak RSS was 221,642,752 bytes; no cohort freeze split model Cp/Ce feature selection or PPO execution; remote Phase 6C commit verified at `b8f010d` |
| 6D - Protocol v1.2 final preprocessing decision and cohort freeze | complete | 153 tests and the 23-source production first-N guard passed; selected `sqi_ge_50__bis20s__drug60s` with at least 120 usable endpoints; all 2,470 source cases yield 2,460 eligible and 10 excluded; eligible-ID checksum `f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd`; source raw 9,880 checksums verified and raw tree unchanged; no raw/API split modeling array prediction Cp/Ce feature selection or PPO execution; remote Phase 6D commit verified at `3421e84` |
| Phase 7 patient split and later research | blocked by protocol | Separate authorization and protocol required |

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

The Phase 5D phase commit
`34b7eb45360e7a0f183f4f845cd91f399a2eee59` was pushed with ordinary Git and
independently verified on remote `main` by the user before this status follow-up
was created.

The Phase 6A phase commit
`15d35dad656f931826255c8e1e0cf6deea69be83` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. The legacy repository remained at
commit `9501b16` and tree `60917f0`; its sole pre-existing untracked `debug.log`
entry was unchanged.

The Phase 6B phase commit
`d3bc24f975484e173da237b756c22dca8d897d54` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. The Phase 6A raw tree remained at
19,761 files and 2,673,762,558 bytes with zero partial files. The legacy
repository remained at commit `9501b16`, tree `60917f0`, and its sole
pre-existing untracked `debug.log` entry.

Phase 6C execution note: the first production invocation completed the 9,880-file
pre-analysis checksum pass and then stopped before case analysis because the
Windows peak-RSS probe lacked an explicit process-handle type. It made no API
request, raw write, or official artifact. The single 299-byte hidden atomic
temporary file was identified and removed. After the Windows API signature was
fixed and its RSS result tested, the complete production run passed both raw
checksum passes and every phase gate. This recovered engineering failure did not
change a scientific rule or case decision.

The Phase 6C phase commit
`b8f010dcc67497f77e26cee53094819f2f5d6cd9` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. The committed change contains no raw
file or modeling array and leaves the legacy repository state unchanged.

The Phase 6D phase commit
`3421e84c59ce23b14a30ffc415b5199b641be9fa` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. The committed change contains the
approved final cohort manifest and case-ID artifacts, contains no raw file or
modeling array, and leaves the legacy repository state unchanged.

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

### 2026-07-20 — Phase 6C independent commit gate

- `failed_gate`: Stage the validated Phase 6C-only change set for its independent commit
- `failure_reason`: The managed execution environment rejected the required Git-index write because its automatic approval reviewer was out of credits. The workspace `.git` directory is read-only without that approval. This was not a Git remote authentication failure.
- `commands`: `git add -- PHASE_STATUS.md README.md docs/compliance_matrix.csv scripts/verify_no_first_n_limit.py data/manifests/causal_grid_*.csv data/manifests/causal_grid_*.csv.gz data/manifests/causal_grid_*.json docs/causal_grid_window_feasibility_report.md scripts/run_causal_grid_feasibility_audit.py src/vitaldb_state_selection/cohort/causal_grid_feasibility.py tests/test_causal_grid_feasibility.py tests/test_causal_grid_feasibility_artifacts.py` (the actual rejected command enumerated every path explicitly and used no glob)
- `generated_files`: Phase 6C code and tests; eleven checksummed report/manifest/summary/source artifacts plus the checksum inventory; modified README, compliance matrix, production first-N guard, and this status file
- `remaining_work`: After Git-index write approval is restored, stage only the enumerated Phase 6C files, review the cached diff, commit, push ordinary Git to `origin/main`, independently verify the remote SHA, update this status record, commit and push the publication follow-up, then stop.
- `local_commit_sha`: `30064de6ee4eeea44b5a220be1e5f6ba7c53b4e4` (unchanged Phase 6B publication tip; all Phase 6C changes remain unstaged)
- `push_error`: Not attempted because the independent commit gate failed before commit; this is not a Git authentication error.
- `resolution`: Git-index write approval was restored. Exactly the 20 reviewed Phase 6C paths were staged, cached-diff reviewed, committed as `b8f010dcc67497f77e26cee53094819f2f5d6cd9`, pushed with ordinary Git, and independently verified on `refs/heads/main`. The failure record is retained for provenance.

### 2026-07-20 - Phase 6D publication approval gate

- `failed_gate`: Push the independently committed Phase 6D change to `origin/main`
- `failure_reason`: The managed execution environment required renewed explicit approval because the commit publishes a final cohort manifest and case-ID artifacts. This was not a Git authentication failure.
- `commands`: `git push origin main`
- `generated_files`: None; commit `3421e84c59ce23b14a30ffc415b5199b641be9fa` was already complete and the worktree remained clean.
- `remaining_work`: Obtain explicit approval for the named origin, commit SHA, cohort manifest, and case-ID artifacts; push with ordinary Git; independently verify the remote SHA; then publish this status follow-up only.
- `local_commit_sha`: `3421e84c59ce23b14a30ffc415b5199b641be9fa`
- `push_error`: Managed approval rejection before network publication; no remote authentication attempt occurred.
- `resolution`: The user explicitly approved publication to `https://github.com/khyitty/VitalDB-State-Selection-Reconstructed.git`. Ordinary Git push succeeded and `refs/heads/main` was independently verified at `3421e84c59ce23b14a30ffc415b5199b641be9fa` before this follow-up commit.

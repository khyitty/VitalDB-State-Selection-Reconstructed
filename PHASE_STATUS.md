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
| 7A - Subject linkage and patient-level split feasibility audit | complete | 167 tests and the 26-source production first-N guard passed; 2,460 cases map without ambiguity to 2,415 nonmissing subjects; subjectid missing 0 and case-to-subject ambiguity 0; cluster sizes are 1×2,378, 2×35, 3×1, and 9×1; 82 cases belong to repeated subjects; sex inconsistency warnings 0; linkage checksum `102ccc60d9f03a8bfe858e5862366ef0b49f80cef3dcc027dae94afface464f7`; count-only nearest case and subject targets are arithmetically feasible; no allocation selected and no split/test seal/outcome/raw/API/modeling/preprocessing fit; remote Phase 7A commit verified at `11cfa98` |
| 7B - Protocol v1.3 control-focused 2×2 study design | complete | 189 tests and the 28-source production first-N guard passed; frozen cohort remains 2,460 cases and 2,415 subjects; P0 `sqi_not_required__bis30s__drug120s` and P1 `sqi_ge_50__bis20s__drug60s`; conceptual S0/S1 and four future policy IDs; planned 1,932/483 subject counts and seeds 42 plus 7/42/84; simulator observation-quality layer requires new implementation and missing encoding architecture budget reward action bounds and allocation method remain human decisions; no split seal modeling array raw outcome dose Cp/Ce prediction feature selection PPO control metric or statistics execution; remote Phase 7B commit verified at `3e8faa86919cda47cadf59844987ebaf81ff435b` |
| 7C - PPO/Simulator reuse audit and minimal implementation plan | complete | 195 audit-scope tests passed (the three excluded scaffold tests were not run after scope correction); the audit utility passed its direct first-N scan; legacy PK/PD synthetic reset plus one 10-second step passed; environment and PPO imports explicitly failed on missing runtime dependencies; only reuse audit documents and a bounded read-only probe were committed; missing encoding remains pending human approval; drug-rate semantics classified retrospective-only; no split raw access real array committed simulator/PPO implementation checkpoint training or evaluation; remote phase commit verified at `03e8ec9f4d3eec640552146d7511867f6db39136` |
| 7D - Protocol v1.3.1 online observation amendment and workspace resolution | complete | 214 tests and the 29-source production first-N guard passed; the 14 excluded paths were backed up with exact copies and a binary patch then selectively removed; Protocol v1.3.1 removes online drug staleness, selects BIS Option B-minimal, freezes S0/S1 at 34/42 conceptual fields, and approves Path A; the numeric BIS age cap remains pending before implementation; no implementation, split, raw access, package change, or PPO execution; remote phase commit independently verified at `2290f559f2790938916a4eef35d316fc81d165c1` |
| 7E - Paper-Grounded Reconstruction Specification | complete | 233 tests and the unchanged 29-source production first-N guard passed; Protocol v1.3.2 retires laboratory-code Path A; 90 evidence rows and 34 missing-constant decisions remain documentary or pending as classified; the frozen 2,460-case/2,415-subject cohort and 2x2 design are unchanged; no simulator, environment, dependency, split, raw access, modeling array, training, evaluation, prediction, Cp/Ce reconstruction, feature selection, or PPO execution; remote phase commit independently verified at `dc05d46f4a0d34f2909d73c42a3b86a1f188cd65` |
| 7F - Stage I paper-grounded deterministic PK/PD reconstruction | complete | MC-001 through MC-009 approved for Stage I and MC-010 through MC-034 remain pending; 262 tests and the unchanged 29-source production first-N guard passed; three fixed synthetic profiles; maximum semigroup error `4.440892098500626e-16`, maximum exact-ZOH versus solve_ivp error `3.3306690738754696e-16`, BIS monotonic-grid violations 0, and remifentanil unit-regression ratio `999.9999999999999`; frozen 2,460-case/2,415-subject cohort and P0/P1 by S0/S1 design unchanged; no dependency change, raw or subject-metadata access, split, test seal, environment, observation adapter, reward, action adapter, PPO, model, checkpoint, training, or evaluation; remote phase commit independently verified at `12268fa086b7ff1926a27479eb114f6cf408a876` |
| 7G - Stage II dependency-free anesthesia environment core | complete | MC-010 through MC-018 and MC-031/MC-032 approved only for the synthetic Stage II core; P0/P1 causal BIS processing, exact-ZOH event partitioning, physical propofol actions, synthetic remifentanil schedules, latent-BIS reward, S0=34/S1=42, and four executable conditions implemented; five fixed synthetic scenarios, all 285 repository tests, and the unchanged 29-source first-N guard passed with latent/reward invariance; no dependency change, raw or subject access, actual template, split, test seal, PPO, model, checkpoint, training, evaluation, or statistics; remote Phase 7G commit independently verified at `a4968c0c66ba503e93bec85c04db6b8bda3c227b` |
| 7H - Stage III Gymnasium and Stable-Baselines3 PPO integration | validation complete; publication pending | Isolated SB3 2.8.0/Gymnasium 1.2.3 CPU runtime; MC-019 through MC-029 and MC-034 approved only as scoped; all four adapters/checkers/VecEnv/model initializations passed; four official 128-timestep smoke updates and two P0S0 determinism repetitions passed; 302/302 tests passed in the isolated RL venv, base discovery passed 302 with 9 optional-RL skips, and the unchanged 29-source first-N guard passed; no reward/BIS comparison, ranking, checkpoint, split, raw or subject access, actual template, real patient, final training, evaluation, or statistics |
| Phase 7I and later execution | blocked by protocol | MC-030 total training budget and MC-033 final seed execution remain pending; subject allocation, split/test-seal, actual template extraction, final PPO training, evaluation, and statistics require later explicit approval |

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

The Phase 7A phase commit
`11cfa98b75b8215efb2334c0c310709f136e0ced` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. The committed change contains the
approved public VitalDB deidentified subject linkage artifacts, no split or test
seal, no raw file or modeling array, and leaves the legacy repository unchanged.

The Phase 7B phase commit
`3e8faa86919cda47cadf59844987ebaf81ff435b` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. Protocol v1.3 freezes the control-focused
2×2 design while recording that its observation-quality layer requires new
implementation and its missing-data encoding remains unresolved. The committed
change contains no split, test seal, raw file, modeling array, prediction, dose,
Cp/Ce value, PPO execution, checkpoint, control result, or statistical result and
leaves the legacy repository unchanged.

The Phase 7C reuse-audit commit
`03e8ec9f4d3eec640552146d7511867f6db39136` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. The commit contains only audit and
planning artifacts plus a bounded read-only probe. It contains none of the local
full-scaffold changes excluded after the scope correction, and it creates no split,
raw access, real modeling array, checkpoint, PPO training, or evaluation result.

The Phase 7D online-observation-amendment commit
`2290f559f2790938916a4eef35d316fc81d165c1` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. The excluded scaffold remains preserved
in the verified external backup and is absent from the committed workspace. The
commit contains no split, raw access, template extraction, simulator/environment
implementation, dependency change, checkpoint, PPO training, or evaluation result.

The Phase 7E paper-grounded-reconstruction-specification commit
`dc05d46f4a0d34f2909d73c42a3b86a1f188cd65` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. It retires laboratory-code Path A only
through the versioned Protocol v1.3.2 amendment; it does not modify Protocol
v1.3.1 or create a simulator, environment, dependency lock, split, modeling array,
checkpoint, training run, or evaluation result. All undisclosed or conflicting
implementation decisions remain pending human approval.

The Phase 7F Stage I deterministic-PK/PD commit
`12268fa086b7ff1926a27479eb114f6cf408a876` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. It contains the paper-grounded
scientific core, synthetic numerical-validation artifacts, and MC-001 through
MC-009 Stage I decisions only. MC-010 through MC-034 remain pending, and the
commit contains no dependency change, VitalDB raw or subject-data derivative,
split, test seal, environment, observation adapter, reward, action adapter, PPO,
checkpoint, training run, or evaluation result.

The Phase 7G Stage II environment-core commit
`a4968c0c66ba503e93bec85c04db6b8bda3c227b` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. It contains only the synthetic Stage II
environment core, contracts, tests, and validation artifacts. It contains no
dependency change, VitalDB raw or subject-data derivative, actual observation
template, split, test seal, PPO, model, checkpoint, training, evaluation, or
statistical result. MC-019 through MC-030, MC-033, and MC-034 remain pending.

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

### 2026-07-20 - Phase 7H checker-warning classification

- `failed_gate`: First aggregate Phase 7H adapter validation run
- `failure_reason`: Gymnasium and SB3 emitted two semantically equivalent recommendations for a normalized continuous action space. The first classifier recognized only one exact wording and conservatively stopped on the second warning. All adapter transitions and checkers themselves had passed.
- `commands`: Isolated-venv execution of `scripts/run_phase7h_validation.py`
- `generated_files`: Partial decision and configuration JSON files only; no smoke summary, model, checkpoint, trajectory, or performance artifact was accepted from the stopped run.
- `remaining_work`: Classify both normalized-action recommendation wordings as expected and harmless under the explicitly physical action contract, then rerun the complete bounded validation.
- `local_commit_sha`: `66c603c4e80fecb1a5efd01b1669df147ee5380d`
- `push_error`: Not applicable; no Phase 7H commit or push existed.
- `resolution`: The classifier now uses the shared semantic phrase, all warning rows are explicit `expected_and_harmless`, and the complete adapter plus smoke validation passed.

### 2026-07-20 - Phase 7H correctness-only artifact assertion

- `failed_gate`: First combined RL integration and artifact test run
- `failure_reason`: One artifact test rejected the word `reward` anywhere in the smoke summary, including the required negative boundary flag `reward_or_bis_comparison_created: false`. The run rows themselves contained no reward or BIS value.
- `commands`: Isolated-venv targeted Phase 7H unittest command
- `generated_files`: None from the failed assertion; existing bounded smoke artifacts were unchanged.
- `remaining_work`: Restrict the absence assertion to condition run payloads while retaining the explicit false comparison flag, rebuild checksums, and rerun targeted and full suites.
- `local_commit_sha`: `66c603c4e80fecb1a5efd01b1669df147ee5380d`
- `push_error`: Not applicable; no Phase 7H commit or push existed.
- `resolution`: All targeted Phase 7H tests then passed; after the exact lock-reproduction test was added, 302/302 tests passed in the isolated RL venv and base discovery passed with 9 optional-RL skips.

### 2026-07-20 - Phase 7E initial test invocation path

- `failed_gate`: Initial targeted Protocol v1.3.2 test invocation
- `failure_reason`: The first direct module invocation omitted the repository's `src` import path, so test discovery could not import the new package module. This was an invocation error, not a scientific or artifact failure.
- `commands`: `python -m unittest tests.test_protocol_v1_3_2 -v`
- `generated_files`: None.
- `remaining_work`: Run the project-standard discovery command with `PYTHONPATH=src`, then run the complete repository suite.
- `local_commit_sha`: `99e32a8a74472ebb07620d280b215f89b21cfe12`
- `push_error`: Not applicable; no Phase 7E commit or push existed.
- `resolution`: The targeted Protocol v1.3.2 suite passed 19/19 under the project-standard source path.

### 2026-07-20 - Phase 7E governance and immutable-guard regression

- `failed_gate`: First complete repository test run for Phase 7E
- `failure_reason`: Two of 233 tests failed. New compliance rows incorrectly placed multiple test IDs in one field even though governance requires one resolvable test ID per implemented row. The Phase 7E source had also been added to the existing first-N guard script, changing a file checksum-sealed by Protocol v1.3.1.
- `commands`: `python -m unittest discover -s tests`
- `generated_files`: None; the test was read-only and did not regenerate research artifacts.
- `remaining_work`: Split combined compliance claims into independently tested rows, restore the immutable 29-source guard, keep Protocol v1.3.2 coverage in its dedicated specification tests, and rerun targeted plus complete tests.
- `local_commit_sha`: `99e32a8a74472ebb07620d280b215f89b21cfe12`
- `push_error`: Not applicable; no Phase 7E commit or push existed.
- `resolution`: Compliance rows now name one automated test each; the original guard checksum is restored; 44 targeted governance, Protocol v1.3.1, and Protocol v1.3.2 tests passed, followed by all 233 repository tests and the 29-source guard.

### 2026-07-20 - Phase 7D excluded-scaffold backup verification

- `failed_gate`: Verify byte-identical tracked reconstruction from the binary patch before workspace cleanup
- `failure_reason`: The binary patch passed `git apply --check` and applied successfully, but a clean `git archive` uses LF while the Windows worktree copies used CRLF, so the initial byte-hash comparison was stricter than patch semantics. A later verification attempt also stopped because untracked copy paths were implicit rather than explicit fields in the backup manifest.
- `commands`: Bounded PowerShell backup creation and verification using `git diff --binary`, SHA-256, `git archive`, and `git apply --check`; no repository reset or clean command was used.
- `generated_files`: External sibling backup only; five tracked working-file copies, nine untracked original copies, `tracked_changes.patch`, `manifest.json`, and `source_head.txt`. The backup is not committed.
- `remaining_work`: None for workspace cleanup. Exact copies provide byte recovery, while the patch independently passed application and normalized-content checks.
- `local_commit_sha`: `989dc909e7e2380d27c5fb1b3ab8601018ef68f7`
- `push_error`: Not applicable; this occurred before Phase 7D commit creation.
- `resolution`: The backup was strengthened with exact tracked working-file copies and explicit relative paths for all 14 copies. Final verification passed 14/14 exact copy hashes, patch application, and 5/5 normalized tracked reconstruction. Only the enumerated paths were then restored or removed, returning the worktree to clean state.

### 2026-07-20 - Phase 7D upstream checksum test format

- `failed_gate`: Initial targeted Protocol v1.3.1 amendment test suite
- `failure_reason`: One new test assumed both prior checksum inventories used the Protocol v1.3 row-list schema. Protocol v1.2 instead uses a direct path-to-hash object. The other 36 targeted tests passed.
- `commands`: `python -m unittest tests.test_protocol_v1_3_1 tests.test_protocol_v1_3_1_artifacts tests.test_governance tests.test_first_n_guard -v`
- `generated_files`: None from the failed test; no research artifact was regenerated from data.
- `remaining_work`: Validate each immutable upstream checksum inventory according to its actual versioned schema and rerun the targeted and full suites.
- `local_commit_sha`: `989dc909e7e2380d27c5fb1b3ab8601018ef68f7`
- `push_error`: Not applicable; no Phase 7D commit or push existed.
- `resolution`: The test now validates the Protocol v1.2 direct mapping and Protocol v1.3 row-list independently without modifying either upstream artifact.

### 2026-07-20 - Phase 7C scope correction and probe-output encoding

- `failed_gate`: Apply the revised audit-only Phase 7C boundary and generate its read-only source snapshot
- `failure_reason`: A full synthetic scaffold had started before the user's higher-priority scope correction arrived. Work stopped immediately. The first two read-only snapshot attempts then failed before artifact creation because Windows subprocess output decoding was implicit and Git rejected the legacy repository as dubious ownership under the sandbox account.
- `commands`: `python -m unittest tests.test_phase7c_observation tests.test_phase7c_simulator tests.test_phase7c_ppo -v`; `python scripts/audit_phase7c_reuse.py --output data/manifests/phase7c_source_snapshot.json` (two failed attempts, followed by one successful bounded run)
- `generated_files`: The out-of-scope scaffold files listed in `docs/phase7c_ppo_simulator_reuse_audit.md` remain uncommitted and excluded from Phase 7C staging. The failed snapshot attempts created no official artifact.
- `remaining_work`: Commit and publish only the revised audit documents, audit utility, synthetic probe tests, source/checksum artifacts, compliance rows, and this audit status; preserve and report the excluded scaffold changes without staging them.
- `local_commit_sha`: `54b5461edf7c18b010538047dca42f1d470c1e35` (unchanged verified Phase 7B publication tip when the correction arrived)
- `push_error`: Not applicable; no push had been attempted.
- `resolution`: The utility now fixes subprocess decoding and uses a command-local read-only `safe.directory` setting. Its bounded synthetic simulator step succeeded; environment/PPO import failures were preserved as audit evidence. No dependency was installed and no PPO update or checkpoint occurred.

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

### 2026-07-20 - Phase 7A publication approval gate

- `failed_gate`: Push the independently committed Phase 7A subject-linkage audit to `origin/main`
- `failure_reason`: The managed execution environment required renewed explicit approval because the commit publishes exact case-to-deidentified-subject linkage and metadata-derived subject grouping. This was not a Git authentication failure.
- `commands`: `git push origin main`
- `generated_files`: None; commit `11cfa98b75b8215efb2334c0c310709f136e0ced` was already complete and the worktree remained clean.
- `remaining_work`: Obtain explicit approval for the named public origin, commit SHA, and deidentified linkage artifacts; re-review prohibited information; push; independently verify the remote SHA; then publish this status follow-up.
- `local_commit_sha`: `11cfa98b75b8215efb2334c0c310709f136e0ced`
- `push_error`: Managed approval rejection before network publication; no remote authentication attempt occurred.
- `resolution`: The user explicitly approved public publication of the named deidentified subject-linkage artifacts and prohibited direct identifiers, raw signals, credentials, secrets, and local paths. Scope review passed, ordinary Git push succeeded, and `refs/heads/main` was independently verified at `11cfa98b75b8215efb2334c0c310709f136e0ced` before this follow-up commit.

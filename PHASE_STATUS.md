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
| 7H - Stage III Gymnasium and Stable-Baselines3 PPO integration | complete | Isolated SB3 2.8.0/Gymnasium 1.2.3 CPU runtime; MC-019 through MC-029 and MC-034 approved only as scoped; all four adapters/checkers/VecEnv/model initializations passed; four official 128-timestep smoke updates and two P0S0 determinism repetitions passed; 302/302 tests passed in the isolated RL venv, base discovery passed 302 with 9 optional-RL skips, and the unchanged 29-source first-N guard passed; no reward/BIS comparison, ranking, checkpoint, split, raw or subject access, actual template, real patient, final training, evaluation, or statistics; remote Phase 7H commit independently verified at `404379f64d5bdce66822c38528f25e0aab91d881` |
| 8A - Outcome-blind subject-level split and test integrity seal | complete | Source commit `22448d447d7e07941a3dc2139cb2eae0d76bd511`; 2,415 subjects allocated as 1,932 train and 483 test, yielding 1,970 train and 490 test cases; subject overlap 0 and case-to-parent split errors 0; `hamilton_stratified_sha256_rank_v1` with seed `20260720`; maximum absolute primary continuous SMD `0.029963981155984278` and balance warnings 0; public integrity-seal payload `6083be99567d5d7d4989ef3c9e35fc51255f614098697f289daac756d643f9af`; 329 base tests discovered with 320 passed and 9 expected optional-RL skips, existing 29-source and Phase 8A 3-source first-N guards passed, and 9 isolated RL tests passed; no raw signal, observation template, preprocessing array, normalization, real-subject simulator, outcome, PPO, model, or checkpoint access or creation; remote implementation commit independently verified at `6e32a1e563bae3df22f5870ce94d802d4d01802f` |
| 8B - Train-only VitalDB observation-template extraction and private template integrity store | complete | Source `f45a0ee6f1208f1f8202bc185a7a005701dfa3e0`; 1,970 train templates and 0 test templates; 3,940 checksum-matched logical raw accesses (1,970 BIS and 1,970 SQI), with 0 test and 0 drug access; raw BIS persisted false and SQI private only; public event-level values 0; same template used for P0/P1; private-store root `96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2`; P0 visibility 2,086,908/2,299,446 and P1 visibility 1,923,357/2,299,446 with zero-visibility templates 0; 354 base tests discovered with 345 passed and 9 existing optional-RL skips, 29/3/4-source first-N guards passed, and 9 isolated RL tests passed; private store ignored and untracked; no normalization, outcome, model, checkpoint, final PPO training, or evaluation; remote implementation commit independently verified at `45ba77801a37dff81ca5f3702f844e44c8e0a427` |
| 8C - Train-only patient runtime inputs and bounded PPO smoke | complete | Source `a7821b43b608180f52e471c4bd8247d60336d8ef`; 1,970 sealed-train profiles and exact RFTN20 schedules with 1,970 train and 0 test logical raw accesses; missing/invalid profiles 0 and approved fallback false; private runtime root `25ad8a860f6c9b0b45febec7ff7d0d0edf88c0f1953229c8d95e207508d3a606`; Phase 8B root unchanged; S0/S1 train-only scalers contain 34/42 fields and are shared across P pairs; all four actual-train reset/step checks and four seed-42 CPU 128-timestep PPO smoke updates passed without persistence or ranking; 373 base tests passed with 11 optional-RL skips, all 11 isolated RL tests passed, and the 29/3/4/3-source first-N guards passed; no test metadata/template/raw access, final training, evaluation, model, or checkpoint; remote implementation commit independently verified at `7cf84d11c054d8b9c6180d0cf0b20749b4ecba39` |
| 8D - Final PPO training infrastructure and launch | training infrastructure complete; final training launched/in progress | Source `00937a28681c8d1949f3bae3dcd74a5fbddd9b39`; final implementation `b782b5e4a9d418f6b907a87d046c4e9789a3e5f0` independently verified on remote `main`; final config freezes seed 42, 1,000,000 environment timesteps per condition, common PPO/optimizer settings, exact 100,000-step private checkpoints, and one common PCG64 train-case sequence; shard A is P0S0/P1S0 and shard B is P0S1/P1S1; all four 1,024-step real-train preflights passed with finite diagnostics, test access 0, and persistence 0; 388 base tests completed with 372 passed and 16 optional-RL skips, all 16 skipped RL tests passed in the isolated environment, and the corrected runner verify-only passed at the final implementation SHA; 29/3/4/3/3-source first-N guards pass; test evaluation and condition comparison are not started or performed |
| 8E - Sealed-test inputs and final evaluation | complete | Readiness implementation `8c752044320c3bd7360d23a0a98927c159f36e13`; all four checksum-pinned seed-42 one-million-timestep models passed the final gate; deterministic evaluation completed 490/490 cases under each of P0S0, P1S0, P0S1, and P1S1, yielding 1,960 paired case-condition rows with failed episodes 0 and silent exclusions 0; 490 test templates and runtime bundles remained private, train-only scalers were applied without fitting, and private output SHA-256 is `8fda4cb70251c319255251601c39d58205ccf62ac88a6a6a96b9d2b0cf8d1167`; no optimizer update, evaluation restart, public case/event row, or best-condition selection occurred |
| 8F - Manuscript and aggregate-results publication pipeline | complete; remote publication pending | Starting source `1964398103a344110b806e82b15de30c5d15f299`; the authorized aggregation boundary consumed all 1,960 private rows, preserved four-condition pairing, aggregated 490 cases to 483 subjects before inference, and emitted 44 condition-metric plus 55 prespecified contrast rows; aggregate SHA-256 `2939f9580a992ef8f43d9f57bc2c7c5a1159b147d3739a6a8809932ac81fcae1` and statistics SHA-256 `681926cb34830cf11391994dbc7d7c14352e94527c2f36549a6fe86547def6ff`; deterministic Markdown/CSV/LaTeX/JSON outputs and 37 exact manuscript token replacements verified; public case/event rows 0, interpretation false, best-condition selection false, and no full-suite rerun |

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

The Phase 7H Stage III integration commit
`404379f64d5bdce66822c38528f25e0aab91d881` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. It contains the optional isolated RL
dependency contracts, Gymnasium adapter, SB3 configuration and bounded synthetic
smoke evidence only. The ignored `.venv-phase7h` and all in-memory models remain
untracked. No raw or subject-data derivative, actual observation template, split,
test seal, persistent checkpoint, full training, evaluation comparison, or
statistical result is included. MC-030 and MC-033 remain pending.

The Phase 8A outcome-blind subject-split implementation commit
`6e32a1e563bae3df22f5870ce94d802d4d01802f` was pushed with ordinary Git, and
`refs/heads/main` was independently observed at that exact SHA before this
publication-status follow-up was created. The public artifacts contain official
VitalDB deidentified subject/case membership and integrity metadata only. They
contain no direct identifier, raw physiological signal, BIS/SQI/drug-rate
time-series value, observation template, preprocessing array, model, checkpoint,
credential, local absolute path, legacy artifact, or unrelated file.

The final Phase 8D training implementation commit
`b782b5e4a9d418f6b907a87d046c4e9789a3e5f0` was pushed with ordinary Git, and
local HEAD, `refs/remotes/origin/main`, and the independently queried remote
`refs/heads/main` were all observed at that exact SHA before this launch-status
follow-up was created. Runner verify-only passed at the clean implementation
commit with both shard-A conditions incomplete, test access zero, and no Phase 8D
private output present. This records the authorized shard launch; it does not
claim completed training, test evaluation, or condition comparison.

The Phase 8E sealed-test evaluation-readiness implementation commit
`8c752044320c3bd7360d23a0a98927c159f36e13` was pushed with ordinary Git, and
local HEAD, `refs/remotes/origin/main`, and the independently queried remote
`refs/heads/main` were all observed at that exact SHA before this status-only
follow-up was created. The implementation prepares private sealed-test inputs and
evaluation infrastructure only; it executes zero real-model episodes, performs no
condition comparison, selects no best model, and does not access Shard B output.

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

### 2026-07-20 - Phase 8A pre-generation immutable first-N artifact

- `failed_gate`: First complete base-suite run before official Phase 8A generation
- `failure_reason`: Adding the Phase 8A production files to the historical 29-source first-N script changed a file protected by the immutable Protocol v1.3.1/v1.3.2 checksum inventories. Removing those entries with the patch tool temporarily changed two mixed line endings even though the semantic Git diff was empty; the prior checksum tests correctly stopped the gate.
- `commands`: Base `unittest` discovery and the Protocol v1.3.1/v1.3.2 checksum tests
- `generated_files`: Phase 8A code and tests only; no official Phase 8A split artifact existed and no raw or outcome data was accessed.
- `remaining_work`: Restore the historical script byte-for-byte, put the three new sources under a separate Phase 8A first-N guard, and rerun the prior checksum tests before official generation.
- `local_commit_sha`: `22448d447d7e07941a3dc2139cb2eae0d76bd511`
- `push_error`: Not applicable; no Phase 8A commit or push existed.
- `resolution`: The historical script was restored to its exact 2,893-byte SHA-256 `f41a8882d1f328d67dd7c2d79bf6ee953f51534a4c6558533be1cebef40daf09`. Its 29-source guard and the separate 3-source Phase 8A guard both pass; all protected prior inventories remain unchanged.

### 2026-07-20 - Phase 8A import-boundary test classifier

- `failed_gate`: First post-generation Phase 8A artifact and access-boundary test run
- `failure_reason`: One new AST test treated the repository package prefix `vitaldb_state_selection` as though it were an import of the external `vitaldb` API. The production modules imported only the repository's own split helpers and did not import a network, raw-data, PK/PD, environment, Gymnasium, SB3, or PPO module.
- `commands`: Phase 8A targeted `unittest` suite
- `generated_files`: The already sealed Phase 8A manifests remained byte-identical; no split regeneration occurred.
- `remaining_work`: Match forbidden external module names and forbidden internal package segments exactly, update only the test checksum entry, then rerun verify-only, artifact, guard, full base, first-N, and isolated RL checks.
- `local_commit_sha`: `22448d447d7e07941a3dc2139cb2eae0d76bd511`
- `push_error`: Not applicable; no Phase 8A commit or push existed.
- `resolution`: The classifier now distinguishes `vitaldb_state_selection` from external `vitaldb`. All 27 Phase 8A tests and the complete 329-test base discovery passed with only the 9 expected optional-RL skips.

### 2026-07-21 - Phase 8A publication risk approval gate

- `failed_gate`: First Phase 8A implementation push attempt
- `failure_reason`: The managed safety reviewer stopped execution before Git authentication because the commit publishes public deidentified subjectid/caseid split membership and required explicit approval after that disclosure risk was stated.
- `commands`: `git push origin main`
- `generated_files`: None; local implementation commit `6e32a1e563bae3df22f5870ce94d802d4d01802f` and its clean worktree were preserved.
- `remaining_work`: Obtain informed explicit approval for the exact public origin, commit, and allowed artifact scope; then push, independently verify the remote SHA, and create only the publication-status follow-up.
- `local_commit_sha`: `6e32a1e563bae3df22f5870ce94d802d4d01802f`
- `push_error`: Managed safety-review rejection before Git authentication; not a remote authentication failure.
- `resolution`: The user explicitly approved publication after acknowledging that official VitalDB deidentified subjectid/caseid split membership would be public and enumerated prohibited content. A renewed scope review passed, ordinary Git push succeeded, and `refs/heads/main` was independently verified at the implementation SHA before this follow-up.

### 2026-07-21 - Phase 8B protected Phase 8A verify-only regression gate

- `failed_gate`: Required targeted Phase 8B and existing Phase 8A regression suite before the Phase 8B implementation commit
- `failure_reason`: `Phase8AArtifactTests.test_verify_only_is_byte_identical_and_generation_is_refused` invokes `scripts/run_phase8a_subject_split.py --verify-only`, whose protected source gate requires the pre-Phase-8A starting HEAD `22448d447d7e07941a3dc2139cb2eae0d76bd511`. The current verified main is `f45a0ee6f1208f1f8202bc185a7a005701dfa3e0`, so that historical verify-only command raises `RuntimeError: Phase 8A starting HEAD mismatch`. Phase 8A source, test, and checksum inventory are protected and were not modified.
- `commands`: `python -m unittest tests.test_phase8b_train_raw_access tests.test_phase8b_train_observation_templates tests.test_recorded_observation_template tests.test_phase8b_artifacts tests.test_phase8a_subject_split tests.test_phase8a_artifacts tests.test_split_guard -v`
- `generated_files`: Ignored private Phase 8B store with 1,970 complete train templates, 0 test templates, 3,940 complete train BIS/SQI logical accesses, and root SHA-256 `96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2`; uncommitted Phase 8B code, tests, aggregate-only public summaries, schema, reports, and checksum inventory. No private or raw file entered Git tracking.
- `remaining_work`: Resolved; complete the reviewed Phase 8B implementation publication and remote-verification follow-up.
- `local_commit_sha`: `f45a0ee6f1208f1f8202bc185a7a005701dfa3e0` (unchanged Phase 8A publication tip; all Phase 8B changes remain uncommitted)
- `push_error`: Not attempted because a required test failed; this is not a Git authentication or network failure.
- `resolution`: The generation-only exact-HEAD/source-ref gate had also been called by verify-only. Verify-only now requires the Phase 8A starting commit to be an ancestor of both current HEAD and `refs/remotes/origin/main`, while generation still requires both refs to equal the exact starting commit and continues to refuse existing official artifacts. Phase 8A membership, seed, creation timestamp, manifests, and seal remain byte-identical; only the script entry in the Phase 8A artifact inventory changed. The previously failing exact test, all 27 Phase 8A targeted tests, all 25 Phase 8B targeted tests, the 354-test base suite with 9 existing optional-RL skips, all three first-N guards, and 9 isolated RL tests passed with no waiver or expected failure.

### 2026-07-21 - Phase 8C regression gate

- `failed_gate`: First complete base-suite run after the train-only runtime-input artifacts were built
- `failure_reason`: Two non-scientific regressions remained: the six new compliance rows used two semicolon-separated test names where governance requires one resolvable test per row, and accidental additions to historical Phase 7G/7H checksum inventories changed the Phase 8A reconstructed source snapshot. Phase 8A membership and seal, Phase 8B templates, Phase 8C private bundles, and all raw files were unchanged.
- `commands`: Complete base `unittest` discovery followed by the exact governance, Phase 8A verify-only, and Phase 8C inventory tests
- `generated_files`: No private artifact was regenerated and no raw signal was reopened for extraction; only public metadata/code under the approved Phase 8C scope remained in the worktree.
- `remaining_work`: Resolved; review the explicit public change set, publish the Phase 8C implementation commit, independently verify remote `main`, and then publish the status-only follow-up.
- `local_commit_sha`: `a7821b43b608180f52e471c4bd8247d60336d8ef` (unchanged Phase 8B publication tip; Phase 8C remains uncommitted)
- `push_error`: Not applicable; publication had not been attempted.
- `resolution`: Each compliance row now references exactly one existing automated test, and the unintended Phase 7G/7H inventory additions were removed without changing historical source files. Phase 8A verify-only is byte-identical and generation remains refused. The repeated complete suite passed all 373 tests with 11 existing/declared optional-RL skips; all 11 skipped RL tests passed in the isolated environment, all four first-N guards passed, and Phase 8A/8B/8C inventories verified. Waived tests and expected failures are zero.

### 2026-07-21 - Phase 8D targeted regression gate

- `failed_gate`: First Phase 8D targeted test and first-N guard run after the bounded preflight
- `failure_reason`: The checkpoint directory scan also matched its own `checkpoint_manifest.json` file, and the historical first-N guard treated the local Git commit variable name `head` as a prohibited case-limit identifier. Neither issue affected PPO configuration, preflight outputs, private roots, test access, or training state.
- `commands`: Isolated Phase 8D targeted `unittest`, public-artifact verify-only, and Phase 8D first-N guard
- `generated_files`: Aggregate-only Phase 8D preflight/protocol artifacts; no model, checkpoint, optimizer state, training progress, or final-training timestep was persisted.
- `remaining_work`: Resolved; publish the reviewed infrastructure, verify the remote implementation SHA, publish the launch-status follow-up, and only then launch shard A from that exact commit.
- `local_commit_sha`: `00937a28681c8d1949f3bae3dcd74a5fbddd9b39` (unchanged Phase 8C publication tip; Phase 8D remains uncommitted)
- `push_error`: Not applicable; publication had not been attempted.
- `resolution`: The scan now skips only the exact manifest filename while continuing to reject malformed checkpoint paths, and the Git variable was renamed without changing its equality gate. The repeated Phase 8D targeted suite passed 15/15, the related isolated Phase 8C/7H/8D suite passed 39/39, all first-N and artifact gates passed, and the complete base suite finished 388 tests with 372 passed plus 16 optional-RL skips. All 16 skipped tests passed in the isolated runtime; waived tests and expected failures are zero.

### 2026-07-21 - Phase 8D post-publication runner gate

- `failed_gate`: First shard A runner verify-only invocation at the independently verified initial infrastructure commit
- `failure_reason`: The gate compared the sealed ordered train-ID checksum to the CSV file-byte checksum. Those are intentionally different checksum representations, so the runner failed closed before creating an output directory, opening a runtime case, or starting training.
- `commands`: Isolated `scripts/run_phase8d_final_training.py --shard A --expected-git-sha <INITIAL_INFRASTRUCTURE_SHA> --total-timesteps 1000000 --seed 42 --resume --verify-only`
- `generated_files`: None; Phase 8A membership/seal and Phase 8B/8C private stores were unchanged, and Phase 8D private training output remained absent.
- `remaining_work`: Validate the sealed `sha256_sorted_train_case_ids` field directly, add a regression test, publish the corrected final implementation SHA, independently verify it, and only then create the launch-status follow-up.
- `local_commit_sha`: `c866ab25c8c5c88d6bb6c96d3a8bfd5aa131da0b`
- `push_error`: Not applicable; the initial infrastructure commit had already pushed successfully, while training had not started.
- `resolution`: The gate now compares like-for-like against the unchanged Phase 8A test-seal field. The runtime store still constructs its fail-closed SplitGuard from the complete sealed manifests, and no file checksum, split membership, seed, PPO configuration, private root, or training budget changed.

### 2026-07-21 - Phase 8E initial targeted regression

- `failed_gate`: First Phase 8E targeted unit-test invocation before private extraction
- `failure_reason`: The synthetic template access fixture lacked the production resume-ledger method, and the base environment correctly lacked optional Gymnasium/SB3 dependencies required by evaluation integration imports.
- `commands`: Base and isolated targeted Phase 8E unittests
- `generated_files`: No production test template or runtime bundle existed when the tests failed.
- `remaining_work`: Resolved; the fixture now implements verified resume bookkeeping and RL-dependent tests use the repository's established optional-skip/base plus isolated-pass pattern.
- `local_commit_sha`: `eb11dedfb644f41ac587d29156a2ec0dea007001`
- `push_error`: Not applicable; publication had not been attempted.
- `resolution`: Four non-RL tests passed in base, five RL-dependent tests were declared optional there and all five passed in `.venv-phase7h`. No test was waived or converted to an expected failure.

### 2026-07-21 - Phase 8E historical inventory regression

- `failed_gate`: First combined relevant Phase 8A/8B/8C/7H/8D/8E regression run
- `failure_reason`: Two historical Phase 8C/8D inventory assertions still contained the pre-Phase-8E byte count and SHA-256 for `docs/compliance_matrix.csv`. All 90 other targeted tests passed or produced only the six established optional-RL skips; no membership, seal, private root, model, or scientific artifact mismatch occurred.
- `commands`: Targeted base `unittest` command for the relevant Phase 8A through Phase 8E modules, followed by the two exact failing inventory tests and the Phase 8C/8D/8E inventory verifiers.
- `generated_files`: None from the failed tests. The only resolution changes were the `docs/compliance_matrix.csv` entries in the Phase 8C and Phase 8D public checksum inventories.
- `remaining_work`: Resolved; run the complete base and isolated-RL suites and publication gates.
- `local_commit_sha`: `eb11dedfb644f41ac587d29156a2ec0dea007001`
- `push_error`: Not applicable; publication had not been attempted.
- `resolution`: Both historical inventories now checksum the current compliance matrix. The two exact tests pass, and all three Phase 8C/8D/8E inventory verify-only commands pass without changing any scientific artifact.

### 2026-07-22 - Phase 8E actual sealed-test evaluation and Phase 8F result freeze

- `gate`: The already running authorized Phase 8E process exited with code 0 after 1,960 deterministic episodes: 490/490 under each frozen condition and failed episodes 0.
- `commands`: Read-only completion collection for the existing process, result-freeze verify-only, Phase 8F renderer verify-only, manuscript token-map verification, targeted Phase 8E/8F tests, and Git privacy checks. The evaluation, private extraction, and full test suite were not rerun.
- `generated_files`: Publication-safe aggregate and statistics JSON, integrity and source snapshots, deterministic Markdown/CSV/LaTeX/JSON tables, an exact manuscript token map, the populated manuscript, tests, and reports. Private case rows remain ignored and untracked.
- `remaining_work`: Explicitly stage only approved public files, commit, push ordinary Git to `origin/main`, and independently compare local, remote-tracking, and actual remote SHAs.
- `local_commit_sha`: `1964398103a344110b806e82b15de30c5d15f299` at evaluation completion; publication changes were initially uncommitted.
- `push_error`: Not applicable before the publication commit.
- `resolution`: Aggregate and statistics bytes are frozen at SHA-256 `2939f9580a992ef8f43d9f57bc2c7c5a1159b147d3739a6a8809932ac81fcae1` and `681926cb34830cf11391994dbc7d7c14352e94527c2f36549a6fe86547def6ff`; all 11 metrics and five contrasts retain their frozen schema and order; results interpreted and best condition selected remain false.

### 2026-07-22 - Phase 8F cross-process statistics reproducibility gate

- `failed_gate`: First independent final-result freeze `--verify-only` invocation after the public artifacts were written.
- `failure_reason`: `paired_differences` iterated a four-condition Python `set`; process-specific hash order changed only last-bit floating-point accumulation and therefore bootstrap/aggregate serialization bytes. The private input SHA, model hashes, accounting, schema, coefficients, and already frozen public files were unchanged.
- `commands`: In-memory checksum comparison and read-only enumeration of the 24 possible term orders, followed by targeted regression and freeze `--verify-only`. No evaluation episode or result artifact was regenerated.
- `generated_files`: None from the failed gate or diagnosis.
- `remaining_work`: Resolved; finish targeted tests, privacy review, explicit staging, commit, and push.
- `local_commit_sha`: `1964398103a344110b806e82b15de30c5d15f299` (publication changes still uncommitted).
- `push_error`: Not applicable.
- `resolution`: A fixed term-accumulation order (`P0S0`, `P0S1`, `P1S1`, `P1S0`) now removes hash-seed dependence while reproducing the original aggregate and statistics SHA-256 values exactly. The repeated verify-only passed with writes 0; no coefficient, private row, aggregate byte, statistics byte, rendered table, or manuscript value changed.

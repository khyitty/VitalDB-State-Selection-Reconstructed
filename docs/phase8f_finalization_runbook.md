# Phase 8F Finalization Runbook

This runbook begins only after Laptop B reports that P0S1 and P1S1 training has ended. Phase 8F preparation itself does not access Shard B, load a policy, run a test episode, calculate a condition comparison, or authorize publication of private outputs.

## Frozen identities

- Training implementation SHA: `b782b5e4a9d418f6b907a87d046c4e9789a3e5f0`
- Conditions, in fixed order: `P0S0`, `P1S0`, `P0S1`, `P1S1`
- Seed: `42`
- Final timestep: `1000000`
- Sealed test set: 490 cases from 483 subjects
- Model root on either laptop: `data/processed/phase8d_final_training_v1`
- Test runtime root on Laptop A: `data/processed/phase8e_test_runtime_inputs_v1`
- Evaluation output root on Laptop A: `data/processed/phase8e_evaluation_outputs_v1`

All paths above are repository-relative and Git-ignored. Do not substitute a local absolute path in a public manifest or report.

## 1. Verify Shard B on Laptop B

From the repository root at the exact training implementation commit, run the existing Phase 8D interface:

```powershell
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8d_final_training.py --shard B --expected-git-sha b782b5e4a9d418f6b907a87d046c4e9789a3e5f0 --total-timesteps 1000000 --seed 42 --resume --verify-only --output-root data/processed/phase8d_final_training_v1
```

The command must succeed without resuming training. Laptop B must report, for both P0S1 and P1S1:

- `OUTPUT_COMPLETE.json` completion status;
- final timestep and total budget;
- implementation and configuration SHA values;
- `final_model.zip` SHA-256;
- optimizer-state and final-checkpoint hashes recorded by the runner;
- checkpoint-manifest checksum and the checksum at timestep 1,000,000;
- test-access count;
- partial-file/directory count.

Any missing completion marker, checksum mismatch, nonzero test access, partial output, wrong seed, wrong budget, or wrong implementation SHA stops the process.

## 2. Transfer Shard B without Git

Copy only the ignored `P0S1` and `P1S1` condition directories under `data/processed/phase8d_final_training_v1` from Laptop B to Laptop A using an encrypted external drive, authenticated local transfer, or another approved non-Git channel. Do not commit, attach, or push models, checkpoints, optimizer state, progress logs, private case sequences, or local paths.

On Laptop A, place the directories at:

```text
data/processed/phase8d_final_training_v1/P0S1
data/processed/phase8d_final_training_v1/P1S1
```

Do not rename files or rebuild metadata during transfer.

## 3. Reverify Shard B on Laptop A

Run the same verify-only command on Laptop A:

```powershell
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8d_final_training.py --shard B --expected-git-sha b782b5e4a9d418f6b907a87d046c4e9789a3e5f0 --total-timesteps 1000000 --seed 42 --resume --verify-only --output-root data/processed/phase8d_final_training_v1
```

Compare every reported P0S1/P1S1 final-model, checkpoint, optimizer, configuration, and completion-record hash with Laptop B's signed or otherwise authenticated transfer record. A mismatch stops finalization; it is not repaired by editing metadata.

## 4. Enforce the four-model completeness gate

Before any test episode, confirm that P0S0, P1S0, P0S1, and P1S1 each have exactly one checksum-valid final model at timestep 1,000,000, seed 42, under the frozen training implementation and configuration. Intermediate checkpoints are not selectable. Do not inspect comparative performance at this gate.

Run the existing Phase 8E runner in verify-only mode:

```powershell
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8e_final_evaluation.py --models-root data/processed/phase8d_final_training_v1 --test-runtime-root data/processed/phase8e_test_runtime_inputs_v1 --expected-training-sha b782b5e4a9d418f6b907a87d046c4e9789a3e5f0 --seed 42 --verify-only
```

Verify-only must not import or load an SB3 policy and must not run an episode. It checks the four final-model records, sealed 490-case runtime store, common case order, and frozen train scalers.

## 5. Execute final evaluation once explicitly authorized

The command below is the repository's existing execution interface. It is documented here but was not run during Phase 8F preparation:

```powershell
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8e_final_evaluation.py --models-root data/processed/phase8d_final_training_v1 --test-runtime-root data/processed/phase8e_test_runtime_inputs_v1 --expected-training-sha b782b5e4a9d418f6b907a87d046c4e9789a3e5f0 --seed 42 --execute --output-root data/processed/phase8e_evaluation_outputs_v1
```

Stop immediately and preserve explicit failure evidence if any of these occurs:

- model, implementation, configuration, seed, timestep, or checksum mismatch;
- missing or additional condition;
- sealed-test count/order/root mismatch or train/test membership violation;
- optimizer, normalizer, scaler, or model mutation;
- nondeterministic-inference setting or exploration noise;
- failure row disappears, case pairing breaks, or subject aggregation is incomplete;
- nonfinite action, latent BIS, reward, metric, or statistic;
- write outside the approved ignored output root;
- raw/private/model/checkpoint path becomes Git-tracked;
- condition ordering, metric definitions, or contrast definitions differ from Phase 8E.

Do not change seed, budget, thresholds, metrics, contrasts, failure handling, or checkpoints to make evaluation pass.

## 6. Freeze a publication aggregate

The current Phase 8E execution runner writes private case-level evaluation rows. It does **not** expose a command that creates the Phase 8F aggregate JSON. Do not invent or imply an existing aggregate-freeze CLI. A separately reviewed and authorized aggregation step must:

1. consume the complete private Phase 8E rows without silent exclusion;
2. preserve within-case four-condition pairing;
3. aggregate multiple cases at subject level before inference;
4. compute only the 11 frozen metrics and five frozen contrasts with the Phase 8E statistics contract;
5. retain explicit attempted/completed/failed accounting;
6. emit no case ID, subject ID, timestamp, event value, trajectory, raw value, or private/local path;
7. serialize the strict schema `schemas/phase8f_aggregate_results.schema.json`;
8. record the SHA-256 of the exact aggregate bytes and freeze those bytes before interpretation.

Until that aggregation implementation has its own review and authorization, stop after private evaluation verification. Phase 8F does not bridge this gap by fabricating an interface or a result.

## 7. Validate and render the frozen aggregate

Use a repository-relative input path containing only the approved aggregate artifact. First validate without writes:

```powershell
python scripts\render_phase8f_paper_tables.py --input paper\generated\phase8e_aggregate_results.json --output-dir paper\generated\tables --verify-only
```

After independently confirming the aggregate SHA-256 and approval to create publication tables:

```powershell
python scripts\render_phase8f_paper_tables.py --input paper\generated\phase8e_aggregate_results.json --output-dir paper\generated\tables
```

If outputs already exist, the renderer refuses replacement. Use `--overwrite` only after comparing the old and new aggregate checksums and recording why replacement is authorized. Outputs are deterministic aggregate Markdown, CSV, LaTeX fragments, and a machine-readable publication summary. The renderer never ranks conditions or supplies narrative interpretation.

## 8. Freeze primary tables before interpretation

Record checksums for the source aggregate and every rendered file. Confirm fixed condition order, 44 condition-metric rows (11 metrics × 4 conditions), 55 paired-contrast rows, explicit failure accounting, finite values, correct units, and zero public case/event rows. Archive the checksum record before reading condition differences or editing the discussion. Changes after this point require a new version and an auditable reason; never overwrite the frozen primary table silently.

## 9. Replace manuscript tokens

Copy checksum-frozen values into `paper/manuscript.md` by exact token mapping. Every token must have one declared source field and unit. Replace `[RESULTS_PENDING]` and `[CONCLUSION_PENDING]` only after all machine tokens are resolved and tables are frozen. Do not add an unplanned metric, contrast, subgroup, seed analysis, composite score, ranking, or favorable-condition label. Adapt at most the applicable prespecified discussion scenario and retain the other scenarios as provenance.

## 10. Public-result boundary

Public commits may contain:

- manuscript text, bibliography, and figure/table specifications;
- schema, renderer, and tests;
- aggregate condition- and subject-level summaries that have passed disclosure review;
- aggregate Markdown/CSV/LaTeX tables and publication summary JSON;
- protocols, runbooks, checksum manifests, and software-version records.

Public commits must not contain:

- raw physiological or drug signals;
- private observation templates or runtime inputs;
- access ledgers, case sequences, case-level rows, subject identifiers, or event timestamps/values;
- models, checkpoints, optimizer/RNG states, training progress logs, or evaluation trajectories;
- credentials, local absolute paths, legacy artifacts, or unreviewed results.

Before staging, run read-only checks:

```powershell
git status --short
git ls-files data/processed
git ls-files | Select-String -Pattern '(?i)(\.npy$|\.npz$|model|checkpoint|optimizer|trajectory|access_ledger)'
git diff --name-only
```

Stage public files by explicit path only. Never use `git add .` or `git add -A`. Review `git diff --cached --name-only`, `git diff --cached --stat`, and the complete cached diff before committing.

## 11. Final manuscript checklist

- [ ] Four final models pass the exact SHA/seed/timestep/configuration gate.
- [ ] Laptop B reported hashes equal Laptop A observed hashes.
- [ ] Phase 8E verify-only passes before execution.
- [ ] The authorized evaluation finishes with explicit 490-case accounting per condition.
- [ ] Silent exclusions, optimizer updates, scaler fits, and normalization updates are zero.
- [ ] Private source rows remain ignored and untracked.
- [ ] The separately authorized aggregate step preserves pairing and subject aggregation.
- [ ] Aggregate bytes and primary rendered tables are checksum-frozen before interpretation.
- [ ] Renderer verify-only passes and generated files are deterministic.
- [ ] All manuscript tokens map to frozen fields with units and precision.
- [ ] Abstract and conclusion contain no pending token at submission time.
- [ ] Discussion matches the complete estimates and does not select a favorable narrative.
- [ ] One-seed, reconstructed-simulator, timestep/epoch, single-center, latent-outcome, frozen-threshold, external-validation, and clinical-significance limitations remain.
- [ ] Public staged data contain zero case-level or event-level rows and zero private/local paths.
- [ ] `data/processed`, raw signals, models, checkpoints, and legacy artifacts have zero staged/tracked files.
- [ ] Repository status, artifact hashes, and remote commit are recorded after publication.

# Phase 7C — PPO/Simulator Reuse Audit and Minimal Implementation Plan

## Outcome

Phase 7C is an audit and planning phase, not an implementation phase. The smallest defensible path is to request the laboratory's executable package first (Path A), while retaining the legacy PK/PD simulator as a tested fallback and the legacy environment/PPO integration as refactor candidates. Full reconstruction is not authorized.

The frozen Protocol v1.2 cohort remains 2,460 cases and 2,415 subjects. No subject split, test seal, VitalDB raw access, replay-template extraction, modeling array, dose or Cp/Ce calculation for real cases, normalization fit, checkpoint, PPO training, evaluation, or four-condition experiment occurred.

## Read-only evidence

The legacy repository remained at commit `9501b16a5c4db27f06fa0d0b252a3a75f633967f`, tree `60917f0b61ec1e6a195b9a648faa6466406aeda1`, with its pre-existing untracked `debug.log`. Fifteen source/configuration files were checksummed in `phase7c_source_snapshot.json`.

The following bounded probes were performed:

- The pure legacy PK/PD simulator imported, initialized without a checkpoint, reset one synthetic 40-year-old male profile, and advanced once for 10 seconds. It returned finite time, BIS, and concentration values.
- The legacy Gymnasium environment did not import because `gymnasium` is not installed in the current environment.
- The legacy PPO module did not import because package initialization reached the same missing `gymnasium` dependency. `stable_baselines3` is also absent and is not declared in the legacy `requirements.txt`.
- No dependency was installed. The existing smoke entry point was not run because it enforces at least 2,000 steps and creates checkpoints, both outside the revised scope.

Thus only `patient_simulator` and `pk_pd_model` meet every executable criterion in this environment. The complete component classification is machine-readable in `data/manifests/phase7c_component_reuse_audit.csv`.

## Reuse conclusions

The simulator has a checkpoint-free reset/advance contract and synthetic defaults. Its equations and units still require primary-source revalidation before scientific use. “Executable” here means software execution only, not scientific validation.

The environment has a coherent reset/step API, propofol action, exogenous remifentanil schedule, history buffer, reward calculator, and state profiles in source. It is `executable_after_small_refactor`, not executable now, because its required runtime dependency is unavailable. A later bounded probe should install a locked dependency set in an isolated environment and run exactly one synthetic reset and step.

The PPO layer delegates actor, critic, rollout buffer, GAE, and update mechanics to Stable-Baselines3 rather than implementing them locally. That is preferable to reconstruction, but the runtime dependency and exact package version are missing. Architecture, action bounds, reward constants, budget, and other scientific constants are not approved. The training and evaluation paths therefore cannot be treated as ready research executables.

Legacy checkpoints, outputs, frozen PPO JSON configurations, splits, scalers, and results remain prohibited artifacts.

## Scientific boundary

The legacy simulator supplies perfect/generated BIS without VitalDB SQI and real observation timing. A main experiment driven only by synthetic corruption would estimate behavior under the assumed corruption generator, not robustness to the empirical VitalDB observation process. A later approved replay layer is therefore needed for the planned empirical P0/P1 interpretation.

The drug-rate semantics audit concludes `retrospective_only_not_valid_for_online_control`; see `phase7c_drug_rate_semantics_report.md`. The Phase 6C drug hold caps cannot be transferred automatically to an online controller.

## Artifacts

- Component reuse audit: `data/manifests/phase7c_component_reuse_audit.csv`
- Source/probe snapshot: `data/manifests/phase7c_source_snapshot.json`
- Missing encoding options: `data/manifests/phase7c_missing_encoding_options.csv`
- S0/S1 feasibility: `data/manifests/phase7c_state_feasibility.csv`
- Minimum observation plan: `docs/phase7c_observation_quality_minimum_plan.md`
- Drug-rate report: `docs/phase7c_drug_rate_semantics_report.md`
- Laboratory checklist: `docs/phase7c_lab_code_request_checklist.md`
- Path comparison and roadmap: `docs/phase7c_implementation_path_comparison.md`, `docs/phase7c_minimal_implementation_roadmap.md`

## Scope correction

Before the revised instruction arrived, an initial full-scaffold implementation had started in the local worktree. Those implementation files are outside this phase, were not used as audit evidence, and must not be staged or committed. The exact list is in `docs/phase7c_excluded_scope_changes.md`. They were preserved rather than automatically deleted or reset, as instructed. Consequently the final worktree may remain dirty even when the audit-only commits are correctly published.

# Phase 8G Multi-Seed Robustness Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a prespecified, fail-closed seed-43/44 PPO training extension while preserving Phase 8D/8E/8F behavior.

**Architecture:** Add an isolated Phase 8G module and runner that reuse immutable Phase 8D checksum primitives while providing seed-aware environment creation and verification. Governance artifacts freeze seeds, shards, source checksums, seed-42 baselines, and the no-test boundary before execution.

**Tech Stack:** Python 3.11, NumPy PCG64, PyTorch CPU, Gymnasium 1.2.3, Stable-Baselines3 2.8.0, unittest, canonical JSON, Git.

## Global Constraints

- Allowed extension seeds are exactly 43 and 44.
- Each condition uses exactly 1,000,000 environment timesteps and checkpoints every 100,000.
- Phase 8D seed-42 source/config/output behavior is immutable.
- Phase 8E evaluation is not executed or modified.
- No raw/API access, private-store regeneration, test access, selection, or private Git tracking.

---

### Task 1: RED tests for extension contracts

**Files:**
- Create: `tests/test_phase8g_multiseed_training.py`
- Create: `tests/test_phase8g_protocol.py`

- [ ] Test seed/budget allowlists, sequence equality/difference, state/action invariants, output isolation, fail-closed resume/partial behavior, and legacy seed-42 verification.
- [ ] Run targeted tests and confirm failure because Phase 8G APIs/artifacts do not exist.

### Task 2: Seed-aware train-only implementation

**Files:**
- Create: `src/vitaldb_state_selection/rl_integration/multiseed_training.py`
- Create: `scripts/run_phase8g_multiseed_training.py`

- [ ] Implement seed-specific configuration and checksums.
- [ ] Implement train-only runtime wrapper without changing Phase 8C.
- [ ] Implement preflight, training, resume, verify-only, already-complete, and legacy verification.
- [ ] Run targeted runtime tests to green.

### Task 3: Public governance artifacts

**Files:**
- Create: `docs/phase8g_multiseed_robustness_protocol.md`
- Create: `docs/phase8g_parallel_training_runbook.md`
- Create: `docs/phase8g_training_infrastructure_report.md`
- Create: `data/manifests/phase8g_multiseed_config.json`
- Create: `data/manifests/phase8g_seed_definition.json`
- Create: `data/manifests/phase8g_shard_definition.json`
- Create: `data/manifests/phase8g_source_snapshot.json`
- Create: `data/manifests/phase8g_artifact_checksums.json`
- Create: `scripts/build_phase8g_artifact_checksums.py`
- Modify: `README.md`
- Modify: `docs/compliance_matrix.csv`

- [ ] Freeze the outcome-blind protocol, original Phase 8D checksum, seed-42 baseline fingerprints, and no-test boundary.
- [ ] Build and verify the self-excluding public checksum inventory.
- [ ] Run protocol tests to green.

### Task 4: Regression and release gates

- [ ] Run Phase 8C/8D/8E/8F regressions, targeted Phase 8G tests, isolated RL tests, first-N guards, and complete unittest discovery.
- [ ] Verify seed-42 fingerprints before and after.
- [ ] Stage only public files, commit, push, and independently verify remote main.

### Task 5: Laptop A execution

- [ ] Run seed 43 preflight, shard A training, verify-only, and seed-42 legacy verification.
- [ ] Repeat for seed 44.
- [ ] Monitor PID, CPU, RSS, progress, checkpoints, disk space, and final output.
- [ ] Re-verify seed-42 fingerprints and Git/private boundaries.

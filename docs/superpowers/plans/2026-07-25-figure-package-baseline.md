# Reproducible Manuscript Figure Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a privacy-safe, reproducible, committed manuscript figure package and a clean remote baseline without changing frozen scientific results.

**Architecture:** Audit the canonical repository figure generators and their publication-safe outputs against frozen Phase 8F artifacts. The user-removed external `figures_skill` directory is out of scope.

**Tech Stack:** Python 3.11, argparse, pathlib, Matplotlib, pandas, NumPy, pytest/unittest, Git.

## Global Constraints

- Do not modify Phase 8D/8E/8F scientific results or private outputs.
- Do not start Phase 8G, training, evaluation, raw/API access, cleanup, reset, or stash.
- Do not alter aggregate values, plotting calculations, labels, axes, colors, or layout.
- Commit zero case-level, subject-level, event-level, trajectory, private-path, model, or checkpoint files.

---

### Task 1: Freeze inventory baseline

**Files:**
- Create: `docs/figure_package_inventory.csv`

**Interfaces:**
- Consumes: current untracked package and SHA-256 hashes
- Produces: one row per canonical package file

- [ ] Record every untracked file's relative path, size, SHA-256, type, generator, reference status, scientific role, leakage risk, and commit decision.
- [ ] Verify both figure-data CSVs against frozen Phase 8F JSON artifacts.

### Task 2: Validate and classify the complete package

**Files:**
- Modify: `docs/figure_package_inventory.csv`

**Interfaces:**
- Consumes: all package files and manuscript/snippet references
- Produces: final A/B/C classification with no unresolved prohibited file

- [ ] Run syntax/import, CSV, PDF/PNG, path, privacy, raw/API, snippet-reference, and private-tracking checks.
- [ ] Run relevant tests and the complete base suite when feasible.
- [ ] Confirm frozen seed-42 and Phase 8B/8C roots are unchanged.

### Task 3: Commit, push, and verify baseline

**Files:**
- Stage: only files approved by the completed inventory

**Interfaces:**
- Consumes: validated package and audit records
- Produces: `FIGURE_PACKAGE_BASELINE_SHA`

- [ ] Print status, staged names/statistics, staged file count, binary bytes, and private staged count.
- [ ] Commit as `Add reproducible manuscript figure package`.
- [ ] Push, fetch, and independently verify local HEAD, `origin/main`, and remote main.
- [ ] Confirm clean status, private roots, seed-42 immutability, no seed-43/44 directories, and no running training/evaluation.

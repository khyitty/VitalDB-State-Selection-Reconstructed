# Generated publication artifacts

This directory contains the disclosure-reviewed Phase 8E aggregate and statistics
JSON, the exact Phase 8F manuscript token map, and deterministic Markdown, CSV,
LaTeX, and JSON outputs from `scripts/render_phase8f_paper_tables.py`. The aggregate
was frozen through the separately reviewed `scripts/freeze_phase8e_final_results.py`
interface before rendering or manuscript population.

Everything under this directory is seed-42, ICTC 2026 manuscript-scope only (see
the repository [README](../../README.md#ictc-2026-paper-scope)). Seed-43/44
extension outputs (e.g. the Phase 8G multi-seed summary) are intentionally kept
out of this directory and live under `data/manifests/phase8g_*` instead, so that
nothing manuscript-facing here ever mixes seeds.

Do not place case-level rows, subject identifiers, event timestamps or values, trajectories, raw signals, private templates, runtime inputs, models, checkpoints, optimizer state, credentials, or local paths in this directory.

# Phase 8G Prespecified Multi-Seed Robustness Extension Design

## Boundary

Phase 8G adds seeds 43 and 44 without changing Phase 8D, Phase 8E, or Phase 8F
source contracts or historical artifacts. Seed 42 remains executable only through
the Phase 8D runner and its private outputs remain immutable.

## Architecture

`multiseed_training.py` provides seed-aware configuration, PCG64 sampling,
train-only environments, checkpoint/resume validation, preflight, execution,
verification, and legacy seed-42 verification. It reuses Phase 8D's atomic and
checksum primitives but does not weaken Phase 8C/8D seed-42 guards.

The Phase 8G runner accepts exactly seeds 43 and 44, exactly 1,000,000 timesteps,
and the unchanged A/B shard mapping. A seed-specific directory is the only write
target. Existing partial directories fail closed and are never removed
automatically.

## Reproducibility

Python, NumPy global, NumPy PCG64, Torch CPU, SB3 model, Gymnasium reset, and
simulator seeds all equal the requested extension seed. All four conditions use
the same ordered sequence for one seed; seeds 43 and 44 produce different
sequences over the unchanged ordered 1,970-case train universe.

## Governance

Public manifests prespecify both seeds before training, preserve the original
Phase 8D config checksum and seed-42 output fingerprints, and record the
2026-07-25 outcome-blind amendment. Private models, checkpoints, progress,
sequences, and patient/runtime data remain Git-ignored.

No sealed-test evaluation, aggregation, condition selection, or manuscript
result update is authorized.

# Phase 8G Training Infrastructure Report

Phase 8G extends the completed seed-42 experiment with prespecified seeds 43 and
44. It reuses the exact Phase 8D PPO architecture and hyperparameters, the
sealed 1,970-case train universe, Phase 8B templates, Phase 8C patient and
remifentanil bundles, and S0/S1 train-only scalers.

The implementation is isolated from the historical Phase 8D runner. Its
seed-aware wrapper constructs the unchanged Gymnasium environment directly from
the already validated private train bundle, allowing only seeds 43 and 44 while
leaving Phase 8C's canonical seed-42 function unchanged.

Before source modification, all 47 inventory entries in each seed-42 condition
passed checksum verification. Their deterministic directory fingerprints are
frozen in `phase8g_source_snapshot.json`.

The extension refuses seed 42, non-prespecified seeds, non-million budgets,
wrong-seed/config/condition/implementation resumes, test membership, missing or
corrupt completion markers, and pre-existing partial directories. Preflight
performs one bounded 1,024-timestep optimizer update in memory and persists no
model, checkpoint, or output.

No Phase 8G training or sealed-test evaluation occurred while preparing these
public artifacts.

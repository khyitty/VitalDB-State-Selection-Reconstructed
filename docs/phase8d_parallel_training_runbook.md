# Phase 8D Parallel Training Runbook

Both laptops must use the same verified implementation commit and unmodified repository source. Laptop A owns shard A (`P0S0`, `P1S0`); Laptop B owns shard B (`P0S1`, `P1S1`). Conditions run sequentially within each shard.

## Laptop B preparation

1. Fetch the repository with ordinary Git and checkout the exact implementation SHA reported by Laptop A. Do not edit or commit repository code on Laptop B.
2. Copy the Phase 8B and Phase 8C private directories by external drive, local network, or secure file copy. Do not use Git.
3. Place them at the repository-relative paths:
   - `data/processed/phase8b_train_observation_templates_v1`
   - `data/processed/phase8c_train_runtime_inputs_v1`
4. Recreate or copy the isolated `.venv-phase7h` runtime and confirm the pinned Python, SB3, Gymnasium, Torch, NumPy, and SciPy versions.
5. From the repository root, verify shard B without opening test data:

```text
.venv-phase7h/Scripts/python.exe scripts/run_phase8d_final_training.py --shard B --expected-git-sha <IMPLEMENTATION_SHA> --total-timesteps 1000000 --seed 42 --resume --verify-only
```

6. Run shard B:

```text
.venv-phase7h/Scripts/python.exe scripts/run_phase8d_final_training.py --shard B --expected-git-sha <IMPLEMENTATION_SHA> --total-timesteps 1000000 --seed 42 --resume
```

## Completion and transfer

Verify again with `--verify-only`. Confirm checkpoints at 100,000 through 1,000,000, `OUTPUT_COMPLETE.json`, final model and optimizer hashes, test access count zero, and no partial path. Transfer the ignored condition directories back to Laptop A without Git. On Laptop A, place them under the same Phase 8D output root and rerun shard B `--verify-only` to recompute every checksum.

Do not publish private outputs, choose a condition, inspect test metrics, or run test evaluation during this procedure.

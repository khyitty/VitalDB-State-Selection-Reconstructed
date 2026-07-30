# Phase 8G Parallel Training Runbook

> This artifact belongs to a replication extension outside the confirmatory
> ICTC 2026 manuscript. The manuscript reports seed 42 only; see
> [Phase 8G protocol](phase8g_multiseed_robustness_protocol.md) and the
> repository [README](../README.md#ictc-2026-paper-scope).

Both laptops must checkout the exact `PHASE8G_IMPLEMENTATION_SHA` published by
Laptop A. Laptop B is execution-only and must not modify, commit, or push source.
Conditions run sequentially within each shard.

## Common preconditions

1. Confirm clean `main` at the exact implementation SHA.
2. Confirm the unchanged Phase 8B root
   `96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2`.
3. Confirm the unchanged Phase 8C root
   `25ad8a860f6c9b0b45febec7ff7d0d0edf88c0f1953229c8d95e207508d3a606`.
4. Confirm no process is updating the same seed and shard.
5. Never delete an existing checkpoint or ambiguous `.partial` path.

## Laptop A / shard A

Replace `<SHA>` with `PHASE8G_IMPLEMENTATION_SHA`:

```powershell
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8g_multiseed_training.py --shard A --seed 43 --total-timesteps 1000000 --expected-git-sha <SHA> --preflight
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8g_multiseed_training.py --shard A --seed 43 --total-timesteps 1000000 --expected-git-sha <SHA> --resume
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8g_multiseed_training.py --shard A --seed 43 --total-timesteps 1000000 --expected-git-sha <SHA> --verify-only
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8g_multiseed_training.py --shard A --seed 43 --total-timesteps 1000000 --expected-git-sha <SHA> --legacy-verify-seed42
```

Repeat the four commands with `--seed 44`.

## Laptop B / shard B

```powershell
git fetch origin
git checkout <SHA>
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8g_multiseed_training.py --shard B --seed 43 --total-timesteps 1000000 --expected-git-sha <SHA> --preflight
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8g_multiseed_training.py --shard B --seed 43 --total-timesteps 1000000 --expected-git-sha <SHA> --resume
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8g_multiseed_training.py --shard B --seed 43 --total-timesteps 1000000 --expected-git-sha <SHA> --verify-only
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8g_multiseed_training.py --shard B --seed 43 --total-timesteps 1000000 --expected-git-sha <SHA> --legacy-verify-seed42
```

Repeat with `--seed 44`. If execution is interrupted, use the same SHA, seed,
shard, and `--resume`; do not restart by deleting private outputs.

During execution monitor PID, cumulative CPU time, RSS, free disk, checkpoint
creation, and `progress.jsonl`. A live PID with increasing CPU or private output
is active even when final stdout has not yet appeared.

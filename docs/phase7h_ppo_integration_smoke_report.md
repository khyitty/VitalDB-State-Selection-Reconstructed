# Phase 7H bounded PPO integration smoke report

The isolated CPU runtime executed one official `ppo_integration_smoke_v1` run for each of P0S0, P1S0, P0S1, and P1S1. Each run used seed 42, one environment, 64-step rollouts, batch size 32, one optimizer epoch, and exactly 128 total timesteps. All four runs initialized the library PPO model, completed two rollout/update cycles, returned finite predicted actions, kept parameters and exposed losses finite, and sent only legal physical actions to the environment.

The machine-readable summary records correctness status, runtime, and traced Python peak memory only. It contains no reward or BIS comparison, condition ranking, convergence claim, best condition, or best seed. No model, optimizer state, rollout buffer, trajectory, TensorBoard log, monitor CSV, or persistent checkpoint was created.

The scientific candidate `paper_oriented_ppo_candidate_v1` remains separate. Its `n_steps=2048`, `batch_size=64`, and `n_epochs=10` were not substituted with smoke values and it was not trained. MC-030 total training budget and MC-033 final seed execution remain pending.

Bounded smoke command:

```powershell
$env:PYTHONPATH='src'; .\.venv-phase7h\Scripts\python.exe scripts\run_phase7h_validation.py
```

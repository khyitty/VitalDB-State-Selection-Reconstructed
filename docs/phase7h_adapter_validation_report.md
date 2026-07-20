# Phase 7H Gymnasium adapter validation

The optional `rl_integration` package wraps the Phase 7G environment core by composition. It does not duplicate the simulator, observation processor, state builder, action guard, or reward implementation. Stage I and Stage II remain importable without Gymnasium, Stable-Baselines3, or Torch.

All four condition IDs passed Gymnasium reset/step, a complete 30-second synthetic episode, Gymnasium's environment checker, Stable-Baselines3 `check_env`, `DummyVecEnv`, and PPO initialization without learning. S0 observations are float32 shape `(34,)`; S1 observations are float32 shape `(42,)`; actions are float32 shape `(1,)` with the physical contract `[0,27.7]` mg per next 10 seconds. Direct and adapted Phase 7G transitions produced equal float32 state, reward, and latent state for the same synthetic inputs.

Both checkers emitted the expected recommendation to use a symmetric normalized continuous action space. This is classified `expected_and_harmless`: Phase 7H was explicitly required to retain the physical action space and not add a normalized wrapper. No adapter bug or environment-contract conflict remained. Legal adapter actions did not invoke the Phase 7G core clipping guard.

Commands:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests -q
$env:PYTHONPATH='src'; .\.venv-phase7h\Scripts\python.exe -m unittest tests.test_phase7h_rl_integration tests.test_phase7h_smoke -v
```

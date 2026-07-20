# Phase 7H report

Phase 7H adds an optional Gymnasium/Stable-Baselines3 integration around the sealed Phase 7G dependency-free core. The approved implementation path uses SB3's PPO objective, rollout buffer, GAE, value optimization, entropy calculation, Adam optimizer, minibatch update, and seed handling. No SB3 internal source was copied or modified.

MC-019–MC-029 define `paper_oriented_ppo_candidate_v1` as a configuration candidate only. MC-034 fixes SB3 2.8.0, Gymnasium 1.2.3, and CPU execution as this study's versioned implementation choice, not a dependency claim about Yun et al. The `[128]` actor and critic networks are a paper-oriented study choice, not an exact reconstruction of an unpublished architecture. Adam weight decay 0.001 is recorded as an approximation of the reported L2 coefficient rather than an identical custom-loss implementation.

The isolated `.venv-phase7h` remains ignored and untracked. `requirements/phase7h_rl_direct.txt` contains only the two approved direct RL dependencies; the exact resolver state is frozen separately. The repository base dependency file was not changed. Because Stage I imports SciPy although it is not declared in `pyproject.toml`, a resolver-selected SciPy and the declared base test dependencies were installed only inside the venv and recorded in the runtime manifest.

Only synthetic inputs were used. No subject split, test seal, VitalDB raw or subject metadata access, actual observation template, real patient, full training, evaluation comparison, statistics, prediction, persistent model, or checkpoint was produced. Phase 7I was not started.

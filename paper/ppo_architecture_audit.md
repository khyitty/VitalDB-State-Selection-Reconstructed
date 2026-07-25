# PPO architecture audit

This audit is read-only. It does not initialize training, execute an evaluation
episode, change a checkpoint, or calculate a new result. In addition to the
source-level audit, all four exact final binary models were loaded on CPU without
an attached environment to verify their serialized architecture.

## Confirmed implementation

| Question | Confirmed structure | Evidence |
|---|---|---|
| Policy implementation | `stable_baselines3.PPO` with policy alias `MlpPolicy` (SB3 2.8.0); repository entry point `make_ppo_model` | `src/vitaldb_state_selection/rl_integration/config.py`; `requirements/phase7h_rl_direct.txt` |
| Feature extractor | SB3 default `FlattenExtractor`; it only flattens the already one-dimensional state and has no trainable parameters | `sb3_policy_kwargs` does not override `features_extractor_class`; installed SB3 2.8.0 `ActorCriticPolicy` default |
| Recurrent layer / LSTM | None | Policy is `MlpPolicy`; repository guard rejects `LstmPolicy` and `RecurrentPPO` |
| Demographic branch | None. Age, sex, height, and weight are the first four entries of the same S0/S1 vector | `src/vitaldb_state_selection/anesthesia/state.py` |
| Feature sharing | Actor and critic share the parameter-free `FlattenExtractor`, then use separate MLP branches. There is no shared trainable dense encoder | SB3 default `share_features_extractor=True`; `net_arch={"pi":[128],"vf":[128]}` |
| Actor branch | `Linear(d,128) → Tanh → Linear(128,1)` produces the Gaussian mean; one learned state-independent `log_std` parameter supplies the diagonal Gaussian scale | `sb3_policy_kwargs`; SB3 2.8.0 `MlpExtractor` and `ActorCriticPolicy._build` |
| Critic branch | `Linear(d,128) → Tanh → Linear(128,1)` produces \(V_\phi(s)\) | Same sources |
| Continuous distribution | One-dimensional `DiagGaussianDistribution`; `use_sde=False`, `squash_output=False` by the unmodified SB3 default | Frozen `phase8d_final_ppo_config.json`; SB3 2.8.0 policy defaults |
| Action bounds and units | Physical `Box([0],[27.7])` in mg per 10 s. SB3 clips unsquashed actions to this Box; the environment applies the same safety clip and converts to mg/min by multiplying by 6 | `SequentialTrainRuntimeEnv`; `anesthesia/action.py` |
| State dimensions | S0 = 34; S1 = 42 | Frozen scaler registry and environment construction |
| PPO hyperparameters | Frozen Phase 8D configuration: 128-unit actor/critic branches, Tanh, Adam, learning rate 0.001, \(n_\mathrm{steps}=2048\), batch 64, 10 epochs, \(\gamma=0.99\), GAE 0.95, clip 0.2 | `data/manifests/phase8d_final_ppo_config.json` |
| Future-BIS prediction head | None | No policy/output head in the integration code; prediction scope is explicitly deprecated for the controlled experiment |

The S0/S1 difference changes only the first linear layer's input width
(\(d=34\) or \(d=42\)). P0/P1 changes observation preprocessing, not the neural
network topology. The four policies are trained separately from scratch with the
same architecture and frozen hyperparameters.

## Explicitly absent

The implemented controller contains no LSTM, GRU, attention mechanism, separate
demographic/covariate branch, future-BIS prediction head, SHAP stage, Elastic Net,
stability selection, or separate feature-selection stage. These elements must
not appear in the architecture figure or Algorithm 1.

## Artifact-level verification

Each `final_model.zip` under
`data/processed/phase8d_final_training_v1/<condition>/seed_42` was loaded with
`PPO.load(..., device="cpu")`. No environment was attached, no prediction or
evaluation step was run, and no optimizer method was called.

| Condition | Final-model SHA-256 | Input | Actor / critic branches | Heads |
|---|---|---:|---|---|
| P0S0 | `f783ba214b9dc7e511ff4af7d38a641bd3924861cf562fad670b4b840ff77f3f` | 34 | separate 34→128 + Tanh | action 128→1; value 128→1; `log_std` shape (1,) |
| P1S0 | `c73bd394af2e5bf801c890bf9d98e1bf5876660b775c3c611ab7c8cdf0a93b83` | 34 | separate 34→128 + Tanh | action 128→1; value 128→1; `log_std` shape (1,) |
| P0S1 | `644371f5d74164fbe04b5f85f2301c4e2b0babf193e1667e623d3a209ce67947` | 42 | separate 42→128 + Tanh | action 128→1; value 128→1; `log_std` shape (1,) |
| P1S1 | `f79172fa014f23507ab2b33eb2a4cd9f2f1615e321165ce8a448ea5d3e0ab662` | 42 | separate 42→128 + Tanh | action 128→1; value 128→1; `log_std` shape (1,) |

All four artifacts reported `ActorCriticPolicy`, shared `FlattenExtractor`,
separate `MlpExtractor.policy_net` and `value_net`, the one-dimensional
`Box(0.0, 27.7, (1,), float32)` action space, `share_features_extractor=True`,
and `num_timesteps=1000000`. For every condition, the SHA-256 before loading,
after loading, and in `OUTPUT_COMPLETE.json` was identical.

## Closed boundary

The exact final model architectures—not only the architecture implied by source
code—are now independently verified. Learned weight values remain private and
were not printed, but this does not leave an architecture ambiguity.

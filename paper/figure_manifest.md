# Figure manifest

| Figure | Research question | Artifact fields | Width | Recommendation |
|---|---|---|---|---|
| `main_control_performance` | How do preprocessing and state representation affect primary control error and above-range exposure? | `phase8e_aggregate_results.json`: `conditions[].metrics[].{median,q1,q3}` for `mean_absolute_bis_deviation` and `time_above_bis_60_seconds` | Double column | Main-text Fig. 2 candidate |
| `paired_control_effects` | What are the subject-paired effects of each factor within the matched sealed-test design? | `phase8e_statistics_results.json`: `contrasts[].{mean_difference,bootstrap_ci_95}` for the same two metrics | Double column | Alternative main-text Fig. 2 candidate |
| `controlled_experiment_framework` | Which factors vary, and which elements are controlled across configurations? | Canonical P0/P1 and S0/S1 registries plus the four-policy and PPO invariance specifications | Double column | Main-text Fig. 1 |
| `training_evaluation_workflow` | Where do preprocessing/state selection and PPO updates occur in training versus evaluation? | `final_training.py`, `final_evaluation.py`, and frozen evaluation configuration | Double column, low profile | Supplementary candidate only |
| `ppo_actor_critic_architecture` | What feed-forward actor--critic topology is held fixed across the four configurations? | `config.py`, `final_training.py`, frozen Phase 8D PPO configuration, S0/S1 schemas, SB3 2.8.0 policy defaults, and all four serialized `final_model.zip` artifacts | Double column | Methods figure candidate |

Only the first two rows contain numerical results. The final public artifacts
contain no public case-level/event-level rows or trajectories, so no case
distribution or representative-trajectory figure is generated.

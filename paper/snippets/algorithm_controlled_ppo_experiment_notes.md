Algorithm 1 isolates the two experimental interventions: the causal preprocessing
profile and the state representation. Every configuration uses the same PPO
specification, seed, one-million-timestep budget, simulator, reward, training-case
sequence, and sealed evaluation cases; evaluation loads the train-only scaler and
uses deterministic policy inference without optimizer, policy, or scaler updates.


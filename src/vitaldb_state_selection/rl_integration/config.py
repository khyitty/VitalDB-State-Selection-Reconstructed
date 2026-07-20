"""Explicit Phase 7H PPO candidate and bounded smoke configurations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PPOConfiguration:
    configuration_id: str
    policy: str
    gamma: float
    gae_lambda: float
    clip_range: float
    n_steps: int
    batch_size: int
    n_epochs: int
    vf_coef: float
    ent_coef: float
    max_grad_norm: float
    learning_rate: float
    optimizer: str
    optimizer_weight_decay: float
    actor_hidden_layers: tuple[int, ...]
    critic_hidden_layers: tuple[int, ...]
    activation: str
    normalize_advantage: bool
    clip_range_vf: None
    use_sde: bool
    device: str
    seed: int | None
    total_timesteps: int | None
    n_envs: int
    purpose: str

    def as_manifest(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["actor_hidden_layers"] = list(self.actor_hidden_layers)
        payload["critic_hidden_layers"] = list(self.critic_hidden_layers)
        return payload


PAPER_ORIENTED_PPO_CANDIDATE_V1 = PPOConfiguration(
    configuration_id="paper_oriented_ppo_candidate_v1",
    policy="MlpPolicy",
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    vf_coef=0.1,
    ent_coef=0.0,
    max_grad_norm=0.5,
    learning_rate=0.001,
    optimizer="Adam",
    optimizer_weight_decay=0.001,
    actor_hidden_layers=(128,),
    critic_hidden_layers=(128,),
    activation="Tanh",
    normalize_advantage=True,
    clip_range_vf=None,
    use_sde=False,
    device="cpu",
    seed=None,
    total_timesteps=None,
    n_envs=1,
    purpose="scientific_candidate_not_approved_for_training",
)


PPO_INTEGRATION_SMOKE_V1 = PPOConfiguration(
    configuration_id="ppo_integration_smoke_v1",
    policy="MlpPolicy",
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    n_steps=64,
    batch_size=32,
    n_epochs=1,
    vf_coef=0.1,
    ent_coef=0.0,
    max_grad_norm=0.5,
    learning_rate=0.001,
    optimizer="Adam",
    optimizer_weight_decay=0.001,
    actor_hidden_layers=(128,),
    critic_hidden_layers=(128,),
    activation="Tanh",
    normalize_advantage=True,
    clip_range_vf=None,
    use_sde=False,
    device="cpu",
    seed=42,
    total_timesteps=128,
    n_envs=1,
    purpose="interface_correctness_only_not_scientific_result",
)


def sb3_policy_kwargs(configuration: PPOConfiguration) -> dict[str, Any]:
    """Translate the versioned contract without copying any PPO implementation."""

    import torch

    return {
        "activation_fn": torch.nn.Tanh,
        "net_arch": {
            "pi": list(configuration.actor_hidden_layers),
            "vf": list(configuration.critic_hidden_layers),
        },
        "optimizer_class": torch.optim.Adam,
        "optimizer_kwargs": {"weight_decay": configuration.optimizer_weight_decay},
    }


def make_ppo_model(environment: Any, configuration: PPOConfiguration = PPO_INTEGRATION_SMOKE_V1) -> Any:
    """Initialize the library PPO implementation on CPU; learning is separate."""

    from stable_baselines3 import PPO

    return PPO(
        configuration.policy,
        environment,
        learning_rate=configuration.learning_rate,
        n_steps=configuration.n_steps,
        batch_size=configuration.batch_size,
        n_epochs=configuration.n_epochs,
        gamma=configuration.gamma,
        gae_lambda=configuration.gae_lambda,
        clip_range=configuration.clip_range,
        clip_range_vf=configuration.clip_range_vf,
        normalize_advantage=configuration.normalize_advantage,
        ent_coef=configuration.ent_coef,
        vf_coef=configuration.vf_coef,
        max_grad_norm=configuration.max_grad_norm,
        use_sde=configuration.use_sde,
        policy_kwargs=sb3_policy_kwargs(configuration),
        seed=configuration.seed,
        device=configuration.device,
        verbose=0,
    )

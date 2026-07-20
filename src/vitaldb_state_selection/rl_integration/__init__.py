"""Optional Phase 7H Gymnasium and Stable-Baselines3 integration."""

from .adapter import GymnasiumAnesthesiaEnv
from .config import PAPER_ORIENTED_PPO_CANDIDATE_V1, PPO_INTEGRATION_SMOKE_V1, PPOConfiguration, make_ppo_model
from .factory import make_gymnasium_environment
from .smoke import run_condition_smoke

__all__ = [
    "GymnasiumAnesthesiaEnv", "PAPER_ORIENTED_PPO_CANDIDATE_V1", "PPOConfiguration",
    "PPO_INTEGRATION_SMOKE_V1", "make_gymnasium_environment", "make_ppo_model",
    "run_condition_smoke",
]

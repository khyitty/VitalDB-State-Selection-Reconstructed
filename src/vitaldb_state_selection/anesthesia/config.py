"""Versioned immutable configuration for the dependency-free Stage II core."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PreprocessingID(str, Enum):
    P0 = "P0_online_bis_permissive_v1"
    P1 = "P1_online_bis_quality_v1"


class StateID(str, Enum):
    S0 = "S0"
    S1 = "S1"


class ConditionID(str, Enum):
    P0S0 = "P0S0"
    P1S0 = "P1S0"
    P0S1 = "P0S1"
    P1S1 = "P1S1"


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    preprocessing_id: PreprocessingID
    state_id: StateID
    control_interval_seconds: float = 10.0
    history_offsets_seconds: tuple[float, ...] = (-50.0, -40.0, -30.0, -20.0, -10.0, 0.0)
    target_bis: float = 50.0
    episode_horizon_seconds: float = 3600.0
    bis_age_clip_seconds: float = 30.0
    p0_bis_staleness_seconds: float = 30.0
    p1_bis_staleness_seconds: float = 20.0
    p1_sqi_threshold: float = 50.0
    action_min_mg_per_10s: float = 0.0
    action_max_mg_per_10s: float = 27.7
    reward_alpha: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.preprocessing_id, PreprocessingID):
            raise ValueError("preprocessing_id must be a PreprocessingID")
        if not isinstance(self.state_id, StateID):
            raise ValueError("state_id must be a StateID")
        if self.control_interval_seconds != 10.0:
            raise ValueError("Stage II control interval is fixed at 10 seconds")
        if self.history_offsets_seconds != (-50.0, -40.0, -30.0, -20.0, -10.0, 0.0):
            raise ValueError("Stage II history offsets are fixed")
        if self.episode_horizon_seconds <= 0 or self.episode_horizon_seconds % 10.0:
            raise ValueError("episode horizon must be a positive multiple of 10 seconds")
        fixed = (
            self.target_bis == 50.0,
            self.bis_age_clip_seconds == 30.0,
            self.p0_bis_staleness_seconds == 30.0,
            self.p1_bis_staleness_seconds == 20.0,
            self.p1_sqi_threshold == 50.0,
            self.action_min_mg_per_10s == 0.0,
            self.action_max_mg_per_10s == 27.7,
            self.reward_alpha == 1.0,
        )
        if not all(fixed):
            raise ValueError("approved Stage II scientific constants may not be overridden")


FOUR_CONDITION_CONFIGS = {
    condition.value: EnvironmentConfig(
        PreprocessingID.P0 if condition.value.startswith("P0") else PreprocessingID.P1,
        StateID.S0 if condition.value.endswith("S0") else StateID.S1,
    )
    for condition in ConditionID
}

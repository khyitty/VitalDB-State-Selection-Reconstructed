"""Thin Gymnasium adapter composed around the sealed Phase 7G core."""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from vitaldb_state_selection.anesthesia import AnesthesiaEnvironmentCore, StateID


class GymnasiumAnesthesiaEnv(gym.Env[np.ndarray, np.ndarray]):
    """Gymnasium interface only; all scientific transitions remain in the core."""

    metadata = {"render_modes": []}

    def __init__(self, core: AnesthesiaEnvironmentCore, *, default_seed: int | None = None, render_mode: None = None):
        if render_mode is not None:
            raise ValueError("Phase 7H supports render_mode=None only")
        self.core = core
        self.default_seed = default_seed
        dimension = 34 if core.config.state_id is StateID.S0 else 42
        self.observation_space = gym.spaces.Box(
            low=np.zeros(dimension, dtype=np.float32),
            high=np.full(dimension, np.finfo(np.float32).max, dtype=np.float32),
            dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(
            low=np.asarray([0.0], dtype=np.float32),
            high=np.asarray([27.7], dtype=np.float32),
            dtype=np.float32,
        )
        self.render_mode = None

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        effective_seed = self.default_seed if seed is None else seed
        super().reset(seed=effective_seed)
        observation, info = self.core.reset(seed=effective_seed, options=options)
        return self._observation(observation), info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        array = np.asarray(action, dtype=np.float32)
        if array.shape != (1,) or not np.isfinite(array).all() or not self.action_space.contains(array):
            raise ValueError("action must be a finite float32-compatible array in the physical Box(0, 27.7, (1,))")
        scalar = float(array[0])
        # Canonicalize the float32 representation of the approved upper endpoint;
        # this is not an additional clipping layer.
        if array[0] == self.action_space.high[0]:
            scalar = self.core.config.action_max_mg_per_10s
        observation, reward, terminated, truncated, info = self.core.step(scalar)
        if info["action_was_clipped"]:
            raise RuntimeError("legal adapter action unexpectedly reached the core clipping guard")
        return self._observation(observation), float(reward), bool(terminated), bool(truncated), info

    def _observation(self, observation: np.ndarray) -> np.ndarray:
        converted = np.asarray(observation, dtype=np.float32)
        if converted.shape != self.observation_space.shape or not np.isfinite(converted).all():
            raise RuntimeError("Phase 7G observation invariant failed at the adapter boundary")
        if not self.observation_space.contains(converted):
            raise RuntimeError("observation is outside the declared nonnegative finite physical space")
        return converted

    def render(self) -> None:
        return None

    def close(self) -> None:
        return None

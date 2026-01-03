from __future__ import annotations

"""Actor interfaces used to build higher-level environments on top of a simulator backend."""

from dataclasses import dataclass
from typing import Any, Protocol

from .actions import DiscreteAction


@dataclass(frozen=True)
class ActorState:
    """Minimal kinematic state for an actor (intended for RL observation construction)."""

    position: tuple[float, float, float]
    yaw: float
    linear_speed: float
    yaw_rate: float


class Actor(Protocol):
    """
    Minimal actor interface that can later be embedded in a Gymnasium env exporter.
    """

    name: str
    entity: Any

    def apply_action(self, action: int | DiscreteAction) -> None: ...
    def step_control(self, dt: float) -> None: ...
    def state(self) -> ActorState: ...



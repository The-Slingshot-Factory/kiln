from __future__ import annotations

"""A simple controllable rigid-body "car" actor built from a box primitive."""

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .actions import ControlMode, DiscreteAction
from .base import ActorState
from .components import BlockBody, BlockController, CollisionEvent, CollisionTracker
from ..sim.genesis.sim import GenesisSim


@dataclass(frozen=True)
class CarBlockConfig:
    """Configuration for `CarBlock` (shape, mass, and control tuning)."""

    # Rigid body
    size: tuple[float, float, float] = (1.0, 0.5, 0.3)
    mass: float = 1.0
    color: tuple[float, float, float] | tuple[float, float, float, float] | None = None

    # Control
    control_mode: ControlMode = ControlMode.KINEMATIC
    max_speed: float = 5.0
    speed_delta: float = 0.5
    turn_rate: float = 1.5  # rad/s (yaw-rate target)

    # Force/torque mode tuning (only used when control_mode=FORCE_TORQUE)
    force: float = 30.0
    torque: float = 10.0

    # Initial state
    initial_yaw: float = 0.0


class CarBlock:
    """A simple "car" represented as a rigid block."""

    def __init__(
        self,
        sim: GenesisSim,
        *,
        name: str = "car",
        position: tuple[float, float, float] = (0.0, 0.0, 0.15),
        config: CarBlockConfig | None = None,
    ):
        self.sim = sim
        self.name = name
        self.config = config or CarBlockConfig()

        self._body = BlockBody(sim, name=name, position=position, config=self.config)
        self.entity = self._body.entity
        self._controller = BlockController(sim, self.entity, self.config, initial_yaw=self.config.initial_yaw)

        self._collisions = CollisionTracker(self.entity)
        self.collision_events_this_step: list[CollisionEvent] = []

    def apply_action(self, action: int | DiscreteAction) -> None:
        """Apply a discrete action by updating target speed and/or yaw-rate."""
        self._controller.apply_action(action)

    def step_control(self, dt: float) -> None:
        """Advance the control policy by one tick (to be called once per sim step)."""
        self._controller.step_control(dt)

    def state(self) -> ActorState:
        """Return the actor's current state (for observation/debugging)."""
        p = self._body.get_position(allow_cached=True)
        return self._controller.state(p)

    def heading_yaw(self) -> float:
        """Return the controller's current yaw estimate (radians)."""
        return self._controller.yaw

    def target_speed(self) -> float:
        """Return the current target speed (m/s)."""
        return self._controller.target_speed

    # ----------------------------
    # Collision events (polling)
    # ----------------------------
    def register_collision_handler(self, handler: Callable[[CollisionEvent], None]) -> None:
        """Register a callback invoked for each BEGIN/END event produced by polling."""
        self._collisions.register_handler(handler)

    def set_collision_targets(
        self,
        *,
        tracked_entities: Iterable[Any] | None = None,
        ignore_entities: Iterable[Any] | None = None,
    ) -> None:
        """Configure which entities count as collisions for this actor."""
        self._collisions.set_targets(tracked_entities=tracked_entities, ignore_entities=ignore_entities)

    def poll_collision_events(self, *, step_idx: int, min_force: float = 0.0) -> list[CollisionEvent]:
        """Poll Genesis contact data and emit BEGIN/END events for tracked entities."""
        self.collision_events_this_step = self._collisions.poll(step_idx=step_idx, min_force=min_force)
        return self.collision_events_this_step


def as_entity(actor: Any) -> Any:
    """Small helper for env exporters: accept an actor or raw entity."""
    return getattr(actor, "entity", actor)

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .actions import ControlMode, DiscreteAction
from .base import ActorState
from ..sim.genesis.sim import GenesisSim


@dataclass(frozen=True)
class CarBlockConfig:
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
    """
    A simple "car" represented as a rigid block.

    Coordinate convention (for now):
    - Ground plane: XY
    - Up axis: +Z
    - Forward: +X at yaw=0
    - Left turn: +yaw about +Z

    TODO(usd): Add constructor that binds to a USD-authored prim (spawn/attach by prim path).
    """

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

        self.entity = sim.add_box(
            name=name,
            size=self.config.size,
            position=position,
            mass=self.config.mass,
            color=self.config.color,
        )

        self._yaw = float(self.config.initial_yaw)
        self._target_speed = 0.0
        self._target_yaw_rate = 0.0
        self._last_action: DiscreteAction | None = None

    def apply_action(self, action: int | DiscreteAction) -> None:
        a = DiscreteAction(int(action))
        self._last_action = a

        if a == DiscreteAction.ACCELERATE:
            self._target_speed = min(self.config.max_speed, self._target_speed + self.config.speed_delta)
            self._target_yaw_rate = 0.0
        elif a == DiscreteAction.DECELERATE:
            self._target_speed = max(0.0, self._target_speed - self.config.speed_delta)
            self._target_yaw_rate = 0.0
        elif a == DiscreteAction.TURN_LEFT:
            self._target_yaw_rate = +self.config.turn_rate
        elif a == DiscreteAction.TURN_RIGHT:
            self._target_yaw_rate = -self.config.turn_rate

    def step_control(self, dt: float) -> None:
        if self.config.control_mode == ControlMode.KINEMATIC:
            self._step_kinematic(dt)
            return
        if self.config.control_mode == ControlMode.FORCE_TORQUE:
            self._step_force_torque(dt)
            return
        raise ValueError(f"Unknown control_mode: {self.config.control_mode!r}")

    def state(self) -> ActorState:
        p = self.sim.get_position(self.entity)
        return ActorState(
            position=p,
            yaw=float(self._yaw),
            linear_speed=float(self._target_speed),
            yaw_rate=float(self._target_yaw_rate),
        )

    # ----------------------------
    # Internals
    # ----------------------------
    def _forward_dir(self) -> tuple[float, float, float]:
        return (math.cos(self._yaw), math.sin(self._yaw), 0.0)

    def _step_kinematic(self, dt: float) -> None:
        # Update our internal yaw and apply as velocities (stable, easy-to-control).
        self._yaw += self._target_yaw_rate * float(dt)

        fx, fy, _ = self._forward_dir()
        vx = self._target_speed * fx
        vy = self._target_speed * fy

        self.sim.set_linear_velocity(self.entity, (vx, vy, 0.0))
        self.sim.set_angular_velocity(self.entity, (0.0, 0.0, self._target_yaw_rate))

    def _step_force_torque(self, dt: float) -> None:
        # Apply forces/torques each step. This is intentionally simple and will be tuned later.
        # We keep an internal yaw estimate to orient forces; future versions can read yaw from Genesis.
        self._yaw += self._target_yaw_rate * float(dt)

        a = self._last_action
        if a == DiscreteAction.ACCELERATE:
            force_mag = +self.config.force
        elif a == DiscreteAction.DECELERATE:
            force_mag = -self.config.force
        else:
            force_mag = 0.0

        fx, fy, _ = self._forward_dir()
        self.sim.apply_force(self.entity, (force_mag * fx, force_mag * fy, 0.0))

        if a == DiscreteAction.TURN_LEFT:
            torque = +self.config.torque
        elif a == DiscreteAction.TURN_RIGHT:
            torque = -self.config.torque
        else:
            torque = 0.0

        # Yaw torque about +Z
        self.sim.apply_torque(self.entity, (0.0, 0.0, torque))


def as_entity(actor: Any) -> Any:
    """
    Small helper for future env exporters: accept an actor or raw entity.
    """

    return getattr(actor, "entity", actor)



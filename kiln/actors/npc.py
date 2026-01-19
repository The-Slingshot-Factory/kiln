from __future__ import annotations

"""NPC actor built from a rigid block with a heuristic roaming policy."""

import random
from dataclasses import dataclass
from typing import Any, Iterable

from .actions import ControlMode, DiscreteAction
from .base import ActorState
from .car import CarBlockConfig
from .components import BlockBody, BlockController, NPCPolicy
from .pathfinding import NavGrid


@dataclass(frozen=True)
class NPCBlockConfig(CarBlockConfig):
    """Configuration for `NPCBlock` (roaming bounds, avoidance, and navigation tuning)."""

    # Roaming
    roam_xy_min: tuple[float, float] = (-5.0, -5.0)
    roam_xy_max: tuple[float, float] = (5.0, 5.0)
    goal_tolerance: float = 0.5

    cruise_speed: float = 2.0
    heading_threshold: float = 0.35  # rad

    # Obstacle avoidance (raycast-first, then proximity fallback)
    raycast_length: float = 2.0
    raycast_angle: float = 0.45  # ~26 degrees
    avoid_distance: float = 1.25
    brake_distance: float = 0.5

    avoid_radius: float = 1.0
    emergency_brake_radius: float = 0.6

    # Stuck detection
    stuck_steps: int = 30
    progress_eps: float = 1e-3

    # Navigation / pathfinding (static obstacles like buildings)
    nav_cell_size: float = 0.5
    nav_inflate: float = 0.3
    waypoint_tolerance: float = 0.35
    max_goal_samples: int = 50


class NPCBlock:
    """NPC-controlled block with the same 4-action interface as `CarBlock`."""

    def __init__(
        self,
        sim: Any,
        *,
        name: str = "npc",
        position: tuple[float, float, float] = (2.0, 0.0, 0.15),
        config: NPCBlockConfig | None = None,
        rng: random.Random | None = None,
        nav_grid: NavGrid | None = None,
    ):
        self.sim = sim
        self.name = name
        self.npc_config = config or NPCBlockConfig()
        self.config = self.npc_config

        self._body = BlockBody(sim, name=name, position=position, config=self.npc_config)
        self.entity = self._body.entity
        self._controller = BlockController(sim, self.entity, self.npc_config, initial_yaw=self.npc_config.initial_yaw)
        self._policy = NPCPolicy(self._body, self._controller, self.npc_config, rng=rng, nav_grid=nav_grid)

    def set_roam_bounds(self, xy_min: tuple[float, float], xy_max: tuple[float, float]) -> None:
        """Set the roaming bounds used for sampling random goals (XY)."""
        self._policy.set_roam_bounds(xy_min, xy_max)

    def set_nav_grid(self, nav_grid: NavGrid | None) -> None:
        """Set or clear a navigation grid (A* waypoints will be generated when present)."""
        self._policy.set_nav_grid(nav_grid)

    def pick_new_goal(self) -> tuple[float, float]:
        """Sample a new goal and (optionally) build an A* path to it if a nav grid is set."""
        return self._policy.pick_new_goal()

    def policy_step(
        self,
        obstacles: Iterable[Any] | None = None,
        *,
        positions_by_id: dict[int, tuple[float, float, float]] | None = None,
    ) -> DiscreteAction:
        """Compute a discrete action from the heuristic policy."""
        return self._policy.policy_step(obstacles=obstacles, positions_by_id=positions_by_id)

    def apply_action(self, action: int | DiscreteAction) -> None:
        """Apply a discrete action by updating target speed and/or yaw-rate."""
        self._controller.apply_action(action)

    def step_control(self, dt: float) -> None:
        """
        Apply control with an extra safety clamp when using a nav grid:
        don't drive into blocked cells (buildings).
        """
        nav_grid = self._policy.nav_grid
        if nav_grid is not None and self.config.control_mode == ControlMode.KINEMATIC:
            v_xyz, w_xyz = self._controller.compute_kinematic(dt)
            px, py, _ = self._body.last_position
            nx = px + v_xyz[0] * float(dt)
            ny = py + v_xyz[1] * float(dt)
            c_next = nav_grid.world_to_cell(nx, ny)
            if nav_grid.is_blocked(c_next):
                self._controller.set_target_speed(0.0)
                self._controller.apply_kinematic((0.0, 0.0, 0.0), w_xyz)
                return
            self._controller.apply_kinematic(v_xyz, w_xyz)
            return

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

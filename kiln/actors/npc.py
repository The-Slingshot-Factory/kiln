from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Iterable

from .actions import DiscreteAction
from .car import CarBlock, CarBlockConfig


@dataclass(frozen=True)
class NPCBlockConfig(CarBlockConfig):
    # Roaming (filled in during npc-roaming todo)
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


class NPCBlock(CarBlock):
    """
    NPC-controlled block with the same 4-action interface as `CarBlock`.

    The heuristic policy is implemented in the next milestone (npc-roaming todo).
    """

    def __init__(
        self,
        sim,
        *,
        name: str = "npc",
        position: tuple[float, float, float] = (2.0, 0.0, 0.15),
        config: NPCBlockConfig | None = None,
        rng: random.Random | None = None,
    ):
        self.npc_config = config or NPCBlockConfig()
        super().__init__(sim, name=name, position=position, config=self.npc_config)

        self._rng = rng or random.Random()
        self._goal_xy: tuple[float, float] | None = None
        self._roam_xy_min = self.npc_config.roam_xy_min
        self._roam_xy_max = self.npc_config.roam_xy_max
        self._prev_goal_dist: float | None = None
        self._stuck_counter: int = 0

    def set_roam_bounds(self, xy_min: tuple[float, float], xy_max: tuple[float, float]) -> None:
        # Will be used by the roaming heuristic.
        self._roam_xy_min = xy_min
        self._roam_xy_max = xy_max

    def pick_new_goal(self) -> tuple[float, float]:
        xmin, ymin = self._roam_xy_min
        xmax, ymax = self._roam_xy_max
        self._goal_xy = (self._rng.uniform(xmin, xmax), self._rng.uniform(ymin, ymax))
        self._prev_goal_dist = None
        self._stuck_counter = 0
        return self._goal_xy

    def policy_step(self, obstacles: Iterable[Any] | None = None) -> DiscreteAction:
        """
        Roaming heuristic:
        - Pick a random goal in bounds
        - Steer toward it
        - Avoid obstacles (raycast-first; proximity fallback; stuck fallback)
        """
        if self._goal_xy is None:
            self.pick_new_goal()

        gx, gy = self._goal_xy
        px, py, _ = self.sim.get_position(self.entity)
        dx, dy = gx - px, gy - py
        goal_dist = math.hypot(dx, dy)

        # Goal reached -> pick another.
        if goal_dist <= self.npc_config.goal_tolerance:
            self.pick_new_goal()
            return DiscreteAction.TURN_LEFT if self._rng.random() < 0.5 else DiscreteAction.TURN_RIGHT

        # Stuck detection based on goal distance not improving.
        if self._prev_goal_dist is not None and goal_dist >= (self._prev_goal_dist - self.npc_config.progress_eps):
            self._stuck_counter += 1
        else:
            self._stuck_counter = 0
        self._prev_goal_dist = goal_dist

        if self._stuck_counter >= self.npc_config.stuck_steps:
            # Hard reset: new goal + random turn.
            self.pick_new_goal()
            return DiscreteAction.TURN_LEFT if self._rng.random() < 0.5 else DiscreteAction.TURN_RIGHT

        # 1) Raycast-based avoidance (best effort; GenesisSim.raycast returns hit=False if unsupported)
        avoid = self._avoid_with_rays()
        if avoid is not None:
            return avoid

        # 2) Proximity-based avoidance if we were given obstacle entities.
        if obstacles is not None:
            avoid = self._avoid_with_proximity(obstacles)
            if avoid is not None:
                return avoid

        # 3) Goal seeking (pure pursuit-ish with discrete steering)
        desired_yaw = math.atan2(dy, dx)
        yaw_err = _wrap_pi(desired_yaw - self._yaw)

        if abs(yaw_err) > self.npc_config.heading_threshold:
            return DiscreteAction.TURN_LEFT if yaw_err > 0 else DiscreteAction.TURN_RIGHT

        # Speed control: nudge toward cruise speed.
        cruise = self.npc_config.cruise_speed
        if self._target_speed < cruise:
            return DiscreteAction.ACCELERATE
        return DiscreteAction.DECELERATE

    # ----------------------------
    # Internals
    # ----------------------------
    def _avoid_with_rays(self) -> DiscreteAction | None:
        px, py, pz = self.sim.get_position(self.entity)
        origin = (px, py, pz + 0.1)

        # Forward direction from our internal yaw
        fx = math.cos(self._yaw)
        fy = math.sin(self._yaw)

        def rot(vx: float, vy: float, ang: float) -> tuple[float, float, float]:
            c, s = math.cos(ang), math.sin(ang)
            return (c * vx - s * vy, s * vx + c * vy, 0.0)

        fwd = (fx, fy, 0.0)
        left = rot(fx, fy, +self.npc_config.raycast_angle)
        right = rot(fx, fy, -self.npc_config.raycast_angle)

        h_c = self.sim.raycast(origin, fwd, max_distance=self.npc_config.raycast_length)
        if not h_c.hit:
            return None

        # If we can't interpret distance, fall back to proximity/stuck logic instead of
        # turning forever.
        if h_c.distance is None:
            return None

        if h_c.distance > self.npc_config.avoid_distance:
            return None

        # Emergency brake if we have a distance and it's very close.
        if h_c.distance <= self.npc_config.brake_distance:
            return DiscreteAction.DECELERATE

        h_l = self.sim.raycast(origin, left, max_distance=self.npc_config.raycast_length)
        h_r = self.sim.raycast(origin, right, max_distance=self.npc_config.raycast_length)

        # Steer away from the side that is blocked.
        left_blocked = h_l.hit and (h_l.distance is None or h_l.distance <= self.npc_config.avoid_distance)
        right_blocked = h_r.hit and (h_r.distance is None or h_r.distance <= self.npc_config.avoid_distance)

        if left_blocked and not right_blocked:
            return DiscreteAction.TURN_RIGHT
        if right_blocked and not left_blocked:
            return DiscreteAction.TURN_LEFT
        return DiscreteAction.TURN_LEFT if self._rng.random() < 0.5 else DiscreteAction.TURN_RIGHT

    def _avoid_with_proximity(self, obstacles: Iterable[Any]) -> DiscreteAction | None:
        px, py, _ = self.sim.get_position(self.entity)
        fx = math.cos(self._yaw)
        fy = math.sin(self._yaw)

        best_dist = None
        best_cross = None

        for obs in obstacles:
            if obs is self.entity:
                continue
            try:
                ox, oy, _ = self.sim.get_position(obs)
            except Exception:
                continue
            dx, dy = ox - px, oy - py
            dist = math.hypot(dx, dy)
            if dist <= 1e-9:
                continue

            # Ahead check via projection onto forward direction.
            proj = dx * fx + dy * fy
            if proj <= 0:
                continue

            if dist <= self.npc_config.emergency_brake_radius:
                return DiscreteAction.DECELERATE

            if dist <= self.npc_config.avoid_radius:
                cross = fx * dy - fy * dx
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_cross = cross

        if best_dist is None or best_cross is None:
            return None

        # If obstacle is to the left (cross > 0), turn right (and vice versa).
        return DiscreteAction.TURN_RIGHT if best_cross > 0 else DiscreteAction.TURN_LEFT


def _wrap_pi(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a



from __future__ import annotations

"""Shared actor components (body, controller, collision tracking, NPC policy)."""

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Protocol

from .actions import ControlMode, DiscreteAction
from .base import ActorState
from .pathfinding import NavGrid, astar, cells_to_waypoints, simplify_path_cells


class BlockShapeConfig(Protocol):
    size: tuple[float, float, float]
    mass: float
    color: tuple[float, float, float] | tuple[float, float, float, float] | None


class BlockControlConfig(Protocol):
    control_mode: ControlMode
    max_speed: float
    speed_delta: float
    turn_rate: float
    force: float
    torque: float


class NPCPolicyConfig(Protocol):
    roam_xy_min: tuple[float, float]
    roam_xy_max: tuple[float, float]
    goal_tolerance: float
    cruise_speed: float
    heading_threshold: float
    raycast_length: float
    raycast_angle: float
    avoid_distance: float
    brake_distance: float
    avoid_radius: float
    emergency_brake_radius: float
    stuck_steps: int
    progress_eps: float
    waypoint_tolerance: float
    max_goal_samples: int


class CollisionPhase(str, Enum):
    BEGIN = "begin"
    END = "end"


@dataclass(frozen=True)
class CollisionEvent:
    """Collision begin/end event for this actor against a tracked target entity."""

    step_idx: int
    phase: CollisionPhase
    other_entity: Any
    other_entity_id: int
    max_force: float | None = None
    contact_count: int = 0


class CollisionTracker:
    """Collision polling utility for a rigid entity."""

    def __init__(self, entity: Any) -> None:
        self.entity = entity
        self.events_this_step: list[CollisionEvent] = []
        self._handlers: list[Callable[[CollisionEvent], None]] = []
        self._tracked_entities: list[Any] = []
        self._ignore_entities: list[Any] = []
        self._tracked_ranges: list[tuple[int, int, int]] = []  # (geom_start, geom_end, entity_id)
        self._ignore_ranges: list[tuple[int, int]] = []  # (geom_start, geom_end)
        self._tracked_by_id: dict[int, Any] = {}
        self._active_entity_ids: set[int] = set()
        self._active_max_force: dict[int, float] = {}

    def register_handler(self, handler: Callable[[CollisionEvent], None]) -> None:
        """Register a callback invoked for each BEGIN/END event."""
        self._handlers.append(handler)

    def set_targets(
        self,
        *,
        tracked_entities: Iterable[Any] | None = None,
        ignore_entities: Iterable[Any] | None = None,
    ) -> None:
        """Configure which entities count as collisions for this tracker."""
        self._tracked_entities = list(tracked_entities or [])
        self._ignore_entities = list(ignore_entities or [])

        self._tracked_ranges = []
        self._ignore_ranges = []
        self._tracked_by_id = {}
        self._active_entity_ids.clear()
        self._active_max_force.clear()

        def geom_range(ent: Any) -> tuple[int, int] | None:
            gs = getattr(ent, "geom_start", None)
            ge = getattr(ent, "geom_end", None)
            if gs is None or ge is None:
                return None
            try:
                return (int(gs), int(ge))
            except Exception:
                return None

        for ent in self._tracked_entities:
            r = geom_range(ent)
            if r is None:
                continue
            eid = id(ent)
            self._tracked_by_id[eid] = ent
            self._tracked_ranges.append((r[0], r[1], eid))

        for ent in self._ignore_entities:
            r = geom_range(ent)
            if r is None:
                continue
            self._ignore_ranges.append((r[0], r[1]))

    def poll(self, *, step_idx: int, min_force: float = 0.0) -> list[CollisionEvent]:
        """Poll contacts from the last `scene.step()` and emit BEGIN/END events."""
        self.events_this_step = []

        if not self._tracked_ranges:
            return self.events_this_step
        if not hasattr(self.entity, "get_contacts"):
            return self.events_this_step

        car_gs = getattr(self.entity, "geom_start", None)
        car_ge = getattr(self.entity, "geom_end", None)
        if car_gs is None or car_ge is None:
            return self.events_this_step

        contacts = self.entity.get_contacts()
        if not isinstance(contacts, dict):
            return self.events_this_step

        geom_a = contacts.get("geom_a")
        geom_b = contacts.get("geom_b")
        if geom_a is None or geom_b is None:
            return self.events_this_step

        force_a = contacts.get("force_a") if min_force > 0.0 else None
        force_b = contacts.get("force_b") if min_force > 0.0 else None

        try:
            import torch
        except Exception:
            torch = None  # type: ignore[assignment]

        current_ids: set[int] = set()
        current_max_force: dict[int, float] = {}
        current_counts: dict[int, int] = {}

        if torch is not None and hasattr(geom_a, "shape"):
            car_gs_i = int(car_gs)
            car_ge_i = int(car_ge)

            in_a = (geom_a >= car_gs_i) & (geom_a < car_ge_i)
            in_b = (geom_b >= car_gs_i) & (geom_b < car_ge_i)
            mask = in_a | in_b

            if mask.numel() > 0 and bool(mask.any()):
                other_geom = torch.where(in_a, geom_b, geom_a)[mask]
                in_a_f = in_a[mask]

                force_mag = None
                if force_a is not None and force_b is not None:
                    car_force = torch.where(in_a_f.unsqueeze(-1), force_a[mask], force_b[mask])
                    force_mag = torch.linalg.vector_norm(car_force, dim=1)

                def in_any_range(g: int, ranges: list[tuple[int, int]]) -> bool:
                    for s, e in ranges:
                        if s <= g < e:
                            return True
                    return False

                def geom_to_tracked_id(g: int) -> int | None:
                    if in_any_range(g, self._ignore_ranges):
                        return None
                    for s, e, eid in self._tracked_ranges:
                        if s <= g < e:
                            return eid
                    return None

                n = int(other_geom.shape[0])
                for i in range(n):
                    g = int(other_geom[i].item())
                    eid = geom_to_tracked_id(g)
                    if eid is None:
                        continue
                    if force_mag is not None:
                        f = float(force_mag[i].item())
                        if f < float(min_force):
                            continue
                        prev = current_max_force.get(eid)
                        if prev is None or f > prev:
                            current_max_force[eid] = f
                    current_ids.add(eid)
                    current_counts[eid] = current_counts.get(eid, 0) + 1

        begins = current_ids.difference(self._active_entity_ids)
        ends = self._active_entity_ids.difference(current_ids)

        for eid in sorted(begins):
            other = self._tracked_by_id.get(eid)
            if other is None:
                continue
            ev = CollisionEvent(
                step_idx=int(step_idx),
                phase=CollisionPhase.BEGIN,
                other_entity=other,
                other_entity_id=eid,
                max_force=current_max_force.get(eid),
                contact_count=int(current_counts.get(eid, 0)),
            )
            self.events_this_step.append(ev)
            self._active_max_force[eid] = current_max_force.get(eid, 0.0)
            for h in self._handlers:
                h(ev)

        for eid in sorted(ends):
            other = self._tracked_by_id.get(eid)
            if other is None:
                continue
            ev = CollisionEvent(
                step_idx=int(step_idx),
                phase=CollisionPhase.END,
                other_entity=other,
                other_entity_id=eid,
                max_force=self._active_max_force.get(eid),
                contact_count=0,
            )
            self.events_this_step.append(ev)
            self._active_max_force.pop(eid, None)
            for h in self._handlers:
                h(ev)

        self._active_entity_ids = set(current_ids)
        for eid, mf in current_max_force.items():
            self._active_max_force[eid] = mf

        return self.events_this_step


class BlockBody:
    """Rigid-body wrapper that owns the Genesis entity and cached position."""

    def __init__(
        self,
        sim: Any,
        *,
        name: str,
        position: tuple[float, float, float],
        config: BlockShapeConfig,
    ) -> None:
        self.sim = sim
        self.name = name
        self.entity = sim.add_box(
            name=name,
            size=config.size,
            position=position,
            mass=config.mass,
            color=config.color,
        )
        self._last_position = (float(position[0]), float(position[1]), float(position[2]))

    @property
    def last_position(self) -> tuple[float, float, float]:
        return self._last_position

    def update_cached_position(self, position: tuple[float, float, float]) -> None:
        self._last_position = (float(position[0]), float(position[1]), float(position[2]))

    def get_position(self, *, allow_cached: bool = False) -> tuple[float, float, float]:
        try:
            p = self.sim.get_position(self.entity)
        except Exception:
            if allow_cached:
                return self._last_position
            raise
        self.update_cached_position(p)
        return p

    def get_xy(self, *, allow_cached: bool = False) -> tuple[float, float]:
        p = self.get_position(allow_cached=allow_cached)
        return (float(p[0]), float(p[1]))


class BlockController:
    """Action-to-control policy for a rigid block."""

    def __init__(
        self,
        sim: Any,
        entity: Any,
        config: BlockControlConfig,
        *,
        initial_yaw: float = 0.0,
    ) -> None:
        self.sim = sim
        self.entity = entity
        self.config = config
        self._yaw = float(initial_yaw)
        self._target_speed = 0.0
        self._target_yaw_rate = 0.0
        self._last_action: DiscreteAction | None = None

    @property
    def yaw(self) -> float:
        return float(self._yaw)

    @property
    def target_speed(self) -> float:
        return float(self._target_speed)

    @property
    def target_yaw_rate(self) -> float:
        return float(self._target_yaw_rate)

    def set_target_speed(self, speed: float) -> None:
        self._target_speed = float(speed)

    def apply_action(self, action: int | DiscreteAction) -> None:
        """Apply a discrete action by updating target speed and/or yaw-rate."""
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

    def state(self, position: tuple[float, float, float]) -> ActorState:
        return ActorState(
            position=position,
            yaw=float(self._yaw),
            linear_speed=float(self._target_speed),
            yaw_rate=float(self._target_yaw_rate),
        )

    def step_control(self, dt: float) -> None:
        """Advance control by one tick (to be called once per sim step)."""
        if self.config.control_mode == ControlMode.KINEMATIC:
            v_xyz, w_xyz = self.compute_kinematic(dt)
            self.apply_kinematic(v_xyz, w_xyz)
            return
        if self.config.control_mode == ControlMode.FORCE_TORQUE:
            f_xyz, tau_xyz = self.compute_force_torque(dt)
            self.apply_force_torque(f_xyz, tau_xyz)
            return
        raise ValueError(f"Unknown control_mode: {self.config.control_mode!r}")

    def compute_kinematic(self, dt: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        self._yaw += self._target_yaw_rate * float(dt)
        fx = math.cos(self._yaw)
        fy = math.sin(self._yaw)
        vx = self._target_speed * fx
        vy = self._target_speed * fy
        return (vx, vy, 0.0), (0.0, 0.0, self._target_yaw_rate)

    def apply_kinematic(self, v_xyz: tuple[float, float, float], w_xyz: tuple[float, float, float]) -> None:
        self.sim.set_linear_angular_velocity(self.entity, v_xyz, w_xyz)

    def compute_force_torque(self, dt: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        self._yaw += self._target_yaw_rate * float(dt)

        a = self._last_action
        if a == DiscreteAction.ACCELERATE:
            force_mag = +self.config.force
        elif a == DiscreteAction.DECELERATE:
            force_mag = -self.config.force
        else:
            force_mag = 0.0

        fx = math.cos(self._yaw)
        fy = math.sin(self._yaw)
        force = (force_mag * fx, force_mag * fy, 0.0)

        if a == DiscreteAction.TURN_LEFT:
            torque = +self.config.torque
        elif a == DiscreteAction.TURN_RIGHT:
            torque = -self.config.torque
        else:
            torque = 0.0
        return force, (0.0, 0.0, torque)

    def apply_force_torque(self, f_xyz: tuple[float, float, float], tau_xyz: tuple[float, float, float]) -> None:
        self.sim.apply_force(self.entity, f_xyz)
        self.sim.apply_torque(self.entity, tau_xyz)


class NPCPolicy:
    """Goal-seeking policy for NPC blocks (optional nav grid + avoidance)."""

    def __init__(
        self,
        body: BlockBody,
        controller: BlockController,
        config: NPCPolicyConfig,
        *,
        rng: random.Random | None = None,
        nav_grid: NavGrid | None = None,
    ) -> None:
        self._body = body
        self._controller = controller
        self._config = config
        self._rng = rng or random.Random()

        self._goal_xy: tuple[float, float] | None = None
        self._roam_xy_min = config.roam_xy_min
        self._roam_xy_max = config.roam_xy_max
        self._prev_goal_dist: float | None = None
        self._stuck_counter: int = 0

        self._nav_grid: NavGrid | None = nav_grid
        self._waypoints_xy: list[tuple[float, float]] = []
        self._waypoint_idx: int = 0

    @property
    def nav_grid(self) -> NavGrid | None:
        return self._nav_grid

    def set_roam_bounds(self, xy_min: tuple[float, float], xy_max: tuple[float, float]) -> None:
        self._roam_xy_min = xy_min
        self._roam_xy_max = xy_max

    def set_nav_grid(self, nav_grid: NavGrid | None) -> None:
        self._nav_grid = nav_grid
        self._waypoints_xy = []
        self._waypoint_idx = 0

    def pick_new_goal(self) -> tuple[float, float]:
        xmin, ymin = self._roam_xy_min
        xmax, ymax = self._roam_xy_max
        if self._nav_grid is not None:
            px, py = self._body.get_xy(allow_cached=True)
            start = self._nav_grid.world_to_cell(px, py)

            for _ in range(max(1, self._config.max_goal_samples)):
                gx = self._rng.uniform(xmin, xmax)
                gy = self._rng.uniform(ymin, ymax)
                goal = self._nav_grid.world_to_cell(gx, gy)
                path = astar(self._nav_grid, start, goal)
                if path is None:
                    continue
                path = simplify_path_cells(path)
                self._waypoints_xy = cells_to_waypoints(self._nav_grid, path)
                self._waypoint_idx = 0
                self._goal_xy = (gx, gy)
                break
            else:
                self._goal_xy = (self._rng.uniform(xmin, xmax), self._rng.uniform(ymin, ymax))
                self._waypoints_xy = []
                self._waypoint_idx = 0
        else:
            self._goal_xy = (self._rng.uniform(xmin, xmax), self._rng.uniform(ymin, ymax))

        self._prev_goal_dist = None
        self._stuck_counter = 0
        return self._goal_xy

    def policy_step(
        self,
        obstacles: Iterable[Any] | None = None,
        *,
        positions_by_id: dict[int, tuple[float, float, float]] | None = None,
    ) -> DiscreteAction:
        if self._goal_xy is None:
            self.pick_new_goal()

        if positions_by_id is not None:
            p = positions_by_id.get(id(self._body.entity))
            if p is not None:
                self._body.update_cached_position(p)
                px, py = float(p[0]), float(p[1])
            else:
                px, py = self._body.get_xy(allow_cached=True)
        else:
            px, py = self._body.get_xy(allow_cached=True)
        target_x, target_y = self._goal_xy

        if self._nav_grid is not None and self._waypoints_xy:
            while self._waypoint_idx < len(self._waypoints_xy):
                wx, wy = self._waypoints_xy[self._waypoint_idx]
                if math.hypot(wx - px, wy - py) <= self._config.waypoint_tolerance:
                    self._waypoint_idx += 1
                    continue
                break
            if self._waypoint_idx >= len(self._waypoints_xy):
                self.pick_new_goal()
                target_x, target_y = self._goal_xy
            else:
                target_x, target_y = self._waypoints_xy[self._waypoint_idx]

        dx, dy = target_x - px, target_y - py
        target_dist = math.hypot(dx, dy)

        if self._nav_grid is None and target_dist <= self._config.goal_tolerance:
            self.pick_new_goal()
            return DiscreteAction.TURN_LEFT if self._rng.random() < 0.5 else DiscreteAction.TURN_RIGHT

        if self._prev_goal_dist is not None and target_dist >= (self._prev_goal_dist - self._config.progress_eps):
            self._stuck_counter += 1
        else:
            self._stuck_counter = 0
        self._prev_goal_dist = target_dist

        if self._stuck_counter >= self._config.stuck_steps:
            if self._nav_grid is not None and self._goal_xy is not None:
                start = self._nav_grid.world_to_cell(px, py)
                goal = self._nav_grid.world_to_cell(self._goal_xy[0], self._goal_xy[1])
                path = astar(self._nav_grid, start, goal)
                if path is not None:
                    path = simplify_path_cells(path)
                    self._waypoints_xy = cells_to_waypoints(self._nav_grid, path)
                    self._waypoint_idx = 0
                    self._stuck_counter = 0
                else:
                    self.pick_new_goal()
            else:
                self.pick_new_goal()
            return DiscreteAction.TURN_LEFT if self._rng.random() < 0.5 else DiscreteAction.TURN_RIGHT

        if obstacles is not None:
            avoid = self._avoid_with_proximity(obstacles, self_xy=(px, py), positions_by_id=positions_by_id)
            if avoid is not None:
                return avoid

        desired_yaw = math.atan2(dy, dx)
        yaw_err = _wrap_pi(desired_yaw - self._controller.yaw)

        if abs(yaw_err) > self._config.heading_threshold:
            return DiscreteAction.TURN_LEFT if yaw_err > 0 else DiscreteAction.TURN_RIGHT

        cruise = self._config.cruise_speed
        if self._controller.target_speed < cruise:
            return DiscreteAction.ACCELERATE
        return DiscreteAction.DECELERATE

    def _avoid_with_rays(self) -> DiscreteAction | None:
        px, py, pz = self._body.get_position(allow_cached=True)
        origin = (px, py, pz + 0.1)

        fx = math.cos(self._controller.yaw)
        fy = math.sin(self._controller.yaw)

        def rot(vx: float, vy: float, ang: float) -> tuple[float, float, float]:
            c, s = math.cos(ang), math.sin(ang)
            return (c * vx - s * vy, s * vx + c * vy, 0.0)

        fwd = (fx, fy, 0.0)
        left = rot(fx, fy, +self._config.raycast_angle)
        right = rot(fx, fy, -self._config.raycast_angle)

        h_c = self._body.sim.raycast(origin, fwd, max_distance=self._config.raycast_length)
        if not h_c.hit or (h_c.distance is not None and h_c.distance > self._config.avoid_distance):
            return None
        if h_c.distance is not None and h_c.distance <= self._config.brake_distance:
            return DiscreteAction.DECELERATE

        h_l = self._body.sim.raycast(origin, left, max_distance=self._config.raycast_length)
        h_r = self._body.sim.raycast(origin, right, max_distance=self._config.raycast_length)

        left_blocked = h_l.hit and (h_l.distance is None or h_l.distance <= self._config.avoid_distance)
        right_blocked = h_r.hit and (h_r.distance is None or h_r.distance <= self._config.avoid_distance)

        if left_blocked and not right_blocked:
            return DiscreteAction.TURN_RIGHT
        if right_blocked and not left_blocked:
            return DiscreteAction.TURN_LEFT
        return DiscreteAction.TURN_LEFT if self._rng.random() < 0.5 else DiscreteAction.TURN_RIGHT

    def _avoid_with_proximity(
        self,
        obstacles: Iterable[Any],
        *,
        self_xy: tuple[float, float] | None = None,
        positions_by_id: dict[int, tuple[float, float, float]] | None = None,
    ) -> DiscreteAction | None:
        if self_xy is None:
            px, py = self._body.get_xy(allow_cached=True)
        else:
            px, py = float(self_xy[0]), float(self_xy[1])
        fx = math.cos(self._controller.yaw)
        fy = math.sin(self._controller.yaw)

        best_dist = None
        best_cross = None

        for obs in obstacles:
            if obs is self._body.entity:
                continue
            if positions_by_id is not None:
                p = positions_by_id.get(id(obs))
                if p is None:
                    continue
                ox, oy = float(p[0]), float(p[1])
            else:
                try:
                    ox, oy, _ = self._body.sim.get_position(obs)
                except Exception:
                    continue
            dx, dy = ox - px, oy - py
            dist = math.hypot(dx, dy)
            if dist <= 1e-9:
                continue

            proj = dx * fx + dy * fy
            if proj <= 0:
                continue

            if dist <= self._config.emergency_brake_radius:
                return DiscreteAction.DECELERATE

            if dist <= self._config.avoid_radius:
                cross = fx * dy - fy * dx
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_cross = cross

        if best_dist is None or best_cross is None:
            return None

        return DiscreteAction.TURN_RIGHT if best_cross > 0 else DiscreteAction.TURN_LEFT


def _wrap_pi(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a

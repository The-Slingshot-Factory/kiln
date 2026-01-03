from __future__ import annotations

"""A simple controllable rigid-body \"car\" actor built from a box primitive."""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable

from .actions import ControlMode, DiscreteAction
from .base import ActorState
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


class CollisionPhase(str, Enum):
    BEGIN = "begin"
    END = "end"


@dataclass(frozen=True)
class CollisionEvent:
    """
    Collision begin/end event for this actor against a *tracked* target entity.
    """

    step_idx: int
    phase: CollisionPhase
    other_entity: Any
    other_entity_id: int
    max_force: float | None = None
    contact_count: int = 0


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
        """Create a new car block and spawn its underlying rigid body into the sim."""
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

        # Collision event tracking (polling model: call poll_collision_events() after sim.step()).
        self.collision_events_this_step: list[CollisionEvent] = []
        self._collision_handlers: list[Callable[[CollisionEvent], None]] = []
        self._collision_tracked_entities: list[Any] = []
        self._collision_ignore_entities: list[Any] = []
        self._collision_tracked_ranges: list[tuple[int, int, int]] = []  # (geom_start, geom_end, entity_id)
        self._collision_ignore_ranges: list[tuple[int, int]] = []  # (geom_start, geom_end)
        self._collision_tracked_by_id: dict[int, Any] = {}
        self._active_collision_entity_ids: set[int] = set()
        self._active_collision_max_force: dict[int, float] = {}

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

    def step_control(self, dt: float) -> None:
        """Advance the control policy by one tick (to be called once per sim step)."""
        if self.config.control_mode == ControlMode.KINEMATIC:
            self._step_kinematic(dt)
            return
        if self.config.control_mode == ControlMode.FORCE_TORQUE:
            self._step_force_torque(dt)
            return
        raise ValueError(f"Unknown control_mode: {self.config.control_mode!r}")

    def state(self) -> ActorState:
        """Return the actor's current state (for observation/debugging)."""
        p = self.sim.get_position(self.entity)
        return ActorState(
            position=p,
            yaw=float(self._yaw),
            linear_speed=float(self._target_speed),
            yaw_rate=float(self._target_yaw_rate),
        )

    # ----------------------------
    # Collision events (polling)
    # ----------------------------
    def register_collision_handler(self, handler: Callable[[CollisionEvent], None]) -> None:
        """
        Register a callback invoked for each BEGIN/END event produced by poll_collision_events().
        """
        self._collision_handlers.append(handler)

    def set_collision_targets(
        self,
        *,
        tracked_entities: Iterable[Any] | None = None,
        ignore_entities: Iterable[Any] | None = None,
    ) -> None:
        """
        Configure which entities count as "collisions" for this actor.

        - tracked_entities: collisions with these entities produce BEGIN/END events.
        - ignore_entities: entities to ignore even if their contacts are present (e.g., ground plane).

        NOTE: This uses Genesis' per-step contact data and geom index ranges (geom_start/geom_end).
        """
        self._collision_tracked_entities = list(tracked_entities or [])
        self._collision_ignore_entities = list(ignore_entities or [])

        self._collision_tracked_ranges = []
        self._collision_ignore_ranges = []
        self._collision_tracked_by_id = {}
        self._active_collision_entity_ids.clear()
        self._active_collision_max_force.clear()

        def geom_range(ent: Any) -> tuple[int, int] | None:
            gs = getattr(ent, "geom_start", None)
            ge = getattr(ent, "geom_end", None)
            if gs is None or ge is None:
                return None
            try:
                return (int(gs), int(ge))
            except Exception:
                return None

        for ent in self._collision_tracked_entities:
            r = geom_range(ent)
            if r is None:
                continue
            eid = id(ent)
            self._collision_tracked_by_id[eid] = ent
            self._collision_tracked_ranges.append((r[0], r[1], eid))

        for ent in self._collision_ignore_entities:
            r = geom_range(ent)
            if r is None:
                continue
            self._collision_ignore_ranges.append((r[0], r[1]))

    def poll_collision_events(self, *, step_idx: int, min_force: float = 0.0) -> list[CollisionEvent]:
        """
        Poll Genesis contact data from the most recent `scene.step()` and emit BEGIN/END events.

        Call this once per timestep **after** `sim.step()`.
        """
        self.collision_events_this_step = []

        if not self._collision_tracked_ranges:
            return self.collision_events_this_step
        if not hasattr(self.entity, "get_contacts"):
            return self.collision_events_this_step

        car_gs = getattr(self.entity, "geom_start", None)
        car_ge = getattr(self.entity, "geom_end", None)
        if car_gs is None or car_ge is None:
            return self.collision_events_this_step

        contacts = self.entity.get_contacts()
        if not isinstance(contacts, dict):
            return self.collision_events_this_step

        geom_a = contacts.get("geom_a")
        geom_b = contacts.get("geom_b")
        if geom_a is None or geom_b is None:
            return self.collision_events_this_step

        # Best-effort force thresholding: avoid pulling extra tensors unless requested.
        force_a = contacts.get("force_a") if min_force > 0.0 else None
        force_b = contacts.get("force_b") if min_force > 0.0 else None

        try:
            import torch
        except Exception:
            torch = None  # type: ignore[assignment]

        current_ids: set[int] = set()
        current_max_force: dict[int, float] = {}
        current_counts: dict[int, int] = {}

        if torch is None or not hasattr(geom_a, "shape"):
            # No torch available (unexpected in Genesis env); skip.
            current_ids = set()
        else:
            car_gs_i = int(car_gs)
            car_ge_i = int(car_ge)

            in_a = (geom_a >= car_gs_i) & (geom_a < car_ge_i)
            in_b = (geom_b >= car_gs_i) & (geom_b < car_ge_i)
            mask = in_a | in_b

            if mask.numel() > 0 and bool(mask.any()):
                # For each contact involving the car, pick the other geom index.
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
                    if in_any_range(g, self._collision_ignore_ranges):
                        return None
                    for s, e, eid in self._collision_tracked_ranges:
                        if s <= g < e:
                            return eid
                    return None

                # Note: contact counts per step are typically small; a Python loop is fine here.
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

        begins = current_ids.difference(self._active_collision_entity_ids)
        ends = self._active_collision_entity_ids.difference(current_ids)

        # Emit events (BEGIN first, then END) for determinism.
        for eid in sorted(begins):
            other = self._collision_tracked_by_id.get(eid)
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
            self.collision_events_this_step.append(ev)
            self._active_collision_max_force[eid] = current_max_force.get(eid, 0.0)
            for h in self._collision_handlers:
                h(ev)

        for eid in sorted(ends):
            other = self._collision_tracked_by_id.get(eid)
            if other is None:
                continue
            ev = CollisionEvent(
                step_idx=int(step_idx),
                phase=CollisionPhase.END,
                other_entity=other,
                other_entity_id=eid,
                max_force=self._active_collision_max_force.get(eid),
                contact_count=0,
            )
            self.collision_events_this_step.append(ev)
            self._active_collision_max_force.pop(eid, None)
            for h in self._collision_handlers:
                h(ev)

        self._active_collision_entity_ids = set(current_ids)
        for eid, mf in current_max_force.items():
            self._active_collision_max_force[eid] = mf

        return self.collision_events_this_step

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

        self.sim.set_linear_angular_velocity(self.entity, (vx, vy, 0.0), (0.0, 0.0, self._target_yaw_rate))

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



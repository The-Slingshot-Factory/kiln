from __future__ import annotations

"""MJCF-style XML loader for Kiln env bundles."""

from dataclasses import dataclass, replace
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterator

from .bundle import EnvBundleError, EnvBundleV1, Pose, PrimitiveSpec, WorldSpec

KILN_NS = "urn:kiln:mjcf:v1"
_KILN_ATTR_PREFIX = f"{{{KILN_NS}}}"


@dataclass(frozen=True)
class ActorSpec:
    """Actor configuration parsed from `<kiln:actor ...>` metadata."""

    id: str
    actor_type: str  # car_block | npc_block
    pose: Pose
    size: tuple[float, float, float]
    mass: float
    color: tuple[float, float, float] | tuple[float, float, float, float] | None
    control_mode: str  # kinematic | force_torque
    max_speed: float
    speed_delta: float
    turn_rate: float
    force: float
    torque: float
    initial_yaw: float
    action_map: tuple[int, int, int, int]
    # NPC-only fields (kept with defaults for uniform runtime handling)
    roam_xy_min: tuple[float, float] = (-5.0, -5.0)
    roam_xy_max: tuple[float, float] = (5.0, 5.0)
    goal_tolerance: float = 0.5
    cruise_speed: float = 2.0
    heading_threshold: float = 0.35
    raycast_length: float = 2.0
    raycast_angle: float = 0.45
    avoid_distance: float = 1.25
    brake_distance: float = 0.5
    avoid_radius: float = 1.0
    emergency_brake_radius: float = 0.6
    stuck_steps: int = 30
    progress_eps: float = 1e-3
    nav_cell_size: float = 0.5
    nav_inflate: float = 0.3
    waypoint_tolerance: float = 0.35
    max_goal_samples: int = 50


@dataclass(frozen=True)
class EnvXmlBundle(EnvBundleV1):
    """XML bundle extension that additionally carries actor specs."""

    actors: tuple[ActorSpec, ...] = ()


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _iter_children(elem: ET.Element, local: str) -> Iterator[ET.Element]:
    for child in list(elem):
        if _local_name(child.tag) == local:
            yield child


def _first_child(elem: ET.Element, local: str) -> ET.Element | None:
    for child in _iter_children(elem, local):
        return child
    return None


def _get_attr(elem: ET.Element | None, name: str, default: str | None = None) -> str | None:
    if elem is None:
        return default
    ns_name = f"{_KILN_ATTR_PREFIX}{name}"
    if ns_name in elem.attrib:
        return elem.attrib[ns_name]
    return elem.attrib.get(name, default)


def _parse_float(raw: str, *, ctx: str) -> float:
    try:
        return float(raw)
    except Exception as e:
        raise EnvBundleError(f"Expected a number for {ctx}, got {raw!r}") from e


def _parse_int(raw: str, *, ctx: str) -> int:
    try:
        return int(float(raw))
    except Exception as e:
        raise EnvBundleError(f"Expected an integer for {ctx}, got {raw!r}") from e


def _parse_float_attr(elem: ET.Element | None, name: str, *, default: float, ctx: str) -> float:
    raw = _get_attr(elem, name, None)
    if raw is None:
        return default
    return _parse_float(raw, ctx=ctx)


def _parse_optional_float_attr(elem: ET.Element | None, name: str, *, ctx: str) -> float | None:
    raw = _get_attr(elem, name, None)
    if raw is None:
        return None
    return _parse_float(raw, ctx=ctx)


def _parse_int_attr(elem: ET.Element | None, name: str, *, default: int, ctx: str) -> int:
    raw = _get_attr(elem, name, None)
    if raw is None:
        return int(default)
    return _parse_int(raw, ctx=ctx)


def _parse_bool(raw: str, *, ctx: str) -> bool:
    v = raw.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    raise EnvBundleError(f"Expected a boolean for {ctx}, got {raw!r}")


def _parse_bool_attr(elem: ET.Element | None, name: str, *, default: bool, ctx: str) -> bool:
    raw = _get_attr(elem, name, None)
    if raw is None:
        return default
    return _parse_bool(raw, ctx=ctx)


def _parse_optional_bool_attr(elem: ET.Element | None, name: str, *, ctx: str) -> bool | None:
    raw = _get_attr(elem, name, None)
    if raw is None:
        return None
    return _parse_bool(raw, ctx=ctx)


def _parse_vec(raw: str, *, n: int, ctx: str) -> tuple[float, ...]:
    parts = [p for p in raw.replace(",", " ").split() if p]
    if len(parts) != n:
        raise EnvBundleError(f"Expected {n} values for {ctx}, got {raw!r}")
    return tuple(_parse_float(p, ctx=f"{ctx}[{i}]") for i, p in enumerate(parts))


def _parse_optional_vec(raw: str | None, *, n: int, ctx: str) -> tuple[float, ...] | None:
    if raw is None:
        return None
    return _parse_vec(raw, n=n, ctx=ctx)


def _parse_pose_from_body(body: ET.Element, *, ctx: str) -> Pose:
    pos_raw = _get_attr(body, "pos", "0 0 0")
    quat_raw = _get_attr(body, "quat", "1 0 0 0")
    pos = _parse_vec(pos_raw, n=3, ctx=f"{ctx}.pos")
    quat = _parse_vec(quat_raw, n=4, ctx=f"{ctx}.quat")
    return Pose(
        pos=(pos[0], pos[1], pos[2]),
        quat=(quat[0], quat[1], quat[2], quat[3]),
    )


def _yaw_from_quat(quat: tuple[float, float, float, float]) -> float:
    """Extract z-yaw (radians) from a `(w, x, y, z)` quaternion."""
    w, x, y, z = quat
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _parse_rgba(geom: ET.Element, *, ctx: str) -> tuple[float, float, float] | tuple[float, float, float, float] | None:
    raw = _get_attr(geom, "rgba", None)
    if raw is None:
        return None
    parts = [p for p in raw.replace(",", " ").split() if p]
    if len(parts) not in (3, 4):
        raise EnvBundleError(f"Expected 3 or 4 values for {ctx}.rgba, got {raw!r}")
    vals = tuple(_parse_float(p, ctx=f"{ctx}.rgba[{i}]") for i, p in enumerate(parts))
    if len(vals) == 3:
        return (vals[0], vals[1], vals[2])
    return (vals[0], vals[1], vals[2], vals[3])


def _parse_geom_size(geom: ET.Element, *, ctx: str) -> list[float]:
    raw = _get_attr(geom, "size", None)
    if raw is None:
        return []
    vals = [p for p in raw.replace(",", " ").split() if p]
    return [_parse_float(v, ctx=f"{ctx}.size[{i}]") for i, v in enumerate(vals)]


def _geom_collision_default(geom: ET.Element) -> bool:
    contype = _get_attr(geom, "contype", None)
    conaffinity = _get_attr(geom, "conaffinity", None)
    if contype is None and conaffinity is None:
        return True
    try:
        ct = int(float(contype)) if contype is not None else 1
        ca = int(float(conaffinity)) if conaffinity is not None else 1
    except Exception:
        return True
    return not (ct == 0 and ca == 0)


def _quat_mul(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def _rotate_vec_y_up_to_z_up(v: tuple[float, float, float]) -> tuple[float, float, float]:
    # +90deg about X: maps source +Y (up) -> target +Z (up).
    x, y, z = v
    return (x, -z, y)


def _convert_pose_y_up_to_z_up(pose: Pose) -> Pose:
    sqrt_half = math.sqrt(0.5)
    q_x_pos_90 = (sqrt_half, sqrt_half, 0.0, 0.0)
    return Pose(
        pos=_rotate_vec_y_up_to_z_up(pose.pos),
        quat=_quat_mul(q_x_pos_90, pose.quat),
    )


def _canonicalize_y_up_bundle(bundle: EnvXmlBundle) -> EnvXmlBundle:
    world = replace(bundle.world, pose=_convert_pose_y_up_to_z_up(bundle.world.pose))

    primitives = tuple(
        replace(
            prim,
            pose=_convert_pose_y_up_to_z_up(prim.pose),
            normal=(_rotate_vec_y_up_to_z_up(prim.normal) if prim.normal is not None else None),
        )
        for prim in bundle.primitives
    )

    actors = tuple(
        replace(actor, pose=_convert_pose_y_up_to_z_up(actor.pose))
        for actor in bundle.actors
    )

    spawn_points = {
        name: _convert_pose_y_up_to_z_up(spawn_pose)
        for name, spawn_pose in bundle.spawn_points.items()
    }

    return replace(
        bundle,
        world=world,
        primitives=primitives,
        spawn_points=spawn_points,
        actors=actors,
    )


def load_env_xml_bundle(xml_path: str | Path) -> EnvBundleV1:
    """
    Parse a MuJoCo-style XML scene into `EnvBundleV1`.

    Supported subset:
    - `<mujoco ... xmlns:kiln="urn:kiln:mjcf:v1">`
    - `<asset><mesh .../></asset>` for world mesh indirection
    - `<worldbody><body ...><geom .../></body></worldbody>`
    - Kiln extension tags: `<kiln:world>`, `<kiln:primitive>`, `<kiln:spawn_points>`,
      `<kiln:actor>`, `<kiln:control>`, `<kiln:npc_policy>`, `<kiln:action_map>`
    """
    xml_file = Path(xml_path)
    if not xml_file.exists():
        raise EnvBundleError(f"XML file does not exist: {xml_file}")

    try:
        root = ET.parse(xml_file).getroot()
    except Exception as e:
        raise EnvBundleError(f"Failed to parse XML file {xml_file}: {e}") from e

    root_name = _local_name(root.tag)
    if root_name not in {"mujoco", "kiln_env"}:
        raise EnvBundleError(f"Unsupported XML root <{root_name}>. Expected <mujoco>.")

    schema_raw = _get_attr(root, "schema_version", "1")
    schema_version = int(_parse_float(schema_raw, ctx="root.schema_version"))
    if schema_version != 1:
        raise EnvBundleError(f"Unsupported schema_version={schema_version}. Expected 1.")
    up_axis = (_get_attr(root, "up_axis", "z") or "z").strip().lower()
    if up_axis not in {"y", "z"}:
        raise EnvBundleError(f"Unsupported up_axis={up_axis!r}. Expected 'y' or 'z'.")

    mesh_files: dict[str, str] = {}
    asset = _first_child(root, "asset")
    if asset is not None:
        for i, mesh in enumerate(_iter_children(asset, "mesh")):
            name = _get_attr(mesh, "name", None)
            file = _get_attr(mesh, "file", None)
            if not name or not file:
                raise EnvBundleError(f"asset.mesh[{i}] requires both name and file")
            mesh_files[name] = file

    worldbody = _first_child(root, "worldbody")
    if worldbody is None:
        raise EnvBundleError("Missing required <worldbody> element")

    scene_file = _get_attr(root, "scene_file", "scene.usda")
    world = WorldSpec(enabled=False)
    world_set = False
    primitives: list[PrimitiveSpec] = []
    actors: list[ActorSpec] = []
    entity_ids: set[str] = set()

    for i, body in enumerate(_iter_children(worldbody, "body")):
        body_name = _get_attr(body, "name", f"body_{i}")
        pose = _parse_pose_from_body(body, ctx=f"worldbody.body[{i}]")

        geom = _first_child(body, "geom")
        if geom is None:
            continue
        geom_type = (_get_attr(geom, "type", "") or "").strip().lower()
        if not geom_type:
            raise EnvBundleError(f"worldbody.body[{i}] is missing geom@type")

        world_meta = _first_child(body, "world")
        primitive_meta = _first_child(body, "primitive")
        actor_meta = _first_child(body, "actor")
        is_world_body = bool(world_meta is not None) or geom_type == "mesh"

        if is_world_body:
            if world_set:
                raise EnvBundleError("Only one world mesh/body is supported in schema v1")

            source_file = _get_attr(world_meta, "source_file", None)
            if source_file is None:
                mesh_ref = _get_attr(geom, "mesh", None)
                if mesh_ref is not None:
                    source_file = mesh_files.get(mesh_ref, mesh_ref)
            if source_file is None:
                source_file = _get_attr(root, "scene_file", None)
            if source_file is None:
                raise EnvBundleError(
                    f"worldbody.body[{i}] is a world mesh but no source file could be resolved"
                )

            scene_file = source_file
            world = WorldSpec(
                enabled=_parse_bool_attr(world_meta, "enabled", default=True, ctx="world.enabled"),
                pose=pose,
                fixed=_parse_bool_attr(world_meta, "fixed", default=True, ctx="world.fixed"),
                collision=_parse_bool_attr(world_meta, "collision", default=True, ctx="world.collision"),
                visualization=_parse_bool_attr(
                    world_meta, "visualization", default=True, ctx="world.visualization"
                ),
                scale=_parse_float_attr(world_meta, "scale", default=1.0, ctx="world.scale"),
            )
            world_set = True
            continue

        if actor_meta is not None:
            actor_type = (_get_attr(actor_meta, "type", "") or "").strip().lower()
            if actor_type not in {"car_block", "npc_block"}:
                raise EnvBundleError(
                    f"Unsupported actor type {actor_type!r} for body {body_name!r}. "
                    "Only car_block/npc_block are supported."
                )
            actor_id = _get_attr(actor_meta, "id", body_name)
            if not actor_id:
                raise EnvBundleError(f"Missing actor id for body {body_name!r}")
            if actor_id == "world":
                raise EnvBundleError("Actor id 'world' is reserved")
            if actor_id in entity_ids:
                raise EnvBundleError(f"Duplicate entity id in XML: {actor_id!r}")
            entity_ids.add(actor_id)

            if geom_type != "box":
                raise EnvBundleError(
                    f"Actor {actor_id!r} must use geom type='box' in schema v1, got {geom_type!r}"
                )
            size_vals = _parse_geom_size(geom, ctx=f"{actor_id}.geom")
            if len(size_vals) != 3:
                raise EnvBundleError(
                    f"Actor {actor_id!r} expects box geom size with 3 half-extents, got {size_vals!r}"
                )
            size = (2.0 * size_vals[0], 2.0 * size_vals[1], 2.0 * size_vals[2])
            mass = _parse_optional_float_attr(geom, "mass", ctx=f"{actor_id}.geom.mass")
            if mass is None:
                mass = 1.0
            color = _parse_rgba(geom, ctx=f"{actor_id}.geom")

            control_mode = (_get_attr(actor_meta, "control_mode", "kinematic") or "kinematic").strip().lower()
            if control_mode not in {"kinematic", "force_torque"}:
                raise EnvBundleError(
                    f"Unsupported control_mode {control_mode!r} for actor {actor_id!r}. "
                    "Expected kinematic or force_torque."
                )

            control_meta = _first_child(actor_meta, "control")
            initial_yaw_default = _yaw_from_quat(pose.quat)
            max_speed = _parse_float_attr(control_meta, "max_speed", default=5.0, ctx=f"{actor_id}.control.max_speed")
            speed_delta = _parse_float_attr(
                control_meta, "speed_delta", default=0.5, ctx=f"{actor_id}.control.speed_delta"
            )
            turn_rate = _parse_float_attr(control_meta, "turn_rate", default=1.5, ctx=f"{actor_id}.control.turn_rate")
            force = _parse_float_attr(control_meta, "force", default=30.0, ctx=f"{actor_id}.control.force")
            torque = _parse_float_attr(control_meta, "torque", default=10.0, ctx=f"{actor_id}.control.torque")
            initial_yaw = _parse_float_attr(
                control_meta,
                "initial_yaw",
                default=initial_yaw_default,
                ctx=f"{actor_id}.control.initial_yaw",
            )

            action_meta = _first_child(actor_meta, "action_map")
            action_map = (
                _parse_int_attr(action_meta, "accelerate", default=0, ctx=f"{actor_id}.action_map.accelerate"),
                _parse_int_attr(action_meta, "decelerate", default=1, ctx=f"{actor_id}.action_map.decelerate"),
                _parse_int_attr(action_meta, "turn_left", default=2, ctx=f"{actor_id}.action_map.turn_left"),
                _parse_int_attr(action_meta, "turn_right", default=3, ctx=f"{actor_id}.action_map.turn_right"),
            )

            # Defaults mirror NPCBlockConfig in kiln/actors/npc.py.
            roam_xy_min: tuple[float, float] = (-5.0, -5.0)
            roam_xy_max: tuple[float, float] = (5.0, 5.0)
            goal_tolerance = 0.5
            cruise_speed = 2.0
            heading_threshold = 0.35
            raycast_length = 2.0
            raycast_angle = 0.45
            avoid_distance = 1.25
            brake_distance = 0.5
            avoid_radius = 1.0
            emergency_brake_radius = 0.6
            stuck_steps = 30
            progress_eps = 1e-3
            nav_cell_size = 0.5
            nav_inflate = 0.3
            waypoint_tolerance = 0.35
            max_goal_samples = 50

            if actor_type == "npc_block":
                policy_meta = _first_child(actor_meta, "npc_policy")
                roam_min_raw = _get_attr(policy_meta, "roam_xy_min", None)
                roam_max_raw = _get_attr(policy_meta, "roam_xy_max", None)
                if roam_min_raw is not None:
                    roam_min = _parse_vec(roam_min_raw, n=2, ctx=f"{actor_id}.npc_policy.roam_xy_min")
                    roam_xy_min = (roam_min[0], roam_min[1])
                if roam_max_raw is not None:
                    roam_max = _parse_vec(roam_max_raw, n=2, ctx=f"{actor_id}.npc_policy.roam_xy_max")
                    roam_xy_max = (roam_max[0], roam_max[1])

                goal_tolerance = _parse_float_attr(
                    policy_meta, "goal_tolerance", default=goal_tolerance, ctx=f"{actor_id}.npc_policy.goal_tolerance"
                )
                cruise_speed = _parse_float_attr(
                    policy_meta, "cruise_speed", default=cruise_speed, ctx=f"{actor_id}.npc_policy.cruise_speed"
                )
                heading_threshold = _parse_float_attr(
                    policy_meta,
                    "heading_threshold",
                    default=heading_threshold,
                    ctx=f"{actor_id}.npc_policy.heading_threshold",
                )
                raycast_length = _parse_float_attr(
                    policy_meta, "raycast_length", default=raycast_length, ctx=f"{actor_id}.npc_policy.raycast_length"
                )
                raycast_angle = _parse_float_attr(
                    policy_meta, "raycast_angle", default=raycast_angle, ctx=f"{actor_id}.npc_policy.raycast_angle"
                )
                avoid_distance = _parse_float_attr(
                    policy_meta, "avoid_distance", default=avoid_distance, ctx=f"{actor_id}.npc_policy.avoid_distance"
                )
                brake_distance = _parse_float_attr(
                    policy_meta, "brake_distance", default=brake_distance, ctx=f"{actor_id}.npc_policy.brake_distance"
                )
                avoid_radius = _parse_float_attr(
                    policy_meta, "avoid_radius", default=avoid_radius, ctx=f"{actor_id}.npc_policy.avoid_radius"
                )
                emergency_brake_radius = _parse_float_attr(
                    policy_meta,
                    "emergency_brake_radius",
                    default=emergency_brake_radius,
                    ctx=f"{actor_id}.npc_policy.emergency_brake_radius",
                )
                stuck_steps = _parse_int_attr(
                    policy_meta, "stuck_steps", default=stuck_steps, ctx=f"{actor_id}.npc_policy.stuck_steps"
                )
                progress_eps = _parse_float_attr(
                    policy_meta, "progress_eps", default=progress_eps, ctx=f"{actor_id}.npc_policy.progress_eps"
                )
                nav_cell_size = _parse_float_attr(
                    policy_meta, "nav_cell_size", default=nav_cell_size, ctx=f"{actor_id}.npc_policy.nav_cell_size"
                )
                nav_inflate = _parse_float_attr(
                    policy_meta, "nav_inflate", default=nav_inflate, ctx=f"{actor_id}.npc_policy.nav_inflate"
                )
                waypoint_tolerance = _parse_float_attr(
                    policy_meta,
                    "waypoint_tolerance",
                    default=waypoint_tolerance,
                    ctx=f"{actor_id}.npc_policy.waypoint_tolerance",
                )
                max_goal_samples = _parse_int_attr(
                    policy_meta,
                    "max_goal_samples",
                    default=max_goal_samples,
                    ctx=f"{actor_id}.npc_policy.max_goal_samples",
                )

            actors.append(
                ActorSpec(
                    id=actor_id,
                    actor_type=actor_type,
                    pose=pose,
                    size=size,
                    mass=float(mass),
                    color=color,
                    control_mode=control_mode,
                    max_speed=max_speed,
                    speed_delta=speed_delta,
                    turn_rate=turn_rate,
                    force=force,
                    torque=torque,
                    initial_yaw=initial_yaw,
                    action_map=action_map,
                    roam_xy_min=roam_xy_min,
                    roam_xy_max=roam_xy_max,
                    goal_tolerance=goal_tolerance,
                    cruise_speed=cruise_speed,
                    heading_threshold=heading_threshold,
                    raycast_length=raycast_length,
                    raycast_angle=raycast_angle,
                    avoid_distance=avoid_distance,
                    brake_distance=brake_distance,
                    avoid_radius=avoid_radius,
                    emergency_brake_radius=emergency_brake_radius,
                    stuck_steps=stuck_steps,
                    progress_eps=progress_eps,
                    nav_cell_size=nav_cell_size,
                    nav_inflate=nav_inflate,
                    waypoint_tolerance=waypoint_tolerance,
                    max_goal_samples=max_goal_samples,
                )
            )
            continue

        shape = (_get_attr(primitive_meta, "shape", geom_type) or "").strip().lower()
        if shape not in {"plane", "box", "sphere", "cylinder"}:
            raise EnvBundleError(
                f"Unsupported primitive shape {shape!r} for body {body_name!r}. "
                "Only plane/box/sphere/cylinder are supported."
            )

        prim_id = _get_attr(primitive_meta, "id", body_name)
        if not prim_id:
            raise EnvBundleError(f"Missing primitive id for body {body_name!r}")
        if prim_id == "world":
            raise EnvBundleError("Primitive id 'world' is reserved")
        if prim_id in entity_ids:
            raise EnvBundleError(f"Duplicate primitive id in XML: {prim_id!r}")
        entity_ids.add(prim_id)

        mass = _parse_optional_float_attr(primitive_meta, "mass", ctx=f"{prim_id}.mass")
        if mass is None:
            mass = _parse_optional_float_attr(geom, "mass", ctx=f"{prim_id}.geom.mass")

        fixed = _parse_optional_bool_attr(primitive_meta, "fixed", ctx=f"{prim_id}.fixed")
        if fixed is None:
            if (mass is not None) and (mass > 0.0):
                fixed = False
            else:
                fixed = True
        collision = _parse_bool_attr(
            primitive_meta,
            "collision",
            default=_geom_collision_default(geom),
            ctx=f"{prim_id}.collision",
        )
        visualization = _parse_bool_attr(
            primitive_meta,
            "visualization",
            default=True,
            ctx=f"{prim_id}.visualization",
        )
        color = _parse_rgba(geom, ctx=f"{prim_id}.geom")

        size: tuple[float, float, float] | None = None
        radius: float | None = None
        height: float | None = None
        normal: tuple[float, float, float] | None = None
        size_vals = _parse_geom_size(geom, ctx=f"{prim_id}.geom")

        if shape == "box":
            if len(size_vals) != 3:
                raise EnvBundleError(
                    f"Box primitive {prim_id!r} expects geom size with 3 half-extents, got {size_vals!r}"
                )
            size = (2.0 * size_vals[0], 2.0 * size_vals[1], 2.0 * size_vals[2])
        elif shape == "sphere":
            if not size_vals:
                raise EnvBundleError(f"Sphere primitive {prim_id!r} expects geom size with radius")
            radius = float(size_vals[0])
        elif shape == "cylinder":
            if len(size_vals) < 2:
                raise EnvBundleError(
                    f"Cylinder primitive {prim_id!r} expects geom size with radius and half-height"
                )
            radius = float(size_vals[0])
            height = float(2.0 * size_vals[1])
        elif shape == "plane":
            normal_vals = _parse_optional_vec(_get_attr(primitive_meta, "normal", None), n=3, ctx=f"{prim_id}.normal")
            if normal_vals is not None:
                normal = (normal_vals[0], normal_vals[1], normal_vals[2])

        primitives.append(
            PrimitiveSpec(
                id=prim_id,
                shape=shape,
                pose=pose,
                fixed=fixed,
                mass=mass,
                collision=collision,
                visualization=visualization,
                color=color,
                size=size,
                radius=radius,
                height=height,
                normal=normal,
            )
        )

    spawn_points: dict[str, Pose] = {}
    spawn_parent = _first_child(root, "spawn_points")
    if spawn_parent is not None:
        for i, spawn in enumerate(_iter_children(spawn_parent, "spawn")):
            name = _get_attr(spawn, "name", None)
            if not name:
                raise EnvBundleError(f"spawn_points.spawn[{i}] is missing name")
            if name in spawn_points:
                raise EnvBundleError(f"Duplicate spawn point name {name!r}")
            spawn_points[name] = _parse_pose_from_body(spawn, ctx=f"spawn_points.spawn[{name!r}]")
    if not spawn_points:
        spawn_points = {"default": Pose(pos=(0.0, 0.0, 0.5))}

    parsed = EnvXmlBundle(
        schema_version=1,
        scene_file=scene_file,
        world=world,
        primitives=tuple(primitives),
        spawn_points=spawn_points,
        actors=tuple(actors),
    )
    if up_axis == "y":
        return _canonicalize_y_up_bundle(parsed)
    return parsed


from __future__ import annotations

"""MJCF-style XML loader for Kiln env bundles."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterator

from .bundle import EnvBundleError, EnvBundleV1, Pose, PrimitiveSpec, WorldSpec

KILN_NS = "urn:kiln:mjcf:v1"
_KILN_ATTR_PREFIX = f"{{{KILN_NS}}}"


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


def load_env_xml_bundle(xml_path: str | Path) -> EnvBundleV1:
    """
    Parse a MuJoCo-style XML scene into `EnvBundleV1`.

    Supported subset:
    - `<mujoco ... xmlns:kiln="urn:kiln:mjcf:v1">`
    - `<asset><mesh .../></asset>` for world mesh indirection
    - `<worldbody><body ...><geom .../></body></worldbody>`
    - Kiln extension tags: `<kiln:world>`, `<kiln:primitive>`, `<kiln:spawn_points>`
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
    primitive_ids: set[str] = set()

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
        if prim_id in primitive_ids:
            raise EnvBundleError(f"Duplicate primitive id in XML: {prim_id!r}")
        primitive_ids.add(prim_id)

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

    return EnvBundleV1(
        schema_version=1,
        scene_file=scene_file,
        world=world,
        primitives=tuple(primitives),
        spawn_points=spawn_points,
    )


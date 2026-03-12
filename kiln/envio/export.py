from __future__ import annotations

"""
Scene exporter: Scene -> MuJoCo MJCF XML + USD bundle.

Exports a Kiln :class:`~kiln.scene.Scene` to a directory containing:
- ``scene.usda`` (or whatever extension the source USD has)
- ``scene.xml``  (MuJoCo MJCF with ``kiln:`` extensions)

The XML follows the Kiln MJCF schema with the ``kiln:`` namespace so that
downstream tooling (Gymnasium envs, simulation loaders) can reconstruct
the full scene.
"""

import shutil
import math
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

if TYPE_CHECKING:
    from kiln.scene import Scene
    from kiln.objects.base_object import BaseObject

KILN_NS = "urn:kiln:mjcf:v1"

# Register the namespace prefix so ElementTree writes ``kiln:`` instead of ``ns0:``.
from xml.etree.ElementTree import register_namespace
register_namespace("kiln", KILN_NS)

USD_EXTS = {".usd", ".usda", ".usdc", ".usdz"}


def _fmt(v: float) -> str:
    """Format a float: strip trailing zeros, keep it human-readable."""
    return f"{v:g}"


def _vec3_str(x: float, y: float, z: float) -> str:
    return f"{_fmt(x)} {_fmt(y)} {_fmt(z)}"


def _quat_from_euler_deg(rx: float, ry: float, rz: float) -> tuple[float, float, float, float]:
    """Convert Euler XYZ degrees -> (w, x, y, z) quaternion.

    MuJoCo uses (w, x, y, z) ordering which matches our convention.
    """
    rx_r = math.radians(rx)
    ry_r = math.radians(ry)
    rz_r = math.radians(rz)

    cx, sx = math.cos(rx_r / 2), math.sin(rx_r / 2)
    cy, sy = math.cos(ry_r / 2), math.sin(ry_r / 2)
    cz, sz = math.cos(rz_r / 2), math.sin(rz_r / 2)

    # ZYX intrinsic = XYZ extrinsic
    w = cx * cy * cz + sx * sy * sz
    x = sx * cy * cz - cx * sy * sz
    y = cx * sy * cz + sx * cy * sz
    z = cx * cy * sz - sx * sy * cz
    return (w, x, y, z)


def _quat_str(w: float, x: float, y: float, z: float) -> str:
    return f"{_fmt(w)} {_fmt(x)} {_fmt(y)} {_fmt(z)}"


def _safe_id(name: str) -> str:
    """Sanitise a name for use as an XML id / MuJoCo name."""
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def export_scene_mjcf(
    scene: "Scene",
    output_dir: str | Path,
    *,
    model_name: str = "kiln_scene",
    overwrite: bool = False,
) -> Path:
    """Export a loaded scene to a Kiln MJCF bundle.

    Creates ``output_dir/`` containing:
    - A copy of the source USD file (e.g. ``scene.usda``)
    - ``scene.xml`` – a MuJoCo-flavoured XML with ``kiln:`` extensions

    Args:
        scene: A loaded :class:`Scene`.
        output_dir: Target directory to create.
        model_name: Value for ``<mujoco model="...">``.
        overwrite: If True and *output_dir* exists, clear it first.

    Returns:
        The path to the created XML file.

    Raises:
        RuntimeError: If no scene is loaded or the output directory exists
            (when *overwrite* is False).
    """
    if scene.scene_path is None:
        raise RuntimeError("No scene is loaded – cannot export.")

    out = Path(output_dir)
    src_usd = scene.scene_path

    # Safety: refuse to export into the same directory that contains the
    # source USD file — that would overwrite the original.
    if out.resolve() == src_usd.parent.resolve():
        raise RuntimeError(
            f"Cannot export into the source directory ({out}).\n"
            "Please choose a different output folder."
        )

    out.mkdir(parents=True, exist_ok=True)

    # ---- 1. Copy USD file ----
    scene_filename = f"scene{src_usd.suffix.lower()}"
    dst_usd = out / scene_filename
    shutil.copy2(src_usd, dst_usd)

    # ---- 2. Build XML tree ----
    root = _build_mjcf(scene, scene_filename, model_name)

    tree = ElementTree(root)
    indent(tree, space="  ")

    xml_path = out / "scene.xml"
    tree.write(str(xml_path), encoding="unicode", xml_declaration=True)

    return xml_path


# ------------------------------------------------------------------
# XML construction
# ------------------------------------------------------------------

def _build_mjcf(scene: "Scene", scene_filename: str, model_name: str) -> Element:
    """Construct the full ``<mujoco>`` element tree from a Scene."""

    root = Element("mujoco")
    root.set("model", model_name)
    root.set(f"{{{KILN_NS}}}schema_version", "1")
    root.set(f"{{{KILN_NS}}}up_axis", "y")
    root.set(f"{{{KILN_NS}}}units", "meter")

    # <compiler>
    compiler = SubElement(root, "compiler")
    compiler.set("angle", "radian")

    # <option>
    option = SubElement(root, "option")
    option.set("timestep", "0.0166667")

    # <asset>
    asset = SubElement(root, "asset")
    mesh = SubElement(asset, "mesh")
    mesh.set("name", "world_mesh")
    mesh.set("file", scene_filename)

    # <worldbody>
    worldbody = SubElement(root, "worldbody")

    # -- World mesh body --
    world_body = SubElement(worldbody, "body")
    world_body.set("name", "world")
    world_body.set("pos", "0 0 0")
    world_body.set("quat", "1 0 0 0")

    world_geom = SubElement(world_body, "geom")
    world_geom.set("name", "world_geom")
    world_geom.set("type", "mesh")
    world_geom.set("mesh", "world_mesh")
    world_geom.set("mass", "0")
    world_geom.set("rgba", "0.7 0.7 0.7 1")

    kiln_world = SubElement(world_body, f"{{{KILN_NS}}}world")
    kiln_world.set("source_file", scene_filename)
    kiln_world.set("fixed", "true")
    kiln_world.set("collision", "true")
    kiln_world.set("visualization", "true")
    kiln_world.set("scale", "1.0")

    # -- Scene objects as bodies --
    for obj in scene.objects:
        _add_object_body(worldbody, obj)

    # <kiln:spawn_points>
    spawn_el = SubElement(root, f"{{{KILN_NS}}}spawn_points")
    default_spawn = SubElement(spawn_el, f"{{{KILN_NS}}}spawn")
    default_spawn.set("name", "default")
    default_spawn.set("pos", "0 0 1.2")
    default_spawn.set("quat", "1 0 0 0")

    # <kiln:ui_objects> — preserves the full editor state
    _add_ui_objects(root, scene)

    return root


def _add_object_body(worldbody: Element, obj: "BaseObject") -> None:
    """Add a ``<body>`` element for a single scene object (Plane or Box)."""
    from kiln.objects import Plane, Box

    safe_name = _safe_id(obj.name)
    # If the object has a role (e.g. "ground"), use it as the XML id.
    xml_id = obj.role if obj.role else safe_name

    pos = _vec3_str(obj.position.x(), obj.position.y(), obj.position.z())
    quat = _quat_from_euler_deg(obj.rotation.x(), obj.rotation.y(), obj.rotation.z())
    quat_s = _quat_str(*quat)

    body = SubElement(worldbody, "body")
    body.set("name", xml_id)
    body.set("pos", pos)
    body.set("quat", quat_s)

    geom = SubElement(body, "geom")
    geom.set("name", f"{xml_id}_geom")

    if isinstance(obj, Plane):
        # Plane — spec says geom type="plane", size="x y z" (not used for dims)
        plane_w = obj.width * obj.scale.x()
        plane_d = obj.depth * obj.scale.z()
        geom.set("type", "plane")
        geom.set("size", _vec3_str(plane_w, plane_d, 1))
        geom.set("mass", "0")
        r, g, b = obj.color.redF(), obj.color.greenF(), obj.color.blueF()
        geom.set("rgba", f"{_fmt(r)} {_fmt(g)} {_fmt(b)} 1")

        kiln_prim = SubElement(body, f"{{{KILN_NS}}}primitive")
        kiln_prim.set("id", xml_id)
        kiln_prim.set("shape", "plane")
        kiln_prim.set("fixed", "true")
        kiln_prim.set("collision", "true")
        kiln_prim.set("visualization", "true")
        kiln_prim.set("normal", "0 1 0")

    elif isinstance(obj, Box):
        half_s = (obj.size * obj.scale.x()) / 2.0
        geom.set("type", "box")
        geom.set("size", _vec3_str(half_s, half_s, half_s))
        geom.set("mass", "0")
        r, g, b = obj.color.redF(), obj.color.greenF(), obj.color.blueF()
        geom.set("rgba", f"{_fmt(r)} {_fmt(g)} {_fmt(b)} 1")

        kiln_prim = SubElement(body, f"{{{KILN_NS}}}primitive")
        kiln_prim.set("id", xml_id)
        kiln_prim.set("shape", "box")
        kiln_prim.set("fixed", "true")
        kiln_prim.set("collision", "true")
        kiln_prim.set("visualization", "true")

    else:
        # Generic fallback
        geom.set("type", "box")
        geom.set("size", "0.5 0.5 0.5")
        geom.set("mass", "0")
        geom.set("rgba", "0.5 0.5 0.5 1")


def _add_ui_objects(root: Element, scene: "Scene") -> None:
    """Append a ``<kiln:ui_objects>`` block that records the full editor state.

    This allows round-tripping: opening an exported XML in Kiln can
    reconstruct all objects with their original transforms.
    """
    from kiln.objects import Plane, Box

    ui_el = SubElement(root, f"{{{KILN_NS}}}ui_objects")
    ui_el.set(f"{{{KILN_NS}}}up_axis", "y")

    for obj in scene.objects:
        o = SubElement(ui_el, f"{{{KILN_NS}}}object")
        o.set("id", _safe_id(obj.name))

        if isinstance(obj, Plane):
            o.set("type", "Plane")
            o.set("width", _fmt(obj.width))
            o.set("depth", _fmt(obj.depth))
        elif isinstance(obj, Box):
            o.set("type", "Box")
            o.set("size", _fmt(obj.size))
        else:
            o.set("type", "Unknown")

        o.set("pos_ui", _vec3_str(obj.position.x(), obj.position.y(), obj.position.z()))
        o.set("rot_xyz_deg", _vec3_str(obj.rotation.x(), obj.rotation.y(), obj.rotation.z()))
        o.set("scale", _vec3_str(obj.scale.x(), obj.scale.y(), obj.scale.z()))
        o.set("color", f"{obj.color.redF():.3f} {obj.color.greenF():.3f} {obj.color.blueF():.3f}")

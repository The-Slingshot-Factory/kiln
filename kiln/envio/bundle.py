from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, MutableMapping, Sequence, TypeAlias

Vec3: TypeAlias = tuple[float, float, float]
Quat4: TypeAlias = tuple[float, float, float, float]  # (w, x, y, z) to match Genesis
RGB: TypeAlias = tuple[float, float, float]
RGBA: TypeAlias = tuple[float, float, float, float]
Color: TypeAlias = RGB | RGBA


class EnvBundleError(RuntimeError):
    pass


def _as_float(x: Any, *, ctx: str) -> float:
    try:
        return float(x)
    except Exception as e:
        raise EnvBundleError(f"Expected a number for {ctx}, got {x!r}") from e


def _as_bool(x: Any, *, ctx: str) -> bool:
    if isinstance(x, bool):
        return x
    raise EnvBundleError(f"Expected a boolean for {ctx}, got {x!r}")


def _as_str(x: Any, *, ctx: str) -> str:
    if isinstance(x, str):
        return x
    raise EnvBundleError(f"Expected a string for {ctx}, got {x!r}")


def _as_vec3(x: Any, *, ctx: str) -> Vec3:
    if not isinstance(x, (list, tuple)) or len(x) != 3:
        raise EnvBundleError(f"Expected a 3-list for {ctx}, got {x!r}")
    return (_as_float(x[0], ctx=f"{ctx}[0]"), _as_float(x[1], ctx=f"{ctx}[1]"), _as_float(x[2], ctx=f"{ctx}[2]"))


def _as_quat4(x: Any, *, ctx: str) -> Quat4:
    if not isinstance(x, (list, tuple)) or len(x) != 4:
        raise EnvBundleError(f"Expected a 4-list (w,x,y,z) for {ctx}, got {x!r}")
    return (
        _as_float(x[0], ctx=f"{ctx}[0]"),
        _as_float(x[1], ctx=f"{ctx}[1]"),
        _as_float(x[2], ctx=f"{ctx}[2]"),
        _as_float(x[3], ctx=f"{ctx}[3]"),
    )


def _as_color(x: Any, *, ctx: str) -> Color:
    if not isinstance(x, (list, tuple)) or (len(x) not in (3, 4)):
        raise EnvBundleError(f"Expected an RGB/RGBA list for {ctx}, got {x!r}")
    vals = tuple(_as_float(v, ctx=f"{ctx}[{i}]") for i, v in enumerate(x))
    if len(vals) == 3:
        return (vals[0], vals[1], vals[2])
    return (vals[0], vals[1], vals[2], vals[3])


@dataclass(frozen=True)
class Pose:
    pos: Vec3 = (0.0, 0.0, 0.0)
    quat: Quat4 = (1.0, 0.0, 0.0, 0.0)

    @staticmethod
    def from_json(obj: Any, *, ctx: str) -> "Pose":
        if obj is None:
            return Pose()
        if not isinstance(obj, Mapping):
            raise EnvBundleError(f"Expected an object for {ctx}, got {obj!r}")
        pos = _as_vec3(obj.get("pos", (0.0, 0.0, 0.0)), ctx=f"{ctx}.pos")
        quat = _as_quat4(obj.get("quat", (1.0, 0.0, 0.0, 0.0)), ctx=f"{ctx}.quat")
        return Pose(pos=pos, quat=quat)

    def to_json(self) -> dict[str, list[float]]:
        return {"pos": [float(self.pos[0]), float(self.pos[1]), float(self.pos[2])], "quat": [float(q) for q in self.quat]}


@dataclass(frozen=True)
class WorldSpec:
    enabled: bool = True
    pose: Pose = field(default_factory=Pose)
    fixed: bool = True
    collision: bool = True
    visualization: bool = True
    scale: float = 1.0

    @staticmethod
    def from_json(obj: Any, *, ctx: str) -> "WorldSpec":
        if obj is None:
            return WorldSpec()
        if not isinstance(obj, Mapping):
            raise EnvBundleError(f"Expected an object for {ctx}, got {obj!r}")
        return WorldSpec(
            enabled=_as_bool(obj.get("enabled", True), ctx=f"{ctx}.enabled"),
            pose=Pose.from_json(obj.get("pose", None), ctx=f"{ctx}.pose"),
            fixed=_as_bool(obj.get("fixed", True), ctx=f"{ctx}.fixed"),
            collision=_as_bool(obj.get("collision", True), ctx=f"{ctx}.collision"),
            visualization=_as_bool(obj.get("visualization", True), ctx=f"{ctx}.visualization"),
            scale=_as_float(obj.get("scale", 1.0), ctx=f"{ctx}.scale"),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "pose": self.pose.to_json(),
            "fixed": bool(self.fixed),
            "collision": bool(self.collision),
            "visualization": bool(self.visualization),
            "scale": float(self.scale),
        }


PrimitiveShape: TypeAlias = Literal["plane", "box", "sphere", "cylinder"]


@dataclass(frozen=True)
class PrimitiveSpec:
    id: str
    shape: PrimitiveShape
    pose: Pose = field(default_factory=Pose)
    fixed: bool | None = None
    mass: float | None = None
    collision: bool = True
    visualization: bool = True
    color: Color | None = None
    # shape params
    size: Vec3 | None = None  # box
    radius: float | None = None  # sphere/cylinder
    height: float | None = None  # cylinder
    normal: Vec3 | None = None  # plane

    @staticmethod
    def from_json(obj: Any, *, ctx: str) -> "PrimitiveSpec":
        if not isinstance(obj, Mapping):
            raise EnvBundleError(f"Expected an object for {ctx}, got {obj!r}")
        pid = _as_str(obj.get("id", ""), ctx=f"{ctx}.id")
        if not pid:
            raise EnvBundleError(f"Missing non-empty {ctx}.id")
        shape = _as_str(obj.get("shape", ""), ctx=f"{ctx}.shape")
        if shape not in ("plane", "box", "sphere", "cylinder"):
            raise EnvBundleError(f"Unsupported {ctx}.shape={shape!r}")

        fixed = obj.get("fixed", None)
        if fixed is not None:
            fixed = _as_bool(fixed, ctx=f"{ctx}.fixed")

        mass = obj.get("mass", None)
        if mass is not None:
            mass = _as_float(mass, ctx=f"{ctx}.mass")

        # Defaulting rules:
        # - if fixed is explicitly set, trust it
        # - else if mass is provided and > 0, assume dynamic
        # - else default to fixed (safe for v1)
        if fixed is None:
            if (mass is not None) and (mass > 0.0):
                fixed = False
            else:
                fixed = True

        color = obj.get("color", None)
        if color is not None:
            color = _as_color(color, ctx=f"{ctx}.color")

        pose = Pose.from_json(obj.get("pose", None), ctx=f"{ctx}.pose")
        collision = _as_bool(obj.get("collision", True), ctx=f"{ctx}.collision")
        visualization = _as_bool(obj.get("visualization", True), ctx=f"{ctx}.visualization")

        size = obj.get("size", None)
        radius = obj.get("radius", None)
        height = obj.get("height", None)
        normal = obj.get("normal", None)

        if shape == "box":
            if size is None:
                raise EnvBundleError(f"Missing {ctx}.size for box")
            size = _as_vec3(size, ctx=f"{ctx}.size")
        elif shape == "sphere":
            if radius is None:
                raise EnvBundleError(f"Missing {ctx}.radius for sphere")
            radius = _as_float(radius, ctx=f"{ctx}.radius")
        elif shape == "cylinder":
            if radius is None or height is None:
                raise EnvBundleError(f"Missing {ctx}.radius/height for cylinder")
            radius = _as_float(radius, ctx=f"{ctx}.radius")
            height = _as_float(height, ctx=f"{ctx}.height")
        elif shape == "plane":
            if normal is not None:
                normal = _as_vec3(normal, ctx=f"{ctx}.normal")

        return PrimitiveSpec(
            id=pid,
            shape=shape,  # type: ignore[arg-type]
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

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "shape": self.shape,
            "pose": self.pose.to_json(),
            "fixed": bool(self.fixed) if self.fixed is not None else None,
            "mass": float(self.mass) if self.mass is not None else None,
            "collision": bool(self.collision),
            "visualization": bool(self.visualization),
        }
        if self.color is not None:
            out["color"] = [float(v) for v in self.color]
        if self.shape == "box":
            assert self.size is not None
            out["size"] = [float(v) for v in self.size]
        elif self.shape == "sphere":
            assert self.radius is not None
            out["radius"] = float(self.radius)
        elif self.shape == "cylinder":
            assert self.radius is not None and self.height is not None
            out["radius"] = float(self.radius)
            out["height"] = float(self.height)
        elif self.shape == "plane":
            if self.normal is not None:
                out["normal"] = [float(v) for v in self.normal]

        # drop None values for cleaner JSON
        return {k: v for k, v in out.items() if v is not None}


@dataclass(frozen=True)
class EnvBundleV1:
    schema_version: int = 1
    scene_file: str = "scene.usda"
    world: WorldSpec = field(default_factory=WorldSpec)
    primitives: tuple[PrimitiveSpec, ...] = ()
    spawn_points: Mapping[str, Pose] = field(default_factory=lambda: {"default": Pose(pos=(0.0, 0.0, 0.5))})

    def resolve_scene_path(self, bundle_dir: Path) -> Path:
        if Path(self.scene_file).is_absolute():
            raise EnvBundleError(f"scene_file must be a relative path, got {self.scene_file!r}")
        bundle_root = bundle_dir.resolve()
        scene_path = (bundle_dir / self.scene_file).resolve()
        if bundle_root not in scene_path.parents and bundle_root != scene_path:
            raise EnvBundleError(f"scene_file escapes bundle dir: {self.scene_file!r}")
        return scene_path

    @staticmethod
    def from_json(obj: Any, *, ctx: str = "env") -> "EnvBundleV1":
        if not isinstance(obj, Mapping):
            raise EnvBundleError(f"Expected a JSON object for {ctx}, got {obj!r}")
        schema_version = int(obj.get("schema_version", 0))
        if schema_version != 1:
            raise EnvBundleError(f"Unsupported schema_version={schema_version}. Expected 1.")
        scene_file = _as_str(obj.get("scene_file", "scene.usda"), ctx=f"{ctx}.scene_file")

        world = WorldSpec.from_json(obj.get("world", None), ctx=f"{ctx}.world")

        primitives_raw = obj.get("primitives", [])
        if primitives_raw is None:
            primitives_raw = []
        if not isinstance(primitives_raw, Sequence) or isinstance(primitives_raw, (str, bytes)):
            raise EnvBundleError(f"Expected a list for {ctx}.primitives, got {primitives_raw!r}")
        primitives = tuple(PrimitiveSpec.from_json(p, ctx=f"{ctx}.primitives[{i}]") for i, p in enumerate(primitives_raw))

        sp_raw = obj.get("spawn_points", {}) or {}
        if not isinstance(sp_raw, Mapping):
            raise EnvBundleError(f"Expected an object for {ctx}.spawn_points, got {sp_raw!r}")
        spawn_points: dict[str, Pose] = {}
        for k, v in sp_raw.items():
            name = _as_str(k, ctx=f"{ctx}.spawn_points key")
            spawn_points[name] = Pose.from_json(v, ctx=f"{ctx}.spawn_points[{name!r}]")
        if not spawn_points:
            spawn_points = {"default": Pose(pos=(0.0, 0.0, 0.5))}

        return EnvBundleV1(
            schema_version=1,
            scene_file=scene_file,
            world=world,
            primitives=primitives,
            spawn_points=spawn_points,
        )

    def to_json(self) -> dict[str, Any]:
        spawn_points: dict[str, Any] = {k: v.to_json() for k, v in self.spawn_points.items()}
        return {
            "schema_version": int(self.schema_version),
            "scene_file": self.scene_file,
            "world": self.world.to_json(),
            "primitives": [p.to_json() for p in self.primitives],
            "spawn_points": spawn_points,
        }


EnvBundle: TypeAlias = EnvBundleV1


def load_env_bundle(bundle_dir: str | Path, *, env_filename: str = "env.json") -> EnvBundle:
    bundle_path = Path(bundle_dir)
    env_path = bundle_path / env_filename
    if not env_path.exists():
        raise EnvBundleError(f"Missing env bundle file: {env_path}")
    try:
        obj = json.loads(env_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise EnvBundleError(f"Failed to read {env_path}: {e}") from e
    bundle = EnvBundleV1.from_json(obj, ctx=env_filename)
    # validate scene path exists when world is enabled
    if bundle.world.enabled:
        scene_path = bundle.resolve_scene_path(bundle_path)
        if not scene_path.exists():
            raise EnvBundleError(f"Missing scene file referenced by env.json: {scene_path}")
    return bundle


def save_env_bundle(
    bundle_dir: str | Path,
    bundle: EnvBundle,
    *,
    env_filename: str = "env.json",
) -> Path:
    bundle_path = Path(bundle_dir)
    bundle_path.mkdir(parents=True, exist_ok=True)
    env_path = bundle_path / env_filename
    data = bundle.to_json()
    # Ensure stable formatting for diffs.
    env_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return env_path



from __future__ import annotations

import math
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _maybe_prepend_wsl_libcuda_path(*, reexec: bool = False) -> None:
    """
    WSL CUDA quirk:

    Some WSL setups end up with a *Linux* NVIDIA driver `libcuda.so` present under
    `/lib/x86_64-linux-gnu/` which can cause Taichi/Genesis CUDA init to fail with:
      CUDA_ERROR_NO_DEVICE: no CUDA-capable device is detected while calling init (cuInit)

    Prepending the WSL shim path `/usr/lib/wsl/lib` ensures we pick up the correct
    WSL-provided libcuda shim.

    This is a no-op on non-WSL systems.

    IMPORTANT: In practice, Taichi's CUDA initialization may require this path to be present
    at *process start* (glibc caches the loader search path). When `reexec=True`, this
    function will `exec()` the current Python process with an updated `LD_LIBRARY_PATH`
    to make the fix reliable.
    """

    wsl_dir = Path("/usr/lib/wsl/lib")
    if not wsl_dir.exists():
        return

    # Be conservative: only apply if we appear to be running under a WSL kernel.
    try:
        osrelease = Path("/proc/sys/kernel/osrelease").read_text().strip().lower()
    except Exception:
        osrelease = platform.release().strip().lower()

    if ("microsoft" not in osrelease) and ("wsl" not in osrelease):
        return

    wsl_path = str(wsl_dir)
    ld = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in ld.split(":") if p]

    if parts and parts[0] == wsl_path:
        return

    if wsl_path in parts:
        parts = [wsl_path] + [p for p in parts if p != wsl_path]
    else:
        parts.insert(0, wsl_path)

    new_ld = ":".join(parts)

    if not reexec:
        os.environ["LD_LIBRARY_PATH"] = new_ld
        return

    # Re-exec once to ensure the dynamic loader sees the updated LD_LIBRARY_PATH.
    if os.environ.get("KILN_WSL_LIBCUDA_REEXECED") == "1":
        os.environ["LD_LIBRARY_PATH"] = new_ld
        return

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = new_ld
    env["KILN_WSL_LIBCUDA_REEXECED"] = "1"
    os.execvpe(sys.executable, [sys.executable, *sys.argv], env)


def _import_genesis():
    try:
        import genesis as gs  # type: ignore
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "Genesis is not installed. Install it with: python -m pip install -e \".[sim]\" "
            "(and install PyTorch separately per Genesis docs)."
        ) from e
    return gs


def _normalize_rgb(color: tuple[float, ...]) -> tuple[float, ...]:
    # Accept either 0..1 floats or 0..255 ints/floats.
    if not color:
        return color
    if max(color) > 1.0:
        return tuple(float(c) / 255.0 for c in color)
    return tuple(float(c) for c in color)


@dataclass(frozen=True)
class GenesisSimConfig:
    dt: float = 1.0 / 60.0
    substeps: int = 1
    headless: bool = True
    seed: int | None = None
    # Genesis backend selector. Common values: "cpu", "gpu", "cuda", "vulkan".
    # If None, Genesis chooses its default backend for the platform.
    backend: str | None = None


@dataclass(frozen=True)
class RaycastHit:
    hit: bool
    distance: float | None = None
    position: tuple[float, float, float] | None = None
    normal: tuple[float, float, float] | None = None
    # Optional: entity/prim identifiers if Genesis exposes them
    collider: Any | None = None


class GenesisSim:
    """
    Thin adapter around a Genesis `Scene`.

    Design goals:
    - Keep a small surface area so we can later swap in USD-driven scene creation.
    - Avoid importing Genesis unless this backend is actually used (UI can run without it).
    """

    def __init__(self, config: GenesisSimConfig | None = None):
        self.config = config or GenesisSimConfig()
        self._gs = None
        self.scene = None
        self._built = False
        # Cache 6-DoF velocity/force vectors per entity (Genesis rigid entities are controlled
        # through dof vectors). This lets higher-level code set linear and angular parts
        # separately without clobbering the other.
        self._vel6_cache: dict[int, tuple[float, float, float, float, float, float]] = {}
        self._force6_cache: dict[int, tuple[float, float, float, float, float, float]] = {}

    # ----------------------------
    # Lifecycle / scene management
    # ----------------------------
    def init(self) -> None:
        # Must happen before importing Genesis/Taichi so dynamic library resolution is correct.
        # NOTE: On WSL + CUDA this may re-exec the process (once) to make the loader fix reliable.
        want_cuda = (str(self.config.backend).strip().lower() if self.config.backend is not None else "") in {
            "cuda",
            "gpu",
        }
        _maybe_prepend_wsl_libcuda_path(reexec=want_cuda)

        gs = _import_genesis()
        self._gs = gs

        # Genesis typically requires an explicit init(). Keep this best-effort and permissive
        # across versions by trying a few common call signatures.
        if hasattr(gs, "init"):
            init_kwargs: dict[str, Any] = {}
            if self.config.seed is not None:
                init_kwargs["seed"] = self.config.seed

            if self.config.backend is not None:
                b = str(self.config.backend).strip().lower()
                # Prefer Genesis' own backend enum (varies by version). Try a few patterns.
                backend_val: Any | None = None
                if hasattr(gs, b):
                    backend_val = getattr(gs, b)
                else:
                    backend_enum = getattr(gs, "gs_backend", None)
                    if backend_enum is not None and hasattr(backend_enum, b):
                        backend_val = getattr(backend_enum, b)
                    else:
                        try:
                            # Fallback to the canonical enum class in genesis.constants.
                            from genesis.constants import backend as gs_backend  # type: ignore

                            if hasattr(gs_backend, b):
                                backend_val = getattr(gs_backend, b)
                        except Exception:
                            backend_val = None

                # If we couldn't resolve, pass the string through (some versions may accept it).
                init_kwargs["backend"] = backend_val if backend_val is not None else self.config.backend

            try:
                gs.init(**init_kwargs)
            except TypeError:
                # Older/newer signatures: fall back by dropping newer kwargs first.
                if init_kwargs:
                    init_kwargs.pop("backend", None)
                try:
                    if init_kwargs:
                        gs.init(**init_kwargs)
                    else:
                        gs.init()
                except TypeError:
                    gs.init()

    def close(self) -> None:
        # Genesis doesn't always expose an explicit shutdown; keep as a no-op.
        self.scene = None
        self._built = False
        self._vel6_cache.clear()
        self._force6_cache.clear()

    def create_programmatic_scene(self, *, with_default_ground: bool = True) -> Any:
        """
        Create a minimal scene programmatically (no USD).

        Returns the underlying Genesis scene object.
        """
        if self._gs is None:
            self.init()
        gs = self._gs

        # Best-effort scene creation. Prefer disabling the viewer for headless runs.
        scene_kwargs: dict[str, Any] = {}
        if hasattr(gs, "options") and hasattr(gs.options, "SimOptions"):
            try:
                scene_kwargs["sim_options"] = gs.options.SimOptions(dt=self.config.dt, substeps=self.config.substeps)
            except Exception:
                # Keep this optional across Genesis versions.
                pass

        # Genesis 0.3.x supports show_viewer=...
        scene_kwargs["show_viewer"] = (not self.config.headless)
        scene = gs.Scene(**scene_kwargs)  # type: ignore[attr-defined]

        self.scene = scene
        self._built = False
        self._vel6_cache.clear()
        self._force6_cache.clear()

        if with_default_ground:
            # Add a ground plane if available.
            try:
                # Dark ground so colored blocks stand out in rendered demos.
                self.add_ground_plane(color=(0.18, 0.18, 0.18))
            except Exception:
                # Ground is optional; demo can still run in free space.
                pass

        return scene

    def build(self) -> None:
        if self.scene is None:
            raise RuntimeError("Scene is not created.")
        if self._built:
            return
        if hasattr(self.scene, "build"):
            self.scene.build()
        self._built = True

    def load_scene_from_usd(self, usd_path: str | Path) -> Any:
        """
        Minimal USD loader (v1):
        - Create an empty Genesis scene
        - Load the USD geometry as a single fixed mesh entity

        This supports the GUI→bundle→runtime pipeline, but does not yet implement
        per-prim semantics (that lives in the env.json sidecar).
        """
        if self._gs is None:
            self.init()
        gs = self._gs

        self.create_programmatic_scene(with_default_ground=False)
        if self.scene is None:
            raise RuntimeError("Scene is not created.")

        usd_path = Path(usd_path)
        if not usd_path.exists():
            raise FileNotFoundError(str(usd_path))

        try:
            morph = gs.morphs.Mesh(file=str(usd_path), fixed=True)
        except ImportError as e:
            raise ImportError(
                "Failed to load USD. Install USD deps (e.g. `pip install -e \".[usd]\"`) and ensure `pxr` is available."
            ) from e

        self.scene.add_entity(morph)  # type: ignore[misc]
        return self.scene

    def load_env_bundle(self, bundle_dir: str | Path, *, env_filename: str = "env.json") -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Load a Kiln env bundle directory (USD geometry + env.json semantics) into this GenesisSim.

        Returns:
        - entities_by_id: mapping from primitive IDs (and 'world' when enabled) to Genesis entities
        - spawn_points: mapping name -> Pose-like dict (pos/quat) from the bundle
        """
        from kiln.envio.bundle import EnvBundleError, PrimitiveSpec, load_env_bundle as _load_env_bundle

        bundle_root = Path(bundle_dir)
        bundle = _load_env_bundle(bundle_root, env_filename=env_filename)

        # Build a fresh scene without default ground; the bundle's world/primitives define geometry.
        self.create_programmatic_scene(with_default_ground=False)
        if self.scene is None:
            raise RuntimeError("Scene is not created.")
        if self._gs is None:
            self.init()
        gs = self._gs

        entities: dict[str, Any] = {}

        # 1) Static world (USD as one fixed entity)
        if bundle.world.enabled:
            usd_path = bundle.resolve_scene_path(bundle_root)
            try:
                morph = gs.morphs.Mesh(
                    file=str(usd_path),
                    pos=bundle.world.pose.pos,
                    quat=bundle.world.pose.quat,
                    fixed=bool(bundle.world.fixed),
                    collision=bool(bundle.world.collision),
                    visualization=bool(bundle.world.visualization),
                    scale=float(bundle.world.scale),
                )
            except ImportError as e:
                raise ImportError(
                    "Failed to load USD. Install USD deps (e.g. `pip install -e \".[usd]\"`) and ensure `pxr` is available."
                ) from e

            entities["world"] = self.scene.add_entity(morph)  # type: ignore[misc]

        # 2) Primitives
        def _spawn_primitive(p: PrimitiveSpec) -> Any:
            fixed = bool(p.fixed) if p.fixed is not None else True
            mass = p.mass
            color = p.color

            if p.shape == "plane":
                normal = p.normal if p.normal is not None else (0.0, 0.0, 1.0)
                return self.add_ground_plane(
                    position=p.pose.pos,
                    normal=normal,
                    fixed=True,  # plane is effectively static in v1
                    collision=p.collision,
                    visualization=p.visualization,
                    color=color,
                )

            if p.shape == "box":
                if p.size is None:
                    raise EnvBundleError(f"Missing size for box: {p.id}")
                # If mass is provided, match it; otherwise fall back to Genesis default material.
                m = 0.0 if fixed else (mass if mass is not None else None)
                return self.add_box(
                    name=p.id,
                    size=p.size,
                    position=p.pose.pos,
                    quat=p.pose.quat,
                    mass=m,
                    collision=p.collision,
                    visualization=p.visualization,
                    color=color,
                )

            if p.shape == "sphere":
                if p.radius is None:
                    raise EnvBundleError(f"Missing radius for sphere: {p.id}")
                m = 0.0 if fixed else (mass if mass is not None else None)
                return self.add_sphere(
                    name=p.id,
                    radius=float(p.radius),
                    position=p.pose.pos,
                    quat=p.pose.quat,
                    mass=m,
                    collision=p.collision,
                    visualization=p.visualization,
                    color=color,
                )

            if p.shape == "cylinder":
                if p.radius is None or p.height is None:
                    raise EnvBundleError(f"Missing radius/height for cylinder: {p.id}")
                m = 0.0 if fixed else (mass if mass is not None else None)
                return self.add_cylinder(
                    name=p.id,
                    radius=float(p.radius),
                    height=float(p.height),
                    position=p.pose.pos,
                    quat=p.pose.quat,
                    mass=m,
                    collision=p.collision,
                    visualization=p.visualization,
                    color=color,
                )

            raise EnvBundleError(f"Unsupported primitive shape: {p.shape!r}")

        for prim in bundle.primitives:
            if prim.id in entities:
                raise EnvBundleError(f"Duplicate entity id in bundle: {prim.id!r}")
            entities[prim.id] = _spawn_primitive(prim)

        # Build once after adding all entities.
        self.build()

        # Return spawn points as raw JSON-like dicts for caller convenience.
        spawn_points = {k: v.to_json() for k, v in bundle.spawn_points.items()}
        return entities, spawn_points

    # ----------------------------
    # Simulation stepping
    # ----------------------------
    def step(self, n: int = 1) -> None:
        if self.scene is None:
            raise RuntimeError("Scene is not created. Call create_programmatic_scene() first.")
        if not self._built:
            self.build()
        for _ in range(n):
            self.scene.step()

    # ----------------------------
    # Entity creation helpers
    # ----------------------------
    def add_ground_plane(
        self,
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
        *,
        normal: tuple[float, float, float] = (0.0, 0.0, 1.0),
        fixed: bool = True,
        collision: bool = True,
        visualization: bool = True,
        color: tuple[float, float, float] | tuple[float, float, float, float] | None = None,
    ) -> Any:
        if self.scene is None:
            raise RuntimeError("Scene is not created.")
        gs = self._gs or _import_genesis()

        # Genesis 0.3.x: scene.add_entity(morph=gs.morphs.Plane(...))
        if hasattr(gs, "morphs") and hasattr(gs.morphs, "Plane"):
            morph = gs.morphs.Plane(
                pos=position,
                normal=normal,
                fixed=bool(fixed),
                collision=bool(collision),
                visualization=bool(visualization),
            )
            surface = None
            if hasattr(gs, "surfaces") and hasattr(gs.surfaces, "Default") and color is not None:
                surface = gs.surfaces.Default(color=_normalize_rgb(color))
            return self.scene.add_entity(morph, surface=surface)  # type: ignore[misc]

        raise RuntimeError("Genesis Plane morph is not available in this version.")

    def add_box(
        self,
        *,
        name: str | None = None,
        size: tuple[float, float, float] = (1.0, 0.5, 0.3),
        position: tuple[float, float, float] = (0.0, 0.0, 0.15),
        quat: tuple[float, float, float, float] | None = None,
        mass: float | None = 1.0,
        collision: bool = True,
        visualization: bool = True,
        color: tuple[float, float, float] | tuple[float, float, float, float] | None = None,
    ) -> Any:
        if self.scene is None:
            raise RuntimeError("Scene is not created.")
        gs = self._gs or _import_genesis()

        # Genesis 0.3.x: scene.add_entity(morph=gs.morphs.Box(pos=..., size=..., fixed=...))
        if hasattr(gs, "morphs") and hasattr(gs.morphs, "Box"):
            fixed = False if mass is None else bool(mass <= 0.0)
            morph_kwargs: dict[str, Any] = {
                "pos": position,
                "size": size,
                "fixed": fixed,
                "collision": bool(collision),
                "visualization": bool(visualization),
            }
            if quat is not None:
                morph_kwargs["quat"] = tuple(float(q) for q in quat)
            morph = gs.morphs.Box(**morph_kwargs)

            material = None
            if (mass is not None) and (mass > 0.0) and (not fixed):
                vol = float(size[0]) * float(size[1]) * float(size[2])
                if vol <= 0.0:
                    raise ValueError(f"Invalid box size/volume: size={size!r}")
                rho = float(mass) / vol
                material = gs.materials.Rigid(rho=rho)
            surface = None
            if hasattr(gs, "surfaces") and hasattr(gs.surfaces, "Default") and color is not None:
                surface = gs.surfaces.Default(color=_normalize_rgb(color))
            # NOTE: Genesis morphs/entities don't currently accept a friendly name in this call
            # signature, so `name` is kept for future USD mapping only.
            _ = name
            return self.scene.add_entity(morph, material=material, surface=surface)  # type: ignore[misc]

        raise RuntimeError("Genesis Box morph is not available in this version.")

    def add_sphere(
        self,
        *,
        name: str | None = None,
        radius: float = 0.5,
        position: tuple[float, float, float] = (0.0, 0.0, 0.5),
        quat: tuple[float, float, float, float] | None = None,
        mass: float | None = 1.0,
        collision: bool = True,
        visualization: bool = True,
        color: tuple[float, float, float] | tuple[float, float, float, float] | None = None,
    ) -> Any:
        if self.scene is None:
            raise RuntimeError("Scene is not created.")
        gs = self._gs or _import_genesis()

        if hasattr(gs, "morphs") and hasattr(gs.morphs, "Sphere"):
            fixed = False if mass is None else bool(mass <= 0.0)
            morph_kwargs: dict[str, Any] = {
                "pos": position,
                "radius": float(radius),
                "fixed": fixed,
                "collision": bool(collision),
                "visualization": bool(visualization),
            }
            if quat is not None:
                morph_kwargs["quat"] = tuple(float(q) for q in quat)
            morph = gs.morphs.Sphere(**morph_kwargs)

            material = None
            if (mass is not None) and (mass > 0.0) and (not fixed):
                vol = (4.0 / 3.0) * math.pi * float(radius) ** 3
                if vol <= 0.0:
                    raise ValueError(f"Invalid sphere radius/volume: radius={radius!r}")
                rho = float(mass) / vol
                material = gs.materials.Rigid(rho=rho)

            surface = None
            if hasattr(gs, "surfaces") and hasattr(gs.surfaces, "Default") and color is not None:
                surface = gs.surfaces.Default(color=_normalize_rgb(color))
            _ = name
            return self.scene.add_entity(morph, material=material, surface=surface)  # type: ignore[misc]

        raise RuntimeError("Genesis Sphere morph is not available in this version.")

    def add_cylinder(
        self,
        *,
        name: str | None = None,
        radius: float = 0.5,
        height: float = 1.0,
        position: tuple[float, float, float] = (0.0, 0.0, 0.5),
        quat: tuple[float, float, float, float] | None = None,
        mass: float | None = 1.0,
        collision: bool = True,
        visualization: bool = True,
        color: tuple[float, float, float] | tuple[float, float, float, float] | None = None,
    ) -> Any:
        if self.scene is None:
            raise RuntimeError("Scene is not created.")
        gs = self._gs or _import_genesis()

        if hasattr(gs, "morphs") and hasattr(gs.morphs, "Cylinder"):
            fixed = False if mass is None else bool(mass <= 0.0)
            morph_kwargs: dict[str, Any] = {
                "pos": position,
                "radius": float(radius),
                "height": float(height),
                "fixed": fixed,
                "collision": bool(collision),
                "visualization": bool(visualization),
            }
            if quat is not None:
                morph_kwargs["quat"] = tuple(float(q) for q in quat)
            morph = gs.morphs.Cylinder(**morph_kwargs)

            material = None
            if (mass is not None) and (mass > 0.0) and (not fixed):
                vol = math.pi * float(radius) ** 2 * float(height)
                if vol <= 0.0:
                    raise ValueError(f"Invalid cylinder radius/height/volume: radius={radius!r} height={height!r}")
                rho = float(mass) / vol
                material = gs.materials.Rigid(rho=rho)

            surface = None
            if hasattr(gs, "surfaces") and hasattr(gs.surfaces, "Default") and color is not None:
                surface = gs.surfaces.Default(color=_normalize_rgb(color))
            _ = name
            return self.scene.add_entity(morph, material=material, surface=surface)  # type: ignore[misc]

        raise RuntimeError("Genesis Cylinder morph is not available in this version.")

    # ----------------------------
    # Query / control helpers
    # ----------------------------
    def get_position(self, entity: Any) -> tuple[float, float, float]:
        def _to_cpu_once(v: Any) -> Any:
            # Avoid per-element CUDA sync when extracting floats from torch tensors.
            try:
                import torch  # type: ignore

                if isinstance(v, torch.Tensor) and getattr(v, "device", None) is not None:
                    if v.device.type != "cpu":
                        return v.detach().to("cpu")
            except Exception:
                pass
            return v

        for attr in ("position", "pos"):
            if hasattr(entity, attr):
                v = _to_cpu_once(getattr(entity, attr))
                try:
                    return (float(v[0]), float(v[1]), float(v[2]))
                except Exception:
                    pass

        for method in ("get_position", "get_pos"):
            if hasattr(entity, method):
                v = _to_cpu_once(getattr(entity, method)())
                return (float(v[0]), float(v[1]), float(v[2]))

        raise AttributeError("Entity has no readable position.")

    def set_position(self, entity: Any, position: tuple[float, float, float]) -> None:
        for method in ("set_position", "set_pos"):
            if hasattr(entity, method):
                getattr(entity, method)(position)
                return
        raise AttributeError("Entity has no set_position method.")

    def set_linear_velocity(self, entity: Any, v_xyz: tuple[float, float, float]) -> None:
        key = id(entity)
        vx, vy, vz = v_xyz
        _, _, _, wx, wy, wz = self._vel6_cache.get(key, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        vel6 = (float(vx), float(vy), float(vz), float(wx), float(wy), float(wz))
        self._set_dofs_velocity6(entity, vel6)
        self._vel6_cache[key] = vel6

    def set_angular_velocity(self, entity: Any, w_xyz: tuple[float, float, float]) -> None:
        key = id(entity)
        wx, wy, wz = w_xyz
        vx, vy, vz, _, _, _ = self._vel6_cache.get(key, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        vel6 = (float(vx), float(vy), float(vz), float(wx), float(wy), float(wz))
        self._set_dofs_velocity6(entity, vel6)
        self._vel6_cache[key] = vel6

    def set_linear_angular_velocity(
        self,
        entity: Any,
        v_xyz: tuple[float, float, float],
        w_xyz: tuple[float, float, float],
    ) -> None:
        """
        Set linear+angular velocity in one call (avoids two `set_dofs_velocity` calls per step).
        """
        key = id(entity)
        vx, vy, vz = v_xyz
        wx, wy, wz = w_xyz
        vel6 = (float(vx), float(vy), float(vz), float(wx), float(wy), float(wz))
        self._set_dofs_velocity6(entity, vel6)
        self._vel6_cache[key] = vel6

    def apply_force(self, entity: Any, f_xyz: tuple[float, float, float]) -> None:
        key = id(entity)
        fx, fy, fz = f_xyz
        _, _, _, tx, ty, tz = self._force6_cache.get(key, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        force6 = (float(fx), float(fy), float(fz), float(tx), float(ty), float(tz))
        self._set_dofs_force6(entity, force6)
        self._force6_cache[key] = force6

    def apply_torque(self, entity: Any, tau_xyz: tuple[float, float, float]) -> None:
        key = id(entity)
        tx, ty, tz = tau_xyz
        fx, fy, fz, _, _, _ = self._force6_cache.get(key, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        force6 = (float(fx), float(fy), float(fz), float(tx), float(ty), float(tz))
        self._set_dofs_force6(entity, force6)
        self._force6_cache[key] = force6

    def _set_dofs_velocity6(self, entity: Any, vel6: tuple[float, float, float, float, float, float]) -> None:
        # NOTE: In Genesis 0.3.x, `control_dofs_velocity()` does not appear to move free rigid
        # bodies (it's intended for articulated/actuated control). For kinematic-ish control
        # of rigid entities, we prefer `set_dofs_velocity()` to directly set base DoF velocity.
        if hasattr(entity, "set_dofs_velocity"):
            entity.set_dofs_velocity(vel6)
            return
        if hasattr(entity, "control_dofs_velocity"):
            entity.control_dofs_velocity(vel6)
            return
        raise AttributeError("Entity has no supported dofs velocity setter.")

    def _set_dofs_force6(self, entity: Any, force6: tuple[float, float, float, float, float, float]) -> None:
        if hasattr(entity, "control_dofs_force"):
            entity.control_dofs_force(force6)
            return
        raise AttributeError("Entity has no supported dofs force control method.")

    # ----------------------------
    # Optional spatial queries
    # ----------------------------
    def raycast(
        self,
        origin: tuple[float, float, float],
        direction: tuple[float, float, float],
        max_distance: float = 5.0,
    ) -> RaycastHit:
        """
        Best-effort raycast wrapper.

        Returns RaycastHit(hit=False) if unsupported.
        """
        if self.scene is None:
            raise RuntimeError("Scene is not created.")

        for method in ("raycast", "cast_ray", "query_raycast"):
            if hasattr(self.scene, method):
                try:
                    res = getattr(self.scene, method)(origin=origin, direction=direction, max_distance=max_distance)
                except TypeError:
                    res = getattr(self.scene, method)(origin, direction, max_distance)

                # Try to normalize a few likely return types.
                if isinstance(res, dict):
                    return RaycastHit(
                        hit=bool(res.get("hit", True)),
                        distance=res.get("distance"),
                        position=res.get("position"),
                        normal=res.get("normal"),
                        collider=res.get("collider"),
                    )
                return RaycastHit(hit=True, collider=res)

        return RaycastHit(hit=False)

    # ----------------------------
    # Diagnostics
    # ----------------------------
    def runtime_info(self, *, sample_contact_entity: Any | None = None) -> dict[str, Any]:
        """
        Best-effort runtime info to help debug CPU vs GPU execution.

        Notes:
        - Genesis has changed APIs across versions; this method intentionally uses permissive
          introspection (attributes may be missing).
        - `sample_contact_entity` can be any entity that supports `get_contacts()`. If available,
          we also report the torch device of contact tensors.
        """
        info: dict[str, Any] = {}

        gs = self._gs
        if gs is None:
            try:
                gs = _import_genesis()
                self._gs = gs
            except Exception as e:
                info["genesis_import_error"] = repr(e)
                return info

        # Genesis version
        info["genesis_version"] = (
            getattr(gs, "__version__", None)
            or getattr(gs, "version", None)
            or getattr(getattr(gs, "VERSION", None), "__str__", lambda: None)()
        )

        # Best-effort backend / device hints (names vary across releases).
        for attr in ("backend", "device", "platform", "compute_backend", "renderer"):
            v = getattr(gs, attr, None)
            if v is not None:
                info[f"genesis_{attr}"] = str(v)

        if self.scene is not None:
            for attr in ("backend", "device"):
                v = getattr(self.scene, attr, None)
                if v is not None:
                    info[f"scene_{attr}"] = str(v)

        # Torch + CUDA info (Genesis depends on torch; still keep permissive).
        try:
            import torch  # type: ignore

            info["torch_version"] = getattr(torch, "__version__", None)
            info["torch_cuda_available"] = bool(torch.cuda.is_available())
            info["torch_cuda_version"] = getattr(getattr(torch, "version", None), "cuda", None)
            if torch.cuda.is_available():
                idx = int(torch.cuda.current_device())
                info["torch_cuda_device"] = idx
                info["torch_cuda_name"] = str(torch.cuda.get_device_name(idx))
        except Exception as e:
            info["torch_error"] = repr(e)

        # If available, report where contact tensors live (cpu vs cuda).
        if sample_contact_entity is not None and hasattr(sample_contact_entity, "get_contacts"):
            try:
                contacts = sample_contact_entity.get_contacts()
                if isinstance(contacts, dict):
                    ga = contacts.get("geom_a")
                    if ga is not None and hasattr(ga, "device"):
                        info["contacts_device"] = str(ga.device)
            except Exception as e:
                info["contacts_device_error"] = repr(e)

        return info



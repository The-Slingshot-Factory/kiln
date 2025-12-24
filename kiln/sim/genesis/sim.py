from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _import_genesis():
    try:
        import genesis as gs  # type: ignore
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "Genesis is not installed. Install it with: python -m pip install -e \".[sim]\" "
            "(and install PyTorch separately per Genesis docs)."
        ) from e
    return gs


@dataclass(frozen=True)
class GenesisSimConfig:
    dt: float = 1.0 / 60.0
    substeps: int = 1
    headless: bool = True
    seed: int | None = None


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
        gs = _import_genesis()
        self._gs = gs

        # Genesis typically requires an explicit init(). Keep this best-effort and permissive
        # across versions by trying a few common call signatures.
        if hasattr(gs, "init"):
            try:
                if self.config.seed is not None:
                    gs.init(seed=self.config.seed)
                else:
                    gs.init()
            except TypeError:
                # Older/newer signatures: fall back to bare init.
                gs.init()

    def close(self) -> None:
        # Genesis doesn't always expose an explicit shutdown; keep as a no-op.
        self.scene = None
        self._built = False
        self._vel6_cache.clear()
        self._force6_cache.clear()

    def create_programmatic_scene(self) -> Any:
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

        # Add a ground plane if available.
        try:
            self.add_ground_plane()
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
        Placeholder for the upcoming Kiln flow:
        - UI authors `.usda/.usd`
        - Kiln exports a Gymnasium env backed by Genesis

        TODO(usd): Implement USD -> Genesis translation (prims -> entities, colliders, materials).
        TODO(usd): Define a stable mapping scheme (USD prim paths -> actor/entity IDs).
        """
        raise NotImplementedError(
            "USD-driven Genesis scenes are not implemented yet. "
            "Use create_programmatic_scene() for now."
        )

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
    def add_ground_plane(self, position: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Any:
        if self.scene is None:
            raise RuntimeError("Scene is not created.")
        gs = self._gs or _import_genesis()

        # Genesis 0.3.x: scene.add_entity(morph=gs.morphs.Plane(...))
        if hasattr(gs, "morphs") and hasattr(gs.morphs, "Plane"):
            morph = gs.morphs.Plane(pos=position)
            return self.scene.add_entity(morph)  # type: ignore[misc]

        raise RuntimeError("Genesis Plane morph is not available in this version.")

    def add_box(
        self,
        *,
        name: str | None = None,
        size: tuple[float, float, float] = (1.0, 0.5, 0.3),
        position: tuple[float, float, float] = (0.0, 0.0, 0.15),
        mass: float = 1.0,
    ) -> Any:
        if self.scene is None:
            raise RuntimeError("Scene is not created.")
        gs = self._gs or _import_genesis()

        # Genesis 0.3.x: scene.add_entity(morph=gs.morphs.Box(pos=..., size=..., fixed=...))
        if hasattr(gs, "morphs") and hasattr(gs.morphs, "Box"):
            fixed = bool(mass <= 0.0)
            morph = gs.morphs.Box(pos=position, size=size, fixed=fixed)
            # NOTE: Genesis morphs/entities don't currently accept a friendly name in this call
            # signature, so `name` is kept for future USD mapping only.
            _ = name
            return self.scene.add_entity(morph)  # type: ignore[misc]

        raise RuntimeError("Genesis Box morph is not available in this version.")

    # ----------------------------
    # Query / control helpers
    # ----------------------------
    def get_position(self, entity: Any) -> tuple[float, float, float]:
        for attr in ("position", "pos"):
            if hasattr(entity, attr):
                v = getattr(entity, attr)
                try:
                    return (float(v[0]), float(v[1]), float(v[2]))
                except Exception:
                    pass

        for method in ("get_position", "get_pos"):
            if hasattr(entity, method):
                v = getattr(entity, method)()
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
        # Prefer velocity control (acts more like an actuator); fall back to directly setting.
        if hasattr(entity, "control_dofs_velocity"):
            entity.control_dofs_velocity(vel6)
            return
        if hasattr(entity, "set_dofs_velocity"):
            entity.set_dofs_velocity(vel6)
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



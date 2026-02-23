from __future__ import annotations

"""
High-level Scene object.

A Scene owns:
- the USD stage (open / save / close)
- the list of BaseObject instances currently in the scene
- the selected object
- object add / remove helpers
- env-bundle export

The UI widgets (ViewportWidget, SceneHierarchyWidget, PropertiesWidget) observe
the scene via Qt signals and never mutate the object list directly.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from kiln.objects import BaseObject, Plane, Cube

if TYPE_CHECKING:
    from PyQt6.QtGui import QVector3D

try:
    from pxr import Usd, UsdGeom, Gf
except ImportError:
    Usd = None
    UsdGeom = None
    Gf = None


class Scene(QObject):
    """Central model for a single 3-D scene backed by a USD stage."""

    # Emitted whenever the objects list changes (add / remove / reload).
    objects_changed = pyqtSignal()

    # Emitted when the selected object changes.  Carries the object (or None).
    selection_changed = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self.scene_path: Path | None = None
        self.stage: Usd.Stage | None = None  # type: ignore[name-defined]
        self.objects: list[BaseObject] = []
        self.selected_object: BaseObject | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self, path: str | Path | None) -> None:
        """Open a USD file (or clear the scene when *path* is ``None``)."""
        self.close()

        if path is None:
            return

        self.scene_path = Path(path)

        if Usd and str(path).endswith((".usd", ".usda", ".usdc")):
            try:
                self.stage = Usd.Stage.Open(str(path))
                self._refresh_from_stage()
            except Exception as e:
                print(f"Failed to open USD stage: {e}")
                self.stage = None

        self.objects_changed.emit()

    def save(self) -> None:
        """Persist the current stage to disk."""
        if self.stage is None:
            return
        try:
            self.stage.GetRootLayer().Save()
        except Exception as e:
            print(f"Failed to save USD stage: {e}")

    def close(self) -> None:
        """Close the scene and clear all state."""
        self.scene_path = None
        self.stage = None
        self.objects.clear()
        self.selected_object = None

    @property
    def is_loaded(self) -> bool:
        return self.scene_path is not None

    # ------------------------------------------------------------------
    # Object management
    # ------------------------------------------------------------------

    def add_object(self, obj: BaseObject, position: "QVector3D | None" = None) -> None:
        """Add *obj* to the scene, optionally setting its position.

        The object is synced to USD (if a stage is open) and automatically
        selected.
        """
        if position is not None:
            obj.position = position

        self.objects.append(obj)

        if self.stage:
            obj.sync_usd(self.stage)
            self.save()

        self.objects_changed.emit()
        self.select(obj)

    def remove_object(self, obj: BaseObject) -> None:
        """Remove *obj* from the scene."""
        if obj not in self.objects:
            return

        self.objects.remove(obj)

        # Remove from USD stage
        if self.stage and obj.prim_path:
            self.stage.RemovePrim(obj.prim_path)
            self.save()

        if self.selected_object is obj:
            self.select(None)

        self.objects_changed.emit()

    def select(self, obj: BaseObject | None) -> None:
        """Select *obj* (or deselect when ``None``)."""
        self.selected_object = obj
        self.selection_changed.emit(obj)

    # ------------------------------------------------------------------
    # Convenience factories
    # ------------------------------------------------------------------

    def add_plane(self, position: "QVector3D | None" = None) -> Plane:
        plane = Plane("Plane")
        self.add_object(plane, position)
        return plane

    def add_cube(self, position: "QVector3D | None" = None) -> Cube:
        cube = Cube("Cube")
        self.add_object(cube, position)
        return cube

    # ------------------------------------------------------------------
    # USD sync helpers
    # ------------------------------------------------------------------

    def sync_selected_to_usd(self) -> None:
        """Sync the currently selected object's transform back to USD and
        save the stage."""
        if self.selected_object and self.stage:
            self.selected_object.sync_usd(self.stage)
            self.save()

    def _refresh_from_stage(self) -> None:
        """Rebuild ``self.objects`` from the current USD stage."""
        self.objects.clear()
        if not self.stage:
            return

        root = self.stage.GetPrimAtPath("/World")
        if not root:
            root = self.stage.GetPseudoRoot()

        for prim in root.GetChildren():
            if not prim.IsValid():
                continue

            type_attr = prim.GetAttribute("kiln:object_type")
            obj_type = None
            if type_attr and type_attr.IsValid():
                obj_type = type_attr.Get()

            if obj_type not in ("Plane", "Cube"):
                continue

            name = prim.GetName()
            obj: BaseObject = Plane(name) if obj_type == "Plane" else Cube(name)

            xform = UsdGeom.Xform(prim)
            if xform:
                from PyQt6.QtGui import QVector3D

                trans_op = rot_op = scale_op = None
                for op in xform.GetOrderedXformOps():
                    op_type = op.GetOpType()
                    if op_type == UsdGeom.XformOp.TypeTranslate:
                        trans_op = op
                    elif op_type == UsdGeom.XformOp.TypeRotateXYZ:
                        rot_op = op
                    elif op_type == UsdGeom.XformOp.TypeScale:
                        scale_op = op

                if trans_op:
                    v = trans_op.Get()
                    obj.position = QVector3D(v[0], v[1], v[2])
                if rot_op:
                    v = rot_op.Get()
                    obj.rotation = QVector3D(v[0], v[1], v[2])
                if scale_op:
                    v = scale_op.Get()
                    obj.scale = QVector3D(v[0], v[1], v[2])

                obj.prim_path = str(prim.GetPath())

            self.objects.append(obj)

        self.objects_changed.emit()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_env_bundle(self, output_dir: str | Path, **kwargs) -> Path:
        """Export the scene as a Kiln MJCF bundle (XML + USD).

        Delegates to :func:`kiln.envio.export.export_scene_mjcf`.
        Raises if no scene is loaded.
        """
        if self.scene_path is None:
            raise RuntimeError("No scene is loaded – cannot export.")

        from kiln.envio.export import export_scene_mjcf

        return export_scene_mjcf(self, output_dir, **kwargs)

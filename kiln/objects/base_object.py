from PyQt6.QtGui import QVector3D, QMatrix4x4, QQuaternion, QColor
from PyQt6.QtOpenGL import QOpenGLShaderProgram
import numpy as np
import math

try:
    from pxr import Usd, UsdGeom, Gf
except ImportError:
    Usd = None
    UsdGeom = None
    Gf = None

print("DEBUG: BaseObject module loaded - VERSION 2 (TRS Fix)")

class BaseObject:
    # Allowed roles. None = no special role.  Extend this list as needed.
    ROLES: list[str | None] = [None, "ground", "building", "car", "npc"]
    
    # Subclasses should override this to restrict which roles they support.
    # By default, objects support no special roles.
    SUPPORTED_ROLES: list[str | None] = [None]

    def __init__(self, name: str, position: QVector3D | None = None, 
                 rotation: QVector3D | None = None, 
                 scale: QVector3D | None = None):
        self.name = name
        self.position = position if position is not None else QVector3D(0, 0, 0)
        self.rotation = rotation if rotation is not None else QVector3D(0, 0, 0) # Euler angles in degrees
        self.scale = scale if scale is not None else QVector3D(1, 1, 1)
        self.visible = True
        self.color = QColor(255, 255, 255) # Default white color
        self.prim_path = None
        self.role: str | None = None
        # Actor config (used when role is "car" or "npc")
        self.control_mode: str = "kinematic"
        self.max_speed: float = 5.0
        self.speed_delta: float = 0.5
        self.turn_rate: float = 1.5
        self.force: float = 30.0
        self.torque: float = 10.0
        self.initial_yaw: float = 0.0
        # NPC-only policy config
        self.roam_xy_min: tuple[float, float] = (-12.0, -12.0)
        self.roam_xy_max: tuple[float, float] = (12.0, 12.0)
        self.goal_tolerance: float = 0.5
        self.cruise_speed: float = 4.0
        self.heading_threshold: float = 0.25
        self.raycast_length: float = 2.0
        self.raycast_angle: float = 0.45
        self.avoid_distance: float = 1.25
        self.brake_distance: float = 0.5
        self.avoid_radius: float = 1.0
        self.emergency_brake_radius: float = 0.6
        self.stuck_steps: int = 30
        self.progress_eps: float = 0.001
        self.nav_cell_size: float = 0.5
        self.nav_inflate: float = 0.55
        self.waypoint_tolerance: float = 0.6
        self.max_goal_samples: int = 50

    def get_transform_matrix(self) -> QMatrix4x4:
        """
        Calculates the transformation matrix for rendering.
        Uses numpy to ensure correct TRS construction.
        """
        # Translation matrix (Row-major)
        T = np.eye(4, dtype=np.float32)
        T[0, 3] = self.position.x()
        T[1, 3] = self.position.y()
        T[2, 3] = self.position.z()
        
        # Rotation matrices (XYZ Euler)
        rx = math.radians(self.rotation.x())
        ry = math.radians(self.rotation.y())
        rz = math.radians(self.rotation.z())
        
        # Rotation around X
        Rx = np.eye(4, dtype=np.float32)
        Rx[1, 1] = math.cos(rx)
        Rx[1, 2] = -math.sin(rx)
        Rx[2, 1] = math.sin(rx)
        Rx[2, 2] = math.cos(rx)
        
        # Rotation around Y
        Ry = np.eye(4, dtype=np.float32)
        Ry[0, 0] = math.cos(ry)
        Ry[0, 2] = math.sin(ry)
        Ry[2, 0] = -math.sin(ry)
        Ry[2, 2] = math.cos(ry)
        
        # Rotation around Z
        Rz = np.eye(4, dtype=np.float32)
        Rz[0, 0] = math.cos(rz)
        Rz[0, 1] = -math.sin(rz)
        Rz[1, 0] = math.sin(rz)
        Rz[1, 1] = math.cos(rz)
        
        # Scale matrix
        S = np.eye(4, dtype=np.float32)
        S[0, 0] = self.scale.x()
        S[1, 1] = self.scale.y()
        S[2, 2] = self.scale.z()
        
        # Standard TRS: T * Rz * Ry * Rx * S
        M = T @ Rz @ Ry @ Rx @ S
        
        # Convert to QMatrix4x4 (expects column-major list)
        return QMatrix4x4(M.T.flatten().tolist())

    def render(self, program: QOpenGLShaderProgram):
        if not self.visible:
            return
        pass

    def sync_usd(self, stage, parent_path: str = "/World") -> bool:
        if Usd is None or stage is None:
            return False

        safe_name = "".join(c for c in self.name if c.isalnum() or c == "_")
        if not safe_name:
            safe_name = f"Object_{id(self)}"
            
        path = f"{parent_path}/{safe_name}"
        self.prim_path = path

        xform = UsdGeom.Xform.Define(stage, path)
        if not xform:
            return False

        translate_op = xform.GetTranslateOp() or xform.AddTranslateOp()
        translate_op.Set(Gf.Vec3d(self.position.x(), self.position.y(), self.position.z()))

        rotate_op = xform.GetRotateXYZOp() or xform.AddRotateXYZOp()
        rotate_op.Set(Gf.Vec3d(self.rotation.x(), self.rotation.y(), self.rotation.z()))

        scale_op = xform.GetScaleOp() or xform.AddScaleOp()
        scale_op.Set(Gf.Vec3d(self.scale.x(), self.scale.y(), self.scale.z()))

        # Sync Metadata
        from pxr import Sdf
        prim = xform.GetPrim()
        
        # Role
        role_attr = prim.CreateAttribute("kiln:role", Sdf.ValueTypeNames.String)
        role_attr.Set(self.role if self.role else "")
        
        # Color
        color_attr = prim.CreateAttribute("kiln:color", Sdf.ValueTypeNames.Float3)
        color_attr.Set(Gf.Vec3f(self.color.redF(), self.color.greenF(), self.color.blueF()))

        # Actor metadata is persisted on the USD prim so UI settings survive reload.
        if self.role in ("car", "npc"):
            prim.CreateAttribute("kiln:control_mode", Sdf.ValueTypeNames.String).Set(self.control_mode)
            prim.CreateAttribute("kiln:max_speed", Sdf.ValueTypeNames.Float).Set(float(self.max_speed))
            prim.CreateAttribute("kiln:speed_delta", Sdf.ValueTypeNames.Float).Set(float(self.speed_delta))
            prim.CreateAttribute("kiln:turn_rate", Sdf.ValueTypeNames.Float).Set(float(self.turn_rate))
            prim.CreateAttribute("kiln:force", Sdf.ValueTypeNames.Float).Set(float(self.force))
            prim.CreateAttribute("kiln:torque", Sdf.ValueTypeNames.Float).Set(float(self.torque))
            prim.CreateAttribute("kiln:initial_yaw", Sdf.ValueTypeNames.Float).Set(float(self.initial_yaw))

        if self.role == "npc":
            prim.CreateAttribute("kiln:roam_xy_min", Sdf.ValueTypeNames.Float2).Set(
                Gf.Vec2f(float(self.roam_xy_min[0]), float(self.roam_xy_min[1]))
            )
            prim.CreateAttribute("kiln:roam_xy_max", Sdf.ValueTypeNames.Float2).Set(
                Gf.Vec2f(float(self.roam_xy_max[0]), float(self.roam_xy_max[1]))
            )
            prim.CreateAttribute("kiln:goal_tolerance", Sdf.ValueTypeNames.Float).Set(float(self.goal_tolerance))
            prim.CreateAttribute("kiln:cruise_speed", Sdf.ValueTypeNames.Float).Set(float(self.cruise_speed))
            prim.CreateAttribute("kiln:heading_threshold", Sdf.ValueTypeNames.Float).Set(float(self.heading_threshold))
            prim.CreateAttribute("kiln:raycast_length", Sdf.ValueTypeNames.Float).Set(float(self.raycast_length))
            prim.CreateAttribute("kiln:raycast_angle", Sdf.ValueTypeNames.Float).Set(float(self.raycast_angle))
            prim.CreateAttribute("kiln:avoid_distance", Sdf.ValueTypeNames.Float).Set(float(self.avoid_distance))
            prim.CreateAttribute("kiln:brake_distance", Sdf.ValueTypeNames.Float).Set(float(self.brake_distance))
            prim.CreateAttribute("kiln:avoid_radius", Sdf.ValueTypeNames.Float).Set(float(self.avoid_radius))
            prim.CreateAttribute("kiln:emergency_brake_radius", Sdf.ValueTypeNames.Float).Set(
                float(self.emergency_brake_radius)
            )
            prim.CreateAttribute("kiln:stuck_steps", Sdf.ValueTypeNames.Int).Set(int(self.stuck_steps))
            prim.CreateAttribute("kiln:progress_eps", Sdf.ValueTypeNames.Float).Set(float(self.progress_eps))
            prim.CreateAttribute("kiln:nav_cell_size", Sdf.ValueTypeNames.Float).Set(float(self.nav_cell_size))
            prim.CreateAttribute("kiln:nav_inflate", Sdf.ValueTypeNames.Float).Set(float(self.nav_inflate))
            prim.CreateAttribute("kiln:waypoint_tolerance", Sdf.ValueTypeNames.Float).Set(float(self.waypoint_tolerance))
            prim.CreateAttribute("kiln:max_goal_samples", Sdf.ValueTypeNames.Int).Set(int(self.max_goal_samples))
        
        return True

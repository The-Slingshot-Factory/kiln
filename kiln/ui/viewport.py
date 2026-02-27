from __future__ import annotations

"""
OpenGL viewport widget.

This is a lightweight viewport used by the UI to preview USD geometry.
It is intentionally simple (no materials/textures), and renders either:
- a fallback splash cube, or
- USD meshes as point clouds (when `pxr` is available).

The ViewportWidget is a **pure renderer**: it does not own the objects list
or the USD stage.  It reads from a :class:`~kiln.scene.Scene` instance.
"""

from typing import TYPE_CHECKING

from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont
from OpenGL.GL import *
import numpy as np
import math
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction

if TYPE_CHECKING:
    from kiln.scene import Scene


class ViewportWidget(QOpenGLWidget):

    def __init__(self, scene: "Scene", parent=None):
        super().__init__(parent)
        self.scene = scene

        # Camera parameters
        self.camera_distance = 10.0
        self.camera_yaw = 45.0
        self.camera_pitch = 30.0
        self.camera_target = np.array([0.0, 0.0, 0.0])

        # Mouse interaction
        self.last_mouse_pos = QPoint()
        self.mouse_button = None

        # OpenGL objects
        self.grid_vao = None
        self.grid_vbo = None
        self.grid_vertex_count = 0

        # Drag and Drop
        self.setAcceptDrops(True)

        self.scene.objects_changed.connect(self.update)
        self.scene.selection_changed.connect(self._on_scene_selection_changed)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # Convenience properties that delegate to the scene
    # ------------------------------------------------------------------

    @property
    def objects(self):
        return self.scene.objects

    @property
    def stage(self):
        return self.scene.stage

    @property
    def selected_object(self):
        return self.scene.selected_object

    @property
    def scene_path(self):
        return self.scene.scene_path

    # ------------------------------------------------------------------
    # Scene signal handlers
    # ------------------------------------------------------------------

    def _on_scene_selection_changed(self, obj):
        """Repaint when the scene's selection changes."""
        self.update()

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-kiln-object"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat("application/x-kiln-object"):
            obj_type = bytes(mime.data("application/x-kiln-object")).decode('utf-8')
            pos = event.position()  # QPointF

            # Perform raycast to find ground position
            world_pos = self.get_raycast_hit_on_ground(pos.x(), pos.y())

            from PyQt6.QtGui import QVector3D
            position = QVector3D(world_pos[0], world_pos[1], world_pos[2])

            if obj_type == "Plane":
                self.scene.add_plane(position=position)
            elif obj_type == "Box":
                self.scene.add_box(position=position)

            event.acceptProposedAction()

    def get_raycast_hit_on_ground(self, screen_x, screen_y):
        w = self.width()
        h = self.height()
        ndc_x = (screen_x / w) * 2.0 - 1.0
        ndc_y = 1.0 - (screen_y / h) * 2.0

        vp = self.get_view_projection_matrix()
        try:
            inv_vp = np.linalg.inv(vp)
        except np.linalg.LinAlgError:
            return np.array([0.0, 0.0, 0.0])

        def unproject(ndc_z):
            vec = np.array([ndc_x, ndc_y, ndc_z, 1.0])
            world = inv_vp @ vec
            if world[3] != 0:
                world /= world[3]
            return world[:3]

        near_point = unproject(-1.0)
        far_point = unproject(1.0)

        ray_dir = far_point - near_point

        if abs(ray_dir[1]) < 1e-6:
            return np.array([near_point[0], 0, near_point[2]])

        t = -near_point[1] / ray_dir[1]

        if t < 0:
            return np.array([near_point[0], 0, near_point[2]])

        hit_point = near_point + t * ray_dir
        return hit_point

    def get_ray_from_mouse(self, screen_x, screen_y):
        """Returns (origin, direction) of a ray starting at the camera."""
        w = self.width()
        h = self.height()
        ndc_x = (screen_x / w) * 2.0 - 1.0
        ndc_y = 1.0 - (screen_y / h) * 2.0

        vp = self.get_view_projection_matrix()
        try:
            inv_vp = np.linalg.inv(vp)
        except np.linalg.LinAlgError:
            return np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])

        def unproject(ndc_z):
            vec = np.array([ndc_x, ndc_y, ndc_z, 1.0])
            world = inv_vp @ vec
            if world[3] != 0:
                world /= world[3]
            return world[:3]

        near_point = unproject(-1.0)
        far_point = unproject(1.0)
        
        ray_dir = far_point - near_point
        ray_dir /= np.linalg.norm(ray_dir)
        
        return near_point, ray_dir

    def intersect_ray_aabb(self, ray_o, ray_d, box_min, box_max):
        """Standard slab-test for Ray-AABB intersection."""
        t1 = (box_min - ray_o) / (ray_d + 1e-10)
        t2 = (box_max - ray_o) / (ray_d + 1e-10)
        
        tmin = np.maximum(np.minimum(t1, t2), -np.inf)
        tmax = np.minimum(np.maximum(t1, t2), np.inf)
        
        real_tmin = np.max(tmin)
        real_tmax = np.min(tmax)
        
        if real_tmax >= real_tmin and real_tmax >= 0:
            return real_tmin if real_tmin > 0 else 0
        return None

    def pick_object(self, screen_x, screen_y):
        """Returns the frontmost object at the given screen coordinates."""
        ray_o, ray_d = self.get_ray_from_mouse(screen_x, screen_y)
        
        closest_obj = None
        min_t = float('inf')
        
        from kiln.objects import Box, Plane
        
        for obj in self.scene.objects:
            # Transform ray to local space
            model_q = obj.get_transform_matrix()
            model = np.array(model_q.copyDataTo(), dtype=np.float32).reshape(4, 4).T
            try:
                inv_model = np.linalg.inv(model)
            except np.linalg.LinAlgError:
                continue
                
            local_o = (inv_model @ np.append(ray_o, 1.0))[:3]
            local_d = (inv_model @ np.append(ray_d, 0.0))[:3]
            
            t = None
            if isinstance(obj, Box):
                hs = obj.size / 2.0
                b_min = np.array([-hs, 0, -hs])
                b_max = np.array([hs, obj.size, hs])
                t = self.intersect_ray_aabb(local_o, local_d, b_min, b_max)
            elif isinstance(obj, Plane):
                # Simple infinite plane intersection in local space (y=0)
                if abs(local_d[1]) > 1e-6:
                    t_val = -local_o[1] / local_d[1]
                    if t_val >= 0:
                        # Check bounds if it's a finite plane (optional, but keep it simple)
                        hit_local = local_o + t_val * local_d
                        if abs(hit_local[0]) <= obj.width/2.0 and abs(hit_local[2]) <= obj.depth/2.0:
                            t = t_val
                            
            if t is not None and t < min_t:
                min_t = t
                closest_obj = obj
                
        return closest_obj

    # ------------------------------------------------------------------
    # Selection (delegates to scene)
    # ------------------------------------------------------------------

    def select_object(self, obj):
        """Select an object via the scene."""
        self.scene.select(obj)

    def load_scene(self, path):
        """Load a scene file (delegates to Scene.load)."""
        self.scene.load(path)

    # ------------------------------------------------------------------
    # OpenGL
    # ------------------------------------------------------------------

    def initializeGL(self):
        glClearColor(0.1, 0.1, 0.1, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glLineWidth(1.5)

        # Shader program
        self.program = QOpenGLShaderProgram()

        self.program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex,
            """
            #version 330 core
            layout (location = 0) in vec3 position;
            layout (location = 1) in vec4 color;
            
            uniform mat4 MVP;
            uniform float zOffset;
            
            out vec4 vertexColor;
            
            void main()
            {
                gl_Position = MVP * vec4(position, 1.0);
                gl_Position.z -= zOffset;
                vertexColor = color;
            }
            """
        )

        self.program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment,
            """
            #version 330 core
            in vec4 vertexColor;
            out vec4 fragColor;
            
            uniform int useUniformColor;
            uniform vec4 overrideColor;
            
            void main()
            {
                if (useUniformColor == 1) {
                    fragColor = overrideColor;
                } else {
                    fragColor = vertexColor;
                }
            }
            """
        )

        if not self.program.link():
            raise RuntimeError(self.program.log())

        self.create_grid()

    def create_grid(self):
        """Create an infinite-looking grid centered at origin"""
        grid_size = 100
        grid_spacing = 1.0

        vertices = []

        for i in range(-grid_size // 2, grid_size // 2 + 1):
            offset = i * grid_spacing

            if i == 0:
                continue
            else:
                distance = abs(i) / (grid_size / 2)
                alpha = max(0.1, 1.0 - distance * 0.7)
                color = [0.3, 0.3, 0.3, alpha]

            vertices.extend([
                -grid_size / 2 * grid_spacing, 0.0, offset, *color,
                grid_size / 2 * grid_spacing, 0.0, offset, *color
            ])

            vertices.extend([
                offset, 0.0, -grid_size / 2 * grid_spacing, *color,
                offset, 0.0, grid_size / 2 * grid_spacing, *color
            ])

        # X-axis (red)
        vertices.extend([
            -grid_size / 2 * grid_spacing, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0,
            grid_size / 2 * grid_spacing, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0
        ])

        # Z-axis (blue)
        vertices.extend([
            0.0, 0.0, -grid_size / 2 * grid_spacing, 0.0, 0.0, 1.0, 1.0,
            0.0, 0.0, grid_size / 2 * grid_spacing, 0.0, 0.0, 1.0, 1.0
        ])

        # Y-axis (green)
        vertices.extend([
            0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0,
            0.0, grid_size / 4 * grid_spacing, 0.0, 0.0, 1.0, 0.0, 1.0
        ])

        vertices = np.array(vertices, dtype=np.float32)
        self.grid_vertex_count = len(vertices) // 7

        self.grid_vao = glGenVertexArrays(1)
        self.grid_vbo = glGenBuffers(1)

        glBindVertexArray(self.grid_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.grid_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 7 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, 7 * 4, ctypes.c_void_p(3 * 4))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

    def get_camera_position(self):
        yaw_rad = math.radians(self.camera_yaw)
        pitch_rad = math.radians(self.camera_pitch)

        x = self.camera_distance * math.cos(pitch_rad) * math.cos(yaw_rad)
        y = self.camera_distance * math.sin(pitch_rad)
        z = self.camera_distance * math.cos(pitch_rad) * math.sin(yaw_rad)

        return np.array([x, y, z]) + self.camera_target

    def get_view_projection_matrix(self):
        camera_pos = self.get_camera_position()
        up = np.array([0.0, 1.0, 0.0])

        z_axis = camera_pos - self.camera_target
        z_axis = z_axis / np.linalg.norm(z_axis)

        x_axis = np.cross(up, z_axis)
        x_axis = x_axis / np.linalg.norm(x_axis)

        y_axis = np.cross(z_axis, x_axis)

        view = np.eye(4, dtype=np.float32)
        view[0, :3] = x_axis
        view[1, :3] = y_axis
        view[2, :3] = z_axis
        view[:3, 3] = -np.array([np.dot(x_axis, camera_pos),
                                  np.dot(y_axis, camera_pos),
                                  np.dot(z_axis, camera_pos)])

        aspect = self.width() / self.height() if self.height() > 0 else 1.0
        fov = math.radians(45.0)
        near = 0.1
        far = 1000.0

        f = 1.0 / math.tan(fov / 2.0)
        projection = np.zeros((4, 4), dtype=np.float32)
        projection[0, 0] = f / aspect
        projection[1, 1] = f
        projection[2, 2] = (far + near) / (near - far)
        projection[2, 3] = (2 * far * near) / (near - far)
        projection[3, 2] = -1.0

        vp = projection @ view
        return vp

    def get_mvp_matrix(self):
        return self.get_view_projection_matrix()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)
        glDisable(GL_CULL_FACE)
        glDisable(GL_BLEND)

        if not self.scene.is_loaded:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QColor(150, 150, 150))
            painter.setFont(QFont("Arial", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No screen selected")
            painter.end()
            return

        if hasattr(self, 'program') and self.program.isLinked():
            self.program.bind()

            mvp_loc = glGetUniformLocation(self.program.programId(), "MVP")
            use_color_loc = glGetUniformLocation(self.program.programId(), "useUniformColor")
            override_color_loc = glGetUniformLocation(self.program.programId(), "overrideColor")
            z_offset_loc = glGetUniformLocation(self.program.programId(), "zOffset")

            vp = self.get_view_projection_matrix()

            # 1. Draw solid objects
            glUniform1i(use_color_loc, 0)
            glUniform1f(z_offset_loc, 0.0)

            for obj in self.scene.objects:
                model_q = obj.get_transform_matrix()
                model_t = np.array(model_q.copyDataTo(), dtype=np.float32).reshape(4, 4)
                model = model_t.T
                mvp = vp @ model

                # Draw Solid
                glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, mvp.T)
                glUniform1i(use_color_loc, 1) # Use uniform color
                r, g, b = obj.color.redF(), obj.color.greenF(), obj.color.blueF()
                glUniform4f(override_color_loc, r, g, b, 1.0)
                glUniform1f(z_offset_loc, 0.0)
                obj.render(self.program)

                # Draw Wireframe Overlay (Black)
                glUniform1f(z_offset_loc, 0.002)
                glUniform1i(use_color_loc, 1)
                glUniform4f(override_color_loc, 0.0, 0.0, 0.0, 1.0)
                obj.draw_outline(self.program)

            # 2. Draw grid
            glUniform1i(use_color_loc, 0)
            glUniform1f(z_offset_loc, 0.0)

            grid_model = np.eye(4, dtype=np.float32)
            grid_model[1, 3] = -0.001
            grid_mvp = vp @ grid_model
            glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, grid_mvp.T)

            if self.grid_vao:
                glBindVertexArray(self.grid_vao)
                glDrawArrays(GL_LINES, 0, self.grid_vertex_count)
                glBindVertexArray(0)

            self.program.release()

        glEnable(GL_BLEND)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    # ------------------------------------------------------------------
    # Mouse controls
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        self.setFocus()
        if not self.scene.is_loaded:
            return

        self.last_mouse_pos = event.position().toPoint()
        self.mouse_button = event.button()
        self.mouse_press_pos = event.pos()

        if event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.pos())

    def mouseMoveEvent(self, event):
        if not self.scene.is_loaded:
            return

        dx = event.pos().x() - self.last_mouse_pos.x()
        dy = event.pos().y() - self.last_mouse_pos.y()

        if self.mouse_button == Qt.MouseButton.LeftButton:
            self.camera_yaw += dx * 0.2
            self.camera_pitch = max(-89, min(89, self.camera_pitch + dy * 0.2))
            self.update()
        elif self.mouse_button == Qt.MouseButton.MiddleButton:
            sensitivity = 0.01 * self.camera_distance
            yaw_rad = math.radians(self.camera_yaw)

            right = np.array([math.cos(yaw_rad), 0, math.sin(yaw_rad)])
            up = np.array([0, 1, 0])

            self.camera_target -= right * dx * sensitivity
            self.camera_target += up * dy * sensitivity
            self.update()

        self.last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if hasattr(self, 'mouse_press_pos'):
            delta = (event.pos() - self.mouse_press_pos).manhattanLength()
            if delta < 5 and event.button() == Qt.MouseButton.LeftButton:
                picked = self.pick_object(event.pos().x(), event.pos().y())
                self.scene.select(picked)

        self.mouse_button = None

    def wheelEvent(self, event):
        if not self.scene.is_loaded:
            return
        delta = event.angleDelta().y()
        self.camera_distance -= delta * 0.005 * (self.camera_distance * 0.1)
        self.camera_distance = max(0.1, min(self.camera_distance, 1000.0))
        self.update()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.scene.selected_object:
                self.scene.remove_object(self.scene.selected_object)
                self.update()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def show_context_menu(self, pos):
        menu = QMenu(self)

        if self.scene.selected_object:
            delete_action = QAction(f"Delete '{self.scene.selected_object.name}'", self)
            delete_action.triggered.connect(lambda: self.scene.remove_object(self.scene.selected_object))
            menu.addAction(delete_action)
            menu.addSeparator()

        add_object_menu = menu.addMenu("Add object")

        add_plane_action = QAction("Plane", self)
        add_plane_action.triggered.connect(lambda: self.scene.add_plane())
        add_object_menu.addAction(add_plane_action)

        add_box_action = QAction("Box", self)
        add_box_action.triggered.connect(lambda: self.scene.add_box())
        add_object_menu.addAction(add_box_action)

        menu.exec(self.mapToGlobal(pos))
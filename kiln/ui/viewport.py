from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont
from OpenGL.GL import *
import numpy as np
import math
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction
from kiln.objects import Plane, Cube

try:
    from pxr import Usd, UsdGeom
except ImportError:
    Usd = None
    UsdGeom = None


class ViewportWidget(QOpenGLWidget):
    objects_changed = pyqtSignal()
    selection_changed = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.scene_path = None
        self.objects = []
        self.stage = None
        self.selected_object = None

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

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-kiln-object"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat("application/x-kiln-object"):
            obj_type = bytes(mime.data("application/x-kiln-object")).decode('utf-8')
            pos = event.position() # QPointF
            
            # Perform raycast to find ground position
            world_pos = self.get_raycast_hit_on_ground(pos.x(), pos.y())
            
            if obj_type == "Plane":
                self.add_plane(position=world_pos)
            elif obj_type == "Cube":
                self.add_cube(position=world_pos)
                
            event.acceptProposedAction()

    def get_raycast_hit_on_ground(self, screen_x, screen_y):
        # Convert screen coords to NDC (-1 to 1)
        # Qt: (0,0) top-left. GL: (-1,-1) bottom-left.
        # Height is self.height(). Width self.width().
        
        # NDC X: (x / w) * 2 - 1
        # NDC Y: 1 - (y / h) * 2  (Flip Y because Qt is Top-Down)
        
        w = self.width()
        h = self.height()
        ndc_x = (screen_x / w) * 2.0 - 1.0
        ndc_y = 1.0 - (screen_y / h) * 2.0
        
        # Unproject points on near and far planes
        vp = self.get_view_projection_matrix() # 4x4 numpy array
        try:
            inv_vp = np.linalg.inv(vp)
        except np.linalg.LinAlgError:
            return np.array([0.0, 0.0, 0.0]) # Degenerate matrix
            
        def unproject(ndc_z):
            # Homogeneous coord
            vec = np.array([ndc_x, ndc_y, ndc_z, 1.0])
            world = inv_vp @ vec
            if world[3] != 0:
                world /= world[3]
            return world[:3]
            
        near_point = unproject(-1.0) # Near plane in GL default NDC is -1
        far_point = unproject(1.0) # Far plane is 1
        
        # Ray direction
        ray_dir = far_point - near_point
        
        # Intersect with Plane Y=0
        # Line: P = Origin + t * Dir
        # We need P.y = 0 => Origin.y + t * Dir.y = 0 => t = -Origin.y / Dir.y
        
        if abs(ray_dir[1]) < 1e-6:
            # Parallel to ground, drag dropped at horizon?
            # Return point at some default distance or on camera target plane
            return np.array([near_point[0], 0, near_point[2]])
            
        t = -near_point[1] / ray_dir[1]
        
        if t < 0:
            # Intersection is behind camera? (Usually shouldn't happen if looking at ground)
            # Just clamp to ground projection
            return np.array([near_point[0], 0, near_point[2]])
            
        hit_point = near_point + t * ray_dir
        return hit_point
    
    def select_object(self, obj):
        """Select an object and notify the properties panel"""
        self.selected_object = obj
        self.selection_changed.emit(obj)
        self.update()

    def initializeGL(self):
        # Basic GL state
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
                // Apply small bias to Z (towards camera) in NDC.
                // Z in NDC is -1 to 1. Camera is at -1 (if standard).
                // Wait, standard GL: -1 near, 1 far? Or -1 near, 1 far.
                // Pulling closer means DECREASING Z value?
                // Standard: Camera looks down -Z. Depth range 0..1.
                // Let's just subtract bias from Z component.
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

        # Create grid
        self.create_grid()

    def create_grid(self):
        """Create an infinite-looking grid centered at origin"""
        grid_size = 100  # Grid extends from -50 to +50
        grid_spacing = 1.0
        
        vertices = []
        
        # Create grid lines
        for i in range(-grid_size // 2, grid_size // 2 + 1):
            offset = i * grid_spacing
            
            # Determine color based on position
            if i == 0:
                # Z-axis (blue) and X-axis (red) at origin
                continue  # We'll add these separately
            else:
                # Regular grid lines (gray, fading with distance)
                distance = abs(i) / (grid_size / 2)
                alpha = max(0.1, 1.0 - distance * 0.7)
                color = [0.3, 0.3, 0.3, alpha]
            
            # Lines parallel to X-axis
            vertices.extend([
                -grid_size / 2 * grid_spacing, 0.0, offset, *color,
                grid_size / 2 * grid_spacing, 0.0, offset, *color
            ])
            
            # Lines parallel to Z-axis
            vertices.extend([
                offset, 0.0, -grid_size / 2 * grid_spacing, *color,
                offset, 0.0, grid_size / 2 * grid_spacing, *color
            ])
        
        # Add X-axis (red)
        vertices.extend([
            -grid_size / 2 * grid_spacing, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0,
            grid_size / 2 * grid_spacing, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0
        ])
        
        # Add Z-axis (blue)
        vertices.extend([
            0.0, 0.0, -grid_size / 2 * grid_spacing, 0.0, 0.0, 1.0, 1.0,
            0.0, 0.0, grid_size / 2 * grid_spacing, 0.0, 0.0, 1.0, 1.0
        ])
        
        # Add Y-axis (green) - pointing up
        vertices.extend([
            0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0,
            0.0, grid_size / 4 * grid_spacing, 0.0, 0.0, 1.0, 0.0, 1.0
        ])
        
        vertices = np.array(vertices, dtype=np.float32)
        self.grid_vertex_count = len(vertices) // 7  # 7 floats per vertex (3 pos + 4 color)
        
        # Create VAO and VBO
        self.grid_vao = glGenVertexArrays(1)
        self.grid_vbo = glGenBuffers(1)
        
        glBindVertexArray(self.grid_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.grid_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        
        # Position attribute
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 7 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        
        # Color attribute
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, 7 * 4, ctypes.c_void_p(3 * 4))
        glEnableVertexAttribArray(1)
        
        glBindVertexArray(0)

    def load_scene(self, path):
        self.scene_path = path if path else None
        self.objects.clear()
        
        if self.scene_path:
            # Try to open the stage if USD is available
            if Usd and str(path).endswith(('.usd', '.usda', '.usdc')):
                try:
                    self.stage = Usd.Stage.Open(str(path))
                    self.refresh_from_stage()
                except Exception as e:
                    print(f"Failed to open USD stage: {e}")
                    self.stage = None
        else:
            self.stage = None
            
        self.objects_changed.emit()
        self.update()

    def refresh_from_stage(self):
        self.objects.clear()
        if not self.stage:
            return

        # Traverse the stage to find objects we can render
        # We look for prims under /World or root that have our custom attribute
        # Or just generic traverse?
        
        # For this prototype, we just look at children of /World if it exists, or root
        root = self.stage.GetPrimAtPath("/World")
        if not root:
            root = self.stage.GetPseudoRoot()
            
        for prim in root.GetChildren():
            if not prim.IsValid():
                continue
                
            # Check for kiln type
            type_attr = prim.GetAttribute("kiln:object_type")
            obj_type = None
            if type_attr and type_attr.IsValid():
                obj_type = type_attr.Get()
            
            if obj_type == "Plane" or obj_type == "Cube":
                # Create object
                name = prim.GetName()
                if obj_type == "Plane":
                    obj = Plane(name)
                else:
                    obj = Cube(name)
                
                # Sync properties from USD to Python Object
                # Position, Rotation, Scale
                xform = UsdGeom.Xform(prim)
                if xform:
                    # Get local transformation
                    # This is complex in USD because of ops order.
                    # We usually want to find the specific ops we created.
                    
                    # Translation
                    trans_op = None
                    rot_op = None
                    scale_op = None
                    
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
                        # PyQt6 QVector3D
                        from PyQt6.QtGui import QVector3D
                        obj.position = QVector3D(v[0], v[1], v[2])
                        
                    if rot_op:
                        v = rot_op.Get()
                        obj.rotation = QVector3D(v[0], v[1], v[2])
                        
                    if scale_op:
                        v = scale_op.Get()
                        obj.scale = QVector3D(v[0], v[1], v[2])
                        
                    # Also set the prim path so it updates the correct one later
                    obj.prim_path = str(prim.GetPath())
                
                self.objects.append(obj)
        
        self.objects_changed.emit()

    def get_camera_position(self):
        """Calculate camera position from spherical coordinates"""
        yaw_rad = math.radians(self.camera_yaw)
        pitch_rad = math.radians(self.camera_pitch)
        
        x = self.camera_distance * math.cos(pitch_rad) * math.cos(yaw_rad)
        y = self.camera_distance * math.sin(pitch_rad)
        z = self.camera_distance * math.cos(pitch_rad) * math.sin(yaw_rad)
        
        return np.array([x, y, z]) + self.camera_target

    def get_view_projection_matrix(self):
        """Calculate View-Projection matrix (without Model)"""

        # View matrix (look at the target from camera position)
        camera_pos = self.get_camera_position()
        up = np.array([0.0, 1.0, 0.0])
        
        # Simple lookAt implementation
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
        
        # Projection matrix (perspective)
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
        
        # Combine matrices
        vp = projection @ view
        return vp

    def get_mvp_matrix(self):
        # Legacy method for grid (identity model)
        return self.get_view_projection_matrix()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Ensure proper GL state for 3D rendering
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)
        glDisable(GL_CULL_FACE) # Ensure double-sided rendering for planes
        glDisable(GL_BLEND) # Start with opaque rendering
        
        if not self.scene_path:
            # Draw "No screen selected" text using QPainter
            # Note: QPainter can change GL state, so we do it only if no scene is loaded.
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QColor(150, 150, 150))
            painter.setFont(QFont("Arial", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No screen selected")
            painter.end()
            return

        # Check if program exists/is linked before using it (safety)
        if hasattr(self, 'program') and self.program.isLinked():
            self.program.bind()
            
            # Get uniform locations
            mvp_loc = glGetUniformLocation(self.program.programId(), "MVP")
            use_color_loc = glGetUniformLocation(self.program.programId(), "useUniformColor")
            override_color_loc = glGetUniformLocation(self.program.programId(), "overrideColor")
            z_offset_loc = glGetUniformLocation(self.program.programId(), "zOffset")
            
            vp = self.get_view_projection_matrix()
            
            # 1. Draw solid objects
            glUniform1i(use_color_loc, 0) # Use vertex colors
            glUniform1f(z_offset_loc, 0.0)
            
            for obj in self.objects:
                model_q = obj.get_transform_matrix()
                model_t = np.array(model_q.copyDataTo(), dtype=np.float32).reshape(4, 4)
                model = model_t.T
                mvp = vp @ model
                
                # Draw Solid
                glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, mvp.T)
                glUniform1i(use_color_loc, 0)
                glUniform1f(z_offset_loc, 0.0)
                obj.render(self.program)
                
                # Draw Wireframe Overlay (Black)
                # Pull lines forward to avoid Z-fighting
                glUniform1f(z_offset_loc, 0.002) 
                glUniform1i(use_color_loc, 1)
                glUniform4f(override_color_loc, 0.0, 0.0, 0.0, 1.0)
                obj.draw_outline(self.program)

            # 2. Draw grid
            # Reset state for grid
            glUniform1i(use_color_loc, 0)
            glUniform1f(z_offset_loc, 0.0)
            
            # Offset grid slightly downwards (Y=-0.001) 
            # This makes it occluded by objects at Y=0 from Top
            # but allows it to occlude them from Bottom.
            grid_model = np.eye(4, dtype=np.float32)
            grid_model[1, 3] = -0.001
            grid_mvp = vp @ grid_model
            glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, grid_mvp.T)
            
            if self.grid_vao:
                glBindVertexArray(self.grid_vao)
                glDrawArrays(GL_LINES, 0, self.grid_vertex_count)
                glBindVertexArray(0)
            
            self.program.release()
            
        # Re-enable blending if needed for UI or other overlays
        glEnable(GL_BLEND)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    # Mouse controls
    def mousePressEvent(self, event):
        if not self.scene_path:
            return
            
        self.last_mouse_pos = event.pos()
        self.mouse_button = event.button()
        self.mouse_press_pos = event.pos()  # Track where mouse was pressed
        
        if event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.pos())

    def mouseMoveEvent(self, event):
        if not self.scene_path:
            return

        dx = event.pos().x() - self.last_mouse_pos.x()
        dy = event.pos().y() - self.last_mouse_pos.y()
        
        if self.mouse_button == Qt.MouseButton.LeftButton:
            # Rotate camera
            self.camera_yaw += dx * 0.2
            self.camera_pitch = max(-89, min(89, self.camera_pitch + dy * 0.2))
            self.update()
        elif self.mouse_button == Qt.MouseButton.MiddleButton:
            # Pan camera
            sensitivity = 0.01 * self.camera_distance
            yaw_rad = math.radians(self.camera_yaw)
            
            right = np.array([math.cos(yaw_rad), 0, math.sin(yaw_rad)])
            up = np.array([0, 1, 0])
            
            self.camera_target -= right * dx * sensitivity
            self.camera_target += up * dy * sensitivity
            self.update()
        
        self.last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event):
        # Detect if this was a click (not a drag)
        if hasattr(self, 'mouse_press_pos'):
            delta = (event.pos() - self.mouse_press_pos).manhattanLength()
            if delta < 5 and event.button() == Qt.MouseButton.LeftButton:
                # This was a click, not a drag
                # For now, select the last object in the list (simple approach)
                # A full implementation would do raycasting to find which object was clicked
                if self.objects:
                    # Simple: select last added object on click
                    # TODO: Implement proper ray-object intersection
                    self.select_object(self.objects[-1])
                else:
                    self.select_object(None)
        
        self.mouse_button = None

    def wheelEvent(self, event):
        if not self.scene_path:
            return

        # Zoom
        delta = event.angleDelta().y()
        self.camera_distance *= 0.9 if delta > 0 else 1.1
        self.camera_distance = max(1.0, min(100.0, self.camera_distance))
        self.update()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        # Add Object submenu
        add_object_menu = menu.addMenu("Add object")
        
        add_plane_action = QAction("Plane", self)
        add_plane_action.triggered.connect(self.add_plane)
        add_object_menu.addAction(add_plane_action)

        add_cube_action = QAction("Cube", self)
        add_cube_action.triggered.connect(self.add_cube)
        add_object_menu.addAction(add_cube_action)
        
        menu.exec(self.mapToGlobal(pos))

    def add_plane(self, position=None):
        # Create a plane
        plane = Plane("Plane")
        if position is not None and not isinstance(position, bool):
             # Convert numpy array to QVector3D
             from PyQt6.QtGui import QVector3D
             # position is likely numpy array [x, 0, z]
             plane.position = QVector3D(position[0], position[1], position[2])
             
        self.objects.append(plane)
        
        # Add to USD stage if available
        if self.stage:
            plane.sync_usd(self.stage)
            # Save the stage?
            try:
                self.stage.GetRootLayer().Save()
            except Exception as e:
                print(f"Failed to save USD stage: {e}")
        
        # Select the newly added object
        self.objects_changed.emit()
        self.select_object(plane)
        self.update()

    def add_cube(self, position=None):
        # Create a cube
        cube = Cube("Cube")
        if position is not None and not isinstance(position, bool):
             from PyQt6.QtGui import QVector3D
             cube.position = QVector3D(position[0], position[1], position[2])
             
        self.objects.append(cube)
        
        # Add to USD stage if available
        if self.stage:
            cube.sync_usd(self.stage)
            # Save the stage?
            try:
                self.stage.GetRootLayer().Save()
            except Exception as e:
                print(f"Failed to save USD stage: {e}")
        
        # Select the newly added object
        self.objects_changed.emit()
        self.select_object(cube)
        self.update()
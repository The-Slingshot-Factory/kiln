from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont
from OpenGL.GL import *
import numpy as np
import math


class ViewportWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.scene_path = None

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
            
            out vec4 vertexColor;
            
            void main()
            {
                gl_Position = MVP * vec4(position, 1.0);
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
            
            void main()
            {
                fragColor = vertexColor;
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
        self.update()

    def get_camera_position(self):
        """Calculate camera position from spherical coordinates"""
        yaw_rad = math.radians(self.camera_yaw)
        pitch_rad = math.radians(self.camera_pitch)
        
        x = self.camera_distance * math.cos(pitch_rad) * math.cos(yaw_rad)
        y = self.camera_distance * math.sin(pitch_rad)
        z = self.camera_distance * math.cos(pitch_rad) * math.sin(yaw_rad)
        
        return np.array([x, y, z]) + self.camera_target

    def get_mvp_matrix(self):
        """Calculate Model-View-Projection matrix"""
        # Model matrix (identity - grid is at origin)
        model = np.eye(4, dtype=np.float32)
        
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
        mvp = projection @ view @ model
        return mvp

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        if not self.scene_path:
            # Draw "No screen selected" text
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
            
            # Set MVP uniform using OpenGL directly
            mvp = self.get_mvp_matrix()
            mvp_location = glGetUniformLocation(self.program.programId(), "MVP")
            glUniformMatrix4fv(mvp_location, 1, GL_FALSE, mvp.T)  # Note: transpose for OpenGL column-major
            
            # Draw grid
            if self.grid_vao:
                glBindVertexArray(self.grid_vao)
                glDrawArrays(GL_LINES, 0, self.grid_vertex_count)
                glBindVertexArray(0)
            
            self.program.release()

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    # Mouse controls
    def mousePressEvent(self, event):
        if not self.scene_path:
            return
            
        self.last_mouse_pos = event.pos()
        self.mouse_button = event.button()

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
        self.mouse_button = None

    def wheelEvent(self, event):
        if not self.scene_path:
            return

        # Zoom
        delta = event.angleDelta().y()
        self.camera_distance *= 0.9 if delta > 0 else 1.1
        self.camera_distance = max(1.0, min(100.0, self.camera_distance))
        self.update()
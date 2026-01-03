from __future__ import annotations

"""
OpenGL viewport widget.

This is a lightweight viewport used by the UI to preview USD geometry.
It is intentionally simple (no materials/textures), and renders either:
- a fallback splash cube, or
- USD meshes as point clouds (when `pxr` is available).
"""

from typing import Any

from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_COLOR_MATERIAL,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_LIGHT0,
    GL_LIGHTING,
    GL_LINES,
    GL_MODELVIEW,
    GL_POINTS,
    GL_POINT_SMOOTH,
    GL_POSITION,
    GL_PROJECTION,
    GL_QUADS,
    glBegin,
    glClear,
    glClearColor,
    glColor3f,
    glDisable,
    glEnable,
    glEnd,
    glLightfv,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPointSize,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glScalef,
    glTranslatef,
    glVertex3f,
    glViewport,
)
from OpenGL.GLU import gluPerspective

try:
    from pxr import Usd, UsdGeom
    HAS_USD = True
except ImportError:
    HAS_USD = False
    Usd = None  # type: ignore[assignment]
    UsdGeom = None  # type: ignore[assignment]

class ViewportWidget(QOpenGLWidget):
    """A basic 3D viewport widget for previewing USD scenes."""

    def __init__(self, parent: Any | None = None):
        super().__init__(parent)
        self.rotation_x = 20
        self.rotation_y = -30
        self.gl_initialized = False
        self.cached_meshes: list[tuple[Any, tuple[float, float, float]]] = []  # (points, rgb)
        self.scene_loaded = False
        self.last_pos = None

    def mousePressEvent(self, event) -> None:
        """Start a drag-rotate gesture."""
        self.last_pos = event.pos()

    def mouseMoveEvent(self, event) -> None:
        """Update rotation while dragging."""
        if self.last_pos is None:
            return
        dx = event.x() - self.last_pos.x()
        dy = event.y() - self.last_pos.y()
        
        self.rotation_x += dy * 0.5
        self.rotation_y += dx * 0.5
        self.last_pos = event.pos()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        """End a drag-rotate gesture."""
        self.last_pos = None

    def initializeGL(self) -> None:
        """Standard OpenGL initialization."""
        try:
            self.gl_initialized = True
            glClearColor(0.1, 0.1, 0.1, 1.0)  # Dark background
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            
            # Light position
            glLightfv(GL_LIGHT0, GL_POSITION, [1.0, 1.0, 1.0, 0.0])
        except Exception as e:
            print(f"OpenGL Initialization failed: {e}")
            self.gl_initialized = False

    def resizeGL(self, w: int, h: int) -> None:
        """Handle widget resize."""
        if not self.gl_initialized:
            return
        if h == 0:
            h = 1
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, w / h, 0.01, 1000.0) # Increased range
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self) -> None:
        """Draw the 3D scene."""
        if not self.gl_initialized:
            return

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # Camera transform
        glTranslatef(0.0, 0.0, -15.0)  
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)

        # Draw infinite floor grid
        self.draw_grid()

        # Only draw the fallback splash cube if no scene is loaded
        if self.scene_loaded:
            if self.cached_meshes:
                self.draw_usd_meshes()
        else:
            self.draw_cube()

        # Draw XYZ Orientation Gizmo (Top Left)
        self.draw_gizmo()

    def draw_grid(self) -> None:
        """Draw a simple floor grid in the XZ plane."""
        glDisable(GL_LIGHTING)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        glColor3f(0.3, 0.3, 0.3)
        
        step = 1.0
        size = 10.0
        
        # Draw grid lines
        i = -size
        while i <= size:
            glVertex3f(i, 0, -size)
            glVertex3f(i, 0, size)
            glVertex3f(-size, 0, i)
            glVertex3f(size, 0, i)
            i += step
            
        glEnd()
        glEnable(GL_LIGHTING)

    def draw_gizmo(self) -> None:
        """Draw an XYZ orientation gizmo in the top-left corner."""
        w = self.width()
        h = self.height()
        size_px = 100
        
        # Setup viewport for top-left (OpenGL coords start bottom-left)
        glViewport(0, h - size_px, size_px, size_px)
        
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(-2, 2, -2, 2, -10, 10)
        
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Apply same rotation as camera to match orientation
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        glLineWidth(3.0)
        glBegin(GL_LINES)
        
        # X Axis (Red)
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(1.5, 0, 0)
        
        # Y Axis (Green)
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 1.5, 0)
        
        # Z Axis (Blue)
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 1.5)
        
        # Draw Labels X, Y, Z
        # X Label at (1.6, 0, 0)
        glColor3f(1, 0, 0)
        # /
        glVertex3f(1.6, -0.1, -0.1)
        glVertex3f(1.6, 0.1, 0.1)
        # \
        glVertex3f(1.6, -0.1, 0.1)
        glVertex3f(1.6, 0.1, -0.1)

        # Y Label at (0, 1.6, 0)
        glColor3f(0, 1, 0)
        # V
        glVertex3f(-0.1, 1.6, 0)
        glVertex3f(0, 1.5, 0)
        glVertex3f(0.1, 1.6, 0)
        glVertex3f(0, 1.5, 0)
        # |
        glVertex3f(0, 1.5, 0)
        glVertex3f(0, 1.4, 0)

        # Z Label at (0, 0, 1.6)
        glColor3f(0, 0, 1)
        # Top bar
        glVertex3f(-0.1, 0.1, 1.6)
        glVertex3f(0.1, 0.1, 1.6)
        # Diagonal
        glVertex3f(0.1, 0.1, 1.6)
        glVertex3f(-0.1, -0.1, 1.6)
        # Bottom bar
        glVertex3f(-0.1, -0.1, 1.6)
        glVertex3f(0.1, -0.1, 1.6)
        
        glEnd()
        glLineWidth(1.0)

    def load_scene(self, path: str) -> None:
        """Load a USD scene from disk and cache mesh points for drawing."""
        if not HAS_USD:
            print("Cannot load USD scene: 'pxr' module missing.")
            return

        print(f"Loading stage: {path}")
        self.scene_loaded = True # Mark as loaded even if empty/failed so we stop showing splash
        try:
            stage = Usd.Stage.Open(str(path))
            if not stage:
                print("Failed to open stage")
                return
            
            self.cached_meshes = []
            
            # DFS Traversal to find all meshes
            for prim in stage.Traverse():
                if prim.IsA(UsdGeom.Mesh):
                    mesh = UsdGeom.Mesh(prim)
                    
                    # Get points (time=default)
                    points_attr = mesh.GetPointsAttr().Get()
                    
                    if points_attr:
                        # Extract color (simple fallback)
                        color = (0.7, 0.7, 0.7) 
                        display_color = mesh.GetDisplayColorAttr().Get()
                        if display_color and len(display_color) > 0:
                            c = display_color[0]
                            color = (c[0], c[1], c[2])

                        self.cached_meshes.append((points_attr, color))
            
            print(f"Loaded {len(self.cached_meshes)} meshes.")
            # Reset rotation to see new object
            self.rotation_x = 0
            self.rotation_y = 0
            self.update()
            
        except Exception as e:
            print(f"Error loading USD stage: {e}")

    def draw_usd_meshes(self) -> None:
        """Draw cached USD meshes as a simple point cloud."""
        # Scale down slightly as USD units can be large (cm vs m)
        glPushMatrix()
        glScalef(0.1, 0.1, 0.1) 
        
        glEnable(GL_POINT_SMOOTH)
        glPointSize(4.0)
        
        glBegin(GL_POINTS)
        for points, color in self.cached_meshes:
            glColor3f(*color)
            for p in points:
                glVertex3f(p[0], p[1], p[2])
        glEnd()
        
        glPopMatrix()

    def update_rotation(self) -> None:
        """Small demo helper: slowly spin the camera and repaint."""
        self.rotation_x += 0.5
        self.rotation_y += 0.5
        self.update()  # Trigger repaint

    def draw_cube(self) -> None:
        """Draw a simple 3D cube."""
        glBegin(GL_QUADS)
        
        # Front face (Yellow)
        glColor3f(1.0, 1.0, 0.0)
        glVertex3f(-1.0, -1.0, 1.0)
        glVertex3f(1.0, -1.0, 1.0)
        glVertex3f(1.0, 1.0, 1.0)
        glVertex3f(-1.0, 1.0, 1.0)
        
        # Back face (Blue)
        glColor3f(0.0, 0.0, 1.0)
        glVertex3f(-1.0, -1.0, -1.0)
        glVertex3f(-1.0, 1.0, -1.0)
        glVertex3f(1.0, 1.0, -1.0)
        glVertex3f(1.0, -1.0, -1.0)
        
        # Top face (Green)
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(-1.0, 1.0, -1.0)
        glVertex3f(-1.0, 1.0, 1.0)
        glVertex3f(1.0, 1.0, 1.0)
        glVertex3f(1.0, 1.0, -1.0)
        
        # Bottom face (Red)
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(-1.0, -1.0, -1.0)
        glVertex3f(1.0, -1.0, -1.0)
        glVertex3f(1.0, -1.0, 1.0)
        glVertex3f(-1.0, -1.0, 1.0)
        
        # Right face (Magenta)
        glColor3f(1.0, 0.0, 1.0)
        glVertex3f(1.0, -1.0, -1.0)
        glVertex3f(1.0, 1.0, -1.0)
        glVertex3f(1.0, 1.0, 1.0)
        glVertex3f(1.0, -1.0, 1.0)
        
        # Left face (Cyan)
        glColor3f(0.0, 1.0, 1.0)
        glVertex3f(-1.0, -1.0, -1.0)
        glVertex3f(-1.0, -1.0, 1.0)
        glVertex3f(-1.0, 1.0, 1.0)
        glVertex3f(-1.0, 1.0, -1.0)
        
        glEnd()

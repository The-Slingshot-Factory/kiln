from .base_object import BaseObject
from PyQt6.QtGui import QVector3D, QColor
from OpenGL.GL import *
import numpy as np
import ctypes

try:
    from pxr import Usd, UsdGeom, Gf, Vt, Sdf
except ImportError:
    Usd = None
    UsdGeom = None
    Gf = None
    Vt = None
    Sdf = None
except ImportError:
    Usd = None
    UsdGeom = None
    Gf = None
    Vt = None

class Plane(BaseObject):
    SUPPORTED_ROLES = [None, "ground"]
    
    def __init__(self, name: str, width: float = 10.0, depth: float = 10.0, 
                 position: QVector3D | None = None, 
                 rotation: QVector3D | None = None, 
                 scale: QVector3D | None = None):
        super().__init__(name, position, rotation, scale)
        self.width = width
        self.depth = depth
        self.color = QColor(200, 200, 200) # Light gray
        
        self.vao = None
        self.vbo = None
        self.vertex_count = 0
        
        # We do NOT initialize GL resources here.
        # They will be initialized lazily on the first render call.
        # This ensures the OpenGL context is current.

    def get_asset_path(self):
        import os
        # Assuming run from source root or installed package
        # Try to find kiln/assets/plane.usda relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # current_dir is .../kiln/objects
        # assets is .../kiln/assets
        asset_path = os.path.join(os.path.dirname(current_dir), "assets", "plane.usda")
        return asset_path

    def _setup_gl_resources(self):
        # Create a simple quad
        # Position (3 floats) + Color (4 floats)

        
        half_w = self.width / 2.0
        half_d = self.depth / 2.0
        
        r, g, b, a = self.color.redF(), self.color.greenF(), self.color.blueF(), 1.0
        
        # 4 vertices for a quad (Triangle Strip or Triangle Fan)
        # Using 2 triangles (6 verts) for simplicity with GL_TRIANGLES if needed, 
        # but GL_TRIANGLE_FAN or STRIP is efficient for a quad.
        # Let's use two triangles explicitly to be safe and standard.
        
        # y is up (0), so plane is on x-z
        p1 = [-half_w, 0.0, -half_d] # Top-Left
        p2 = [-half_w, 0.0,  half_d] # Bottom-Left
        p3 = [ half_w, 0.0,  half_d] # Bottom-Right
        p4 = [ half_w, 0.0, -half_d] # Top-Right
        
        data = [
            *p1, r, g, b, a,
            *p2, r, g, b, a,
            *p4, r, g, b, a,
            *p4, r, g, b, a,
            *p2, r, g, b, a,
            *p3, r, g, b, a
        ]
        
        vertices = np.array(data, dtype=np.float32)
        self.vertex_count = len(vertices) // 7
        
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        # Check if attributes are correct for the viewport shader
        # loc 0: position (vec3)
        # loc 1: color (vec4)
        stride = 7 * 4
        
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * 4))
        
        glBindVertexArray(0)
        
        # Setup Outline Resources
        # 4 corners line loop
        outline_data = [
            *p1, 0,0,0,1,
            *p2, 0,0,0,1,
            *p3, 0,0,0,1,
            *p4, 0,0,0,1
        ]
        outline_vertices = np.array(outline_data, dtype=np.float32)
        
        self.outline_vao = glGenVertexArrays(1)
        self.outline_vbo = glGenBuffers(1)
        
        glBindVertexArray(self.outline_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.outline_vbo)
        glBufferData(GL_ARRAY_BUFFER, outline_vertices.nbytes, outline_vertices, GL_STATIC_DRAW)
        
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        
        # We don't strictly need color attribute if we override uniform, but reusing shader needs it enabled?
        # Shader expects attr 1. We can just point it to same data or disable distinct attr.
        # But `program` has fixed attributes.
        # If we use `useUniformColor`, the shader ignores vertex color value, but the Attribute MUST be enabled/bound if defined in VAO state?
        # Actually in Core Profile, unrelated attributes can be disabled.
        # But let's just enable it to be safe and consistent.
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * 4))

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def render(self, program):
        if not self.visible:
            return
            
        if not self.vao:
            # Lazy initialization when context is guaranteed to be current
            self._setup_gl_resources()
            
        # We assume program is bound and uniforms (MVP) are set by the caller (Viewport)
        
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLES, 0, self.vertex_count)
        glBindVertexArray(0)

    def draw_outline(self, program):
        if not self.visible:
            return
        if not hasattr(self, 'outline_vao') or not self.outline_vao:
            self._setup_gl_resources()
            
        glBindVertexArray(self.outline_vao)
        glDrawArrays(GL_LINE_LOOP, 0, 4)
        glBindVertexArray(0)

    def sync_usd(self, stage, parent_path: str = "/World") -> bool:
        # First sync the Xform (base implementation)
        if not super().sync_usd(stage, parent_path):
            return False
            
        if UsdGeom is None:
            return False

        # Get the prim we just created/updated
        prim = stage.GetPrimAtPath(self.prim_path)
        
        # Add reference to the plane asset
        asset_path = self.get_asset_path()
        refs = prim.GetReferences()
        refs.AddReference(asset_path)
        
        # Tag with kiln type for reloading
        # We use a custom attribute
        attr = prim.CreateAttribute("kiln:object_type", Sdf.ValueTypeNames.String)
        attr.Set("Plane")
        
        return True

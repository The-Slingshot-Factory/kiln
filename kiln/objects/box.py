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

class Box(BaseObject):
    SUPPORTED_ROLES = [None, "building"]

    def __init__(self, name: str, size: float = 1.0, 
                 position: QVector3D | None = None, 
                 rotation: QVector3D | None = None, 
                 scale: QVector3D | None = None):
        super().__init__(name, position, rotation, scale)
        self.size = size
        self.color = QColor(52, 152, 219) # Premium Blue (#3498db)
        
        self.vao = None
        self.vbo = None
        self.vertex_count = 0 

    def get_asset_path(self):
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        asset_path = os.path.join(os.path.dirname(current_dir), "assets", "box.usda")
        return asset_path

    def _setup_gl_resources(self):
        hs = self.size / 2.0
        r, g, b, a = self.color.redF(), self.color.greenF(), self.color.blueF(), 1.0

        # 8 corners
        p = [
            [-hs, 0,        hs], [ hs, 0,        hs], [ hs, self.size,  hs], [-hs, self.size,  hs],
            [-hs, 0,       -hs], [ hs, 0,       -hs], [ hs, self.size, -hs], [-hs, self.size, -hs]
        ]
        
        # 6 faces, 2 triangles each -> 36 vertices
        indices = [
            0, 1, 2, 0, 2, 3, # Front
            5, 4, 7, 5, 7, 6, # Back
            4, 0, 3, 4, 3, 7, # Left
            1, 5, 6, 1, 6, 2, # Right
            3, 2, 6, 3, 6, 7, # Top
            4, 5, 1, 4, 1, 0  # Bottom
        ]
        
        data = []
        for i in indices:
            data.extend(p[i])
            data.extend([r, g, b, a])
            
        vertices = np.array(data, dtype=np.float32)
        self.vertex_count = len(vertices) // 7
        
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        stride = 7 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * 4))
        
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        
        outline_indices = [
            0,1, 1,2, 2,3, 3,0, # Front Face
            4,5, 5,6, 6,7, 7,4, # Back Face
            0,4, 1,5, 2,6, 3,7  # Connecting Edges
        ]
        
        outline_data = []
        for i in outline_indices:
            outline_data.extend(p[i])
            outline_data.extend([0,0,0,1]) # Black color
            
        outline_verts = np.array(outline_data, dtype=np.float32)
        
        self.outline_vao = glGenVertexArrays(1)
        self.outline_vbo = glGenBuffers(1)
        
        glBindVertexArray(self.outline_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.outline_vbo)
        glBufferData(GL_ARRAY_BUFFER, outline_verts.nbytes, outline_verts, GL_STATIC_DRAW)
        
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * 4))
        
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def render(self, program):
        if not self.visible:
            return
        if not self.vao:
            self._setup_gl_resources()
            
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLES, 0, self.vertex_count)
        glBindVertexArray(0)
        
    def draw_outline(self, program):
        if not self.visible:
            return
        if not hasattr(self, 'outline_vao') or not self.outline_vao:
            self._setup_gl_resources()
            
        glBindVertexArray(self.outline_vao)
        glDrawArrays(GL_LINES, 0, 24) # 12 edges * 2 verts
        glBindVertexArray(0)

    def sync_usd(self, stage, parent_path: str = "/World") -> bool:
        if not super().sync_usd(stage, parent_path):
            return False
        if UsdGeom is None:
            return False

        prim = stage.GetPrimAtPath(self.prim_path)
        if not prim:
            return False

        asset_path = self.get_asset_path()
        prim.GetReferences().AddReference(asset_path)
        
        attr = prim.CreateAttribute("kiln:object_type", Sdf.ValueTypeNames.String)
        attr.Set("Box")
        
        return True

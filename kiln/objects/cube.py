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

class Cube(BaseObject):
    def __init__(self, name: str, size: float = 1.0, 
                 position=QVector3D(0, 0, 0), rotation=QVector3D(0, 0, 0), scale=QVector3D(1, 1, 1)):
        super().__init__(name, position, rotation, scale)
        self.size = size
        self.color = QColor(52, 152, 219) # Premium Blue (#3498db)
        
        self.vao = None
        self.vbo = None
        self.vertex_count = 0 

    def get_asset_path(self):
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        asset_path = os.path.join(os.path.dirname(current_dir), "assets", "cube.usda")
        return asset_path

    def _setup_gl_resources(self):
        hs = self.size / 2.0
        r, g, b, a = self.color.redF(), self.color.greenF(), self.color.blueF(), 1.0

        # 8 corners
        # 0: -x, -y, +z (BLF)
        # 1: +x, -y, +z (BRF)
        # 2: +x, +y, +z (TRF)
        # 3: -x, +y, +z (TLF)
        # 4: -x, -y, -z (BLB)
        # 5: +x, -y, -z (BRB)
        # 6: +x, +y, -z (TRB)
        # 7: -x, +y, -z (TLB)
        
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
        
        # Outline (12 edges)
        # 0: BLF, 1: BRF, 2: TRF, 3: TLF (Front face? No see p definition)
        # p from previous setup:
        # 0:BLF, 1:BRF, 2:TRF, 3:TLF? No wait.
        # p has 8 points.
        # [0,1,2,3] are Base (Y=0). [4,5,6,7] are Top (Y=size).
        
        # Edges:
        # Base Loop: 0-1, 1-2, 3-2, 0-3 ?
        # Top Loop: 4-5, 5-6, 7-6, 4-7 ?
        # Verticals: 0-4, 1-5, 2-6, 3-7 ?
        
        # Let's verify p indices again.
        # p[0](-,-,+), p[1](+,-,+), p[2](+,+,+), p[3](-,+,+) ??
        # In current code:
        # p = [ [-hs, 0, hs], [hs, 0, hs], [hs, size, hs], [-hs, size, hs], ... ]
        # 0: (-hs, 0, hs) BLF
        # 1: (hs, 0, hs) BRF
        # 2: (hs, size, hs) TRF
        # 3: (-hs, size, hs) TLF
        # So 0,1,2,3 is the FRONT FACE.
        # 4,5,6,7 is the BACK FACE.
        
        # Edges layout:
        # Front Loop: 0-1, 1-2, 2-3, 3-0
        # Back Loop: 4-5, 5-6, 6-7, 7-4
        # Connecting: 0-4 (BLF-BLB), 1-5 (BRF-BRB), 2-6 (TRF-TRB), 3-7 (TLF-TLB).
        
        # Wait, indices check:
        # 0: (-hs, 0, hs) BLF
        # 4: (-hs, 0, -hs) BLB
        # So 0-4 is valid edge.
        
        outline_indices = [
            0,1, 1,2, 2,3, 3,0, # Front Face
            4,5, 5,6, 6,7, 7,4, # Back Face
            0,4, 1,5, 2,6, 3,7  # Connecting Edges
        ]
        
        outline_data = []
        for i in outline_indices:
            outline_data.extend(p[i])
            outline_data.extend([0,0,0,1]) # Black color (placeholder)
            
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
        attr.Set("Cube")
        
        return True

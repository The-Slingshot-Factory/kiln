from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
                             QLabel, QAbstractItemView)
from PyQt6.QtCore import Qt, QMimeData, QSize
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor

class LibraryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("Asset Library")
        title.setStyleSheet("font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(32, 32))
        self.list_widget.setDragEnabled(True)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        
        # Add basic items
        self.add_item("Plane", "application/x-kiln-object:Plane")
        self.add_item("Cube", "application/x-kiln-object:Cube")
        
        layout.addWidget(self.list_widget)

    def add_item(self, name, mime_type):
        item = QListWidgetItem(name)
        # Store mime type in custom data role if needed, but QListWidget handles mime types strictly via mimeData method override usually.
        # Or we can just use the item text if unique.
        item.setData(Qt.ItemDataRole.UserRole, mime_type)
        self.list_widget.addItem(item)

    # We need to subclass QListWidget to customize mimeData if we want specific mime types easily,
    # OR we rely on default behaviour which sends qabstractitemmodel/datalist.
    # But for a simple app, drag logic is often custom.
    # Let's subclass QListWidget to be cleaner or just hook into startDrag.
    
    # Actually, default QListWidget supports internal move. For external drag, we want custom mime.
    
# Let's override the list widget
class DraggableListWidget(QListWidget):
    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return
            
        mime_data = QMimeData()
        obj_type = item.text() # "Plane" or "Cube"
        mime_data.setText(obj_type)
        mime_data.setData("application/x-kiln-object", obj_type.encode('utf-8'))
        
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # Create a simple pixmap for visual feedback
        pixmap = QPixmap(100, 30)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, obj_type)
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())
        
        drag.exec(Qt.DropAction.CopyAction)

# Update LibraryWidget to use custom list
class LibraryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        title = QLabel("Asset Library")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: white;")
        layout.addWidget(title)
        
        self.list_widget = DraggableListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #3A3A3A;
            }
        """)
        
        layout.addWidget(self.list_widget)
        
        self.add_item("Plane", "Plane")
        self.add_item("Cube", "Cube")

    def add_item(self, name, type_id):
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, type_id)
        self.list_widget.addItem(item)

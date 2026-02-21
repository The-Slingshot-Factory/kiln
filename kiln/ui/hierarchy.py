from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

class SceneHierarchyWidget(QWidget):
    # Signal emitted when an object is selected in the hierarchy
    object_selected = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title = QLabel("Hierarchy")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(15)
        layout.addWidget(self.tree)
        
        # Connect selection
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        
        self.objects_map = {} # Map item to object
        self.current_objects = []
        self._block_signals = False

    def set_objects(self, objects):
        """Update the hierarchy with the list of objects"""
        self._block_signals = True
        self.current_objects = objects
        self.tree.clear()
        self.objects_map = {}
        
        for obj in objects:
            item = QTreeWidgetItem([obj.name])
            item.setData(0, Qt.ItemDataRole.UserRole, obj)
            self.tree.addTopLevelItem(item)
            self.objects_map[id(obj)] = item
        self._block_signals = False
            
    def select_object(self, obj):
        """Programmatically select an object in the hierarchy"""
        if self._block_signals:
            return
            
        self._block_signals = True
        if obj is None:
            self.tree.clearSelection()
        else:
            item = self.objects_map.get(id(obj))
            if item:
                self.tree.setCurrentItem(item)
        self._block_signals = False

    def _on_selection_changed(self):
        if self._block_signals:
            return
            
        items = self.tree.selectedItems()
        if items:
            obj = items[0].data(0, Qt.ItemDataRole.UserRole)
            self.object_selected.emit(obj)
        else:
            self.object_selected.emit(None)

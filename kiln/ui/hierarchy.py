from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel, QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal, QPoint

class SceneHierarchyWidget(QWidget):
    # Signal emitted when an object is selected in the hierarchy
    object_selected = pyqtSignal(object)
    # Signal emitted when an object is requested to be deleted
    object_deleted = pyqtSignal(object)
    
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
        
        # Context menu
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        
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

    def _show_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if not item:
            return

        obj = item.data(0, Qt.ItemDataRole.UserRole)
        if not obj:
            return

        menu = QMenu(self)
        delete_action = QAction(f"Delete '{obj.name}'", self)
        
        # We need a reference to the scene to delete, but HierarchyWidget 
        # doesn't usually own it. However, in this app, we can either:
        # 1. Emit a signal 'object_deleted' and let the parent handle it.
        # 2. Give the hierarchy a reference to the scene.
        #
        # Looking at project_screen.py might help see how it's used.
        # For now, let's look at the current signals. It only has object_selected.
        # Let's add object_deleted.
        
        delete_action.triggered.connect(lambda: self.object_deleted.emit(obj))
        menu.addAction(delete_action)
        menu.exec(self.tree.mapToGlobal(pos))

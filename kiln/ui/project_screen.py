from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QSplitter, 
                             QTreeView, QLabel, QFrame, QMenu, QMessageBox)
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import Qt, QDir
from pathlib import Path

from .viewport import ViewportWidget
from .properties import PropertiesWidget
from .hierarchy import SceneHierarchyWidget

class ProjectScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.project_path = None
        self._init_ui()

    def set_project(self, path):
        self.project_path = Path(path)
        self.model.setRootPath(str(self.project_path))
        self.tree.setRootIndex(self.model.index(str(self.project_path)))

    def _init_ui(self):
        # Set layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter is the only child of main_layout
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        main_layout.addWidget(self.splitter)

        # Left Panel: Project Browser
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Files)
        self.model.setReadOnly(False) # Enable file operations
        
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setFrameShape(QFrame.Shape.NoFrame)
        # Hide extra columns
        for i in range(1, self.model.columnCount()):
            self.tree.hideColumn(i)
        self.tree.setHeaderHidden(True)
        
        # Context Menu for Deletion
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        # Selection Handling for Preview
        self.tree.selectionModel().selectionChanged.connect(self._on_selection_changed)
        
        self.splitter.addWidget(self.tree)

        # Center Panel: Viewport
        self.viewport = ViewportWidget()
        self.splitter.addWidget(self.viewport)
        
        # Right Panel: Workspace (Hierarchy + Properties)
        self.right_panel = QSplitter(Qt.Orientation.Vertical)
        self.right_panel.setHandleWidth(1)
        
        self.hierarchy = SceneHierarchyWidget()
        self.right_panel.addWidget(self.hierarchy)
        
        self.properties = PropertiesWidget()
        self.right_panel.addWidget(self.properties)
        
        self.splitter.addWidget(self.right_panel)
        
        # Connect signals
        # 1. Viewport -> Hierarchy (Sync list)
        self.viewport.objects_changed.connect(lambda: self.hierarchy.set_objects(self.viewport.objects))
        
        # 2. Viewport -> Workspace (Sync selection)
        self.viewport.selection_changed.connect(self.hierarchy.select_object)
        self.viewport.selection_changed.connect(self.properties.set_object)
        
        # 3. Hierarchy -> Viewport (Input selection)
        self.hierarchy.object_selected.connect(self.viewport.select_object)
        
        # 4. Properties -> USD/Viewport (Input changes)
        self.properties.property_changed.connect(self._on_property_changed)
        
        # Set initial sizes
        self.splitter.setSizes([200, 600, 250])
        self.right_panel.setSizes([300, 400])
        
    def _on_property_changed(self, property_name, value):
        """Handle property changes from the properties panel"""
        # Trigger viewport update and USD sync
        if self.viewport.selected_object and self.viewport.stage:
            self.viewport.selected_object.sync_usd(self.viewport.stage)
            try:
                self.viewport.stage.GetRootLayer().Save()
            except Exception as e:
                print(f"Failed to save USD stage: {e}")
        # Trigger viewport redraw
        self.viewport.update()

    def _on_context_menu(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid(): return

        menu = QMenu()
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.tree.viewport().mapToGlobal(position))

        if action == delete_action:
            self._delete_file(index)

    def _delete_file(self, index):
        path = self.model.filePath(index)
        msg = QMessageBox()
        msg.setWindowTitle("Delete File")
        msg.setText(f"Are you sure you want to delete '{Path(path).name}'?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            if self.model.isDir(index):
                self.model.rmdir(index)
            else:
                self.model.remove(index)

    def _on_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            # Only look at the first column (col 0) which is the name
            index = indexes[0] 
            path = self.model.filePath(index)
            if path.endswith(".usda") or path.endswith(".usd"):
                if hasattr(self.viewport, 'load_scene'):
                    self.viewport.load_scene(path)
            else:
                if hasattr(self.viewport, 'load_scene'):
                    self.viewport.load_scene(None)

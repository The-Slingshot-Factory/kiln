from __future__ import annotations

"""Project workspace screen (file browser + viewport)."""

from typing import Any

from PyQt6.QtWidgets import QFileDialog, QFrame, QMenu, QMessageBox, QSplitter, QTreeView, QVBoxLayout, QWidget
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import QDir, Qt
from pathlib import Path

from kiln.scene import Scene
from .viewport import ViewportWidget
from .properties import PropertiesWidget
from .hierarchy import SceneHierarchyWidget

class ProjectScreen(QWidget):
    """Main project workspace: tree view (left) and viewport (right)."""

    def __init__(self) -> None:
        super().__init__()
        self.project_path: Path | None = None

        # The central Scene model
        self.scene = Scene()

        self._init_ui()

    def set_project(self, path: str | Path) -> None:
        """Set the current project directory (root of the project browser)."""
        self.project_path = Path(path)
        self.model.setRootPath(str(self.project_path))
        self.tree.setRootIndex(self.model.index(str(self.project_path)))

    def _init_ui(self) -> None:
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

        # Center Panel: Viewport (receives scene reference)
        self.viewport = ViewportWidget(self.scene)
        self.splitter.addWidget(self.viewport)
        
        # Right Panel: Workspace (Hierarchy + Properties)
        self.right_panel = QSplitter(Qt.Orientation.Vertical)
        self.right_panel.setHandleWidth(1)
        
        self.hierarchy = SceneHierarchyWidget()
        self.right_panel.addWidget(self.hierarchy)
        
        self.properties = PropertiesWidget()
        self.right_panel.addWidget(self.properties)
        
        self.splitter.addWidget(self.right_panel)
        
        # Connect signals — everything flows through the Scene
        # 1. Scene -> Hierarchy (Sync list)
        self.scene.objects_changed.connect(lambda: self.hierarchy.set_objects(self.scene.objects))
        
        # 2. Scene -> Hierarchy + Properties (Sync selection)
        self.scene.selection_changed.connect(self.hierarchy.select_object)
        self.scene.selection_changed.connect(self.properties.set_object)
        
        # 3. Hierarchy -> Scene (Input selection)
        self.hierarchy.object_selected.connect(self.scene.select)
        
        # 4. Properties -> Scene (Input changes)
        self.properties.property_changed.connect(self._on_property_changed)
        
        # Set initial sizes
        self.splitter.setSizes([200, 600, 250])
        self.right_panel.setSizes([300, 400])
        
    def _on_property_changed(self, property_name, value):
        """Handle property changes from the properties panel"""
        self.scene.sync_selected_to_usd()
        # Trigger viewport redraw
        self.viewport.update()

    def _on_context_menu(self, position) -> None:
        index = self.tree.indexAt(position)
        if not index.isValid():
            return

        menu = QMenu()
        export_action = None
        path = self.model.filePath(index)
        if (not self.model.isDir(index)) and path.lower().endswith((".usd", ".usda", ".usdc", ".usdz")):
            export_action = menu.addAction("Export Kiln Env Bundle…")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.tree.viewport().mapToGlobal(position))

        if export_action is not None and action == export_action:
            self._export_env_bundle()
            return

        if action == delete_action:
            self._delete_file(index)

    def _export_env_bundle(self) -> None:
        """Prompt the user for an output folder and export the scene as MJCF + USD."""
        if not self.scene.is_loaded:
            QMessageBox.warning(self, "Export", "No scene is loaded. Select a USD file first.")
            return

        # Start the dialog in the scene's parent directory
        start_dir = str(self.scene.scene_path.parent)

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose export directory",
            start_dir,
        )
        if not output_dir:
            return  # user cancelled

        try:
            xml_path = self.scene.export_env_bundle(output_dir)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", f"{e}")
            return

        QMessageBox.information(
            self,
            "Export complete",
            f"Kiln bundle exported to:\n{output_dir}\n\nFiles:\n- scene.xml\n- scene{self.scene.scene_path.suffix.lower()}",
        )

    def _delete_file(self, index) -> None:
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

    def _on_selection_changed(self, selected: Any, deselected: Any) -> None:
        indexes = selected.indexes()
        if indexes:
            index = indexes[0] 
            path = self.model.filePath(index)
            if path.endswith(".usda") or path.endswith(".usd"):
                self.scene.load(path)
            else:
                self.scene.load(None)

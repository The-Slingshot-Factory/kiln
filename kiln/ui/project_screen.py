from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QSplitter, 
                             QTreeView, QLabel, QFrame, QMenu, QMessageBox)
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import Qt, QDir
from pathlib import Path

from .viewport import ViewportWidget
from kiln.envio.export import export_bundle_from_usd
from kiln.envio.bundle import EnvBundleError

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

        # Right Panel: Viewport
        self.viewport = ViewportWidget()
        self.splitter.addWidget(self.viewport)
        
        # Set initial sizes for splitter
        self.splitter.setSizes([200, 800])

    def _on_context_menu(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid(): return

        menu = QMenu()
        export_action = None
        path = self.model.filePath(index)
        if (not self.model.isDir(index)) and path.lower().endswith((".usd", ".usda", ".usdc", ".usdz")):
            export_action = menu.addAction("Export Kiln Env Bundle…")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.tree.viewport().mapToGlobal(position))

        if export_action is not None and action == export_action:
            self._export_env_bundle(path)
            return

        if action == delete_action:
            self._delete_file(index)

    def _export_env_bundle(self, usd_path: str) -> None:
        src = Path(usd_path)
        bundle_dir = src.parent / f"{src.stem}.kiln_env"
        try:
            export_bundle_from_usd(src, bundle_dir, overwrite=False)
        except EnvBundleError as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Export failed", f"Unexpected error: {e!r}")
            return

        QMessageBox.information(
            self,
            "Export complete",
            f"Env bundle created:\n{bundle_dir}\n\nFiles:\n- scene{src.suffix.lower()}\n- env.json",
        )

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
                # Pass to viewport for rendering
                if hasattr(self.viewport, 'load_scene'):
                    self.viewport.load_scene(path)

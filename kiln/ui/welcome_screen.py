from __future__ import annotations

"""Welcome screen (project creation + recent projects)."""

from typing import Any

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from pathlib import Path
from ..constants import APP_NAME

class WelcomeScreen(QWidget):
    """Landing screen for creating/opening projects and selecting recents."""

    # Signals to communicate with the main controller
    project_opened = pyqtSignal(Path)

    def __init__(self, config_manager: Any):
        super().__init__()
        self.config_manager = config_manager
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(50, 50, 50, 50)
        self.setLayout(layout)

        # Title
        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 48px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Main Actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        
        self.new_btn = QPushButton("New Project")
        self.new_btn.setFixedSize(180, 40)
        self.new_btn.clicked.connect(self._on_new_project)
        btn_layout.addWidget(self.new_btn)

        self.open_btn = QPushButton("Open Project")
        self.open_btn.setFixedSize(180, 40)
        self.open_btn.clicked.connect(self._on_open_project)
        btn_layout.addWidget(self.open_btn)

        layout.addLayout(btn_layout)

        # Recent Projects
        if self.config_manager.recent_projects:
            recent_label = QLabel("Recent")
            recent_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888; margin-top: 40px;")
            layout.addWidget(recent_label)

            for project_path in self.config_manager.recent_projects[:5]:
                item_btn = QPushButton(project_path.name)
                item_btn.setFlat(True)
                item_btn.setStyleSheet("text-align: left; font-size: 14px; padding: 5px; color: #3B8ED0;")
                item_btn.setToolTip(str(project_path))
                item_btn.clicked.connect(lambda checked, p=project_path: self._open_recent(p))
                layout.addWidget(item_btn)

    def _on_new_project(self) -> None:
        """Prompt for a project name and directory, create it, then emit `project_opened`."""
        name, ok = QInputDialog.getText(self, "New Project", "Enter project name:")
        if ok and name:
            parent_dir = QFileDialog.getExistingDirectory(self, "Select location for new project")
            if parent_dir:
                new_path = Path(parent_dir) / name
                if new_path.exists():
                    QMessageBox.critical(self, "Error", "A project with this name already exists.")
                else:
                    try:
                        new_path.mkdir(parents=True)
                        self.project_opened.emit(new_path)
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to create project: {e}")

    def _on_open_project(self) -> None:
        """Prompt for an existing project directory and emit `project_opened`."""
        path = QFileDialog.getExistingDirectory(self, "Select project folder")
        if path:
            self.project_opened.emit(Path(path))

    def _open_recent(self, path: Path) -> None:
        """Open a recent project, or remove it from recents if missing."""
        if path.exists():
            self.project_opened.emit(path)
        else:
            QMessageBox.critical(self, "Error", "This project no longer exists.")
            self.config_manager.remove_recent_project(path)
            self._refresh()

    def _refresh(self) -> None:
        """Rebuild the UI (used when the recent-project list changes)."""
        # Clear the old layout: unparent it so widgets can be GC'd.
        QWidget().setLayout(self.layout())  # Hack: unparent old layout
        self._init_ui()

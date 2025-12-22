import sys
import os

from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
import qdarkstyle

from kiln.config import ConfigManager
from kiln.ui.welcome_screen import WelcomeScreen
from kiln.ui.project_screen import ProjectScreen
from kiln.constants import APP_NAME

class KilnApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1024, 768)

        self.config_manager = ConfigManager()
        
        # Central widget is a stack of screens
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Initialize screens
        self.welcome_screen = WelcomeScreen(self.config_manager)
        self.project_screen = ProjectScreen()

        self.stack.addWidget(self.welcome_screen)
        self.stack.addWidget(self.project_screen)

        # Connect signals
        self.welcome_screen.project_opened.connect(self.open_project)

        self.show_welcome()

    def show_welcome(self):
        self.stack.setCurrentWidget(self.welcome_screen)
        self._setup_menu(is_project=False)

    def open_project(self, path):
        self.config_manager.add_recent_project(path)
        self.project_screen.set_project(path)
        self.stack.setCurrentWidget(self.project_screen)
        self._setup_menu(is_project=True)

    def _setup_menu(self, is_project=False):
        self.menuBar().clear()
        
        file_menu = self.menuBar().addMenu("&File")
        
        if is_project:
            # Project Menu
            project_menu = self.menuBar().addMenu("&Project")
            new_scene_action = QAction("&New Scene", self)
            new_scene_action.triggered.connect(self._create_new_scene)
            project_menu.addAction(new_scene_action)

            close_action = QAction("&Close Project", self)
            close_action.triggered.connect(self.show_welcome)
            file_menu.addAction(close_action)
            file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _create_new_scene(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        
        name, ok = QInputDialog.getText(self, "New Scene", "Enter scene name:")
        if ok and name:
            if not name.endswith(".usda"):
                name += ".usda"
            
            project_path = self.project_screen.project_path
            scene_path = project_path / name
            
            try:
                from pxr import Usd, UsdGeom
                stage = Usd.Stage.CreateNew(str(scene_path))
                if stage:
                    # Create default primitive: A Ground Plane
                    root = UsdGeom.Xform.Define(stage, '/World')
                    plane = UsdGeom.Mesh.Define(stage, '/World/GroundPlane')
                    
                    # Define a 10x10 plane at the origin (Y-up)
                    plane.GetPointsAttr().Set([(-5, 0, 5), (5, 0, 5), (5, 0, -5), (-5, 0, -5)])
                    plane.GetFaceVertexCountsAttr().Set([4])
                    plane.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])
                    plane.GetExtentAttr().Set([(-5, 0, -5), (5, 0, 5)])
                    
                    # Dark grey grid-like color
                    plane.GetDisplayColorAttr().Set([(0.3, 0.3, 0.3)])
                    
                    stage.GetRootLayer().Save()
                else:
                    raise Exception("Failed to create USD stage")
            except ImportError:
                QMessageBox.critical(self, "Error", "USD library (pxr) not found.\nPlease install 'usd-core' (pip install usd-core).")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create scene: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Apply dark theme
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
    
    window = KilnApp()
    window.show()
    sys.exit(app.exec())

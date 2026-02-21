from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QDoubleSpinBox, 
                             QHBoxLayout, QGroupBox, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QVector3D

class PropertiesWidget(QWidget):
    # Signal emitted when a property changes: (property_name, value)
    property_changed = pyqtSignal(str, object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_object = None
        self._updating = False  # Flag to prevent feedback loops
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title = QLabel("Properties")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        main_layout.addWidget(title)
        
        # Scroll area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        # Container widget for scroll area
        container = QWidget()
        self.properties_layout = QVBoxLayout(container)
        self.properties_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # Create property groups
        self._create_transform_group()
        
        # Initially show "No object selected"
        self.no_selection_label = QLabel("No object selected")
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setStyleSheet("color: #888; padding: 20px;")
        self.properties_layout.addWidget(self.no_selection_label)
        
    def _create_transform_group(self):
        """Create the Transform property group"""
        self.transform_group = QGroupBox("Transform")
        transform_layout = QVBoxLayout()
        
        # Position
        pos_label = QLabel("Position")
        pos_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        transform_layout.addWidget(pos_label)
        
        pos_layout = QHBoxLayout()
        self.pos_x = self._create_spinbox("X:")
        self.pos_y = self._create_spinbox("Y:")
        self.pos_z = self._create_spinbox("Z:")
        pos_layout.addWidget(QLabel("X:"))
        pos_layout.addWidget(self.pos_x)
        pos_layout.addWidget(QLabel("Y:"))
        pos_layout.addWidget(self.pos_y)
        pos_layout.addWidget(QLabel("Z:"))
        pos_layout.addWidget(self.pos_z)
        transform_layout.addLayout(pos_layout)
        
        # Rotation
        rot_label = QLabel("Rotation")
        rot_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        transform_layout.addWidget(rot_label)
        
        rot_layout = QHBoxLayout()
        self.rot_x = self._create_spinbox("X:", min_val=-360, max_val=360)
        self.rot_y = self._create_spinbox("Y:", min_val=-360, max_val=360)
        self.rot_z = self._create_spinbox("Z:", min_val=-360, max_val=360)
        rot_layout.addWidget(QLabel("X:"))
        rot_layout.addWidget(self.rot_x)
        rot_layout.addWidget(QLabel("Y:"))
        rot_layout.addWidget(self.rot_y)
        rot_layout.addWidget(QLabel("Z:"))
        rot_layout.addWidget(self.rot_z)
        transform_layout.addLayout(rot_layout)
        
        # Scale
        scale_label = QLabel("Scale")
        scale_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        transform_layout.addWidget(scale_label)
        
        scale_layout = QHBoxLayout()
        self.scale_x = self._create_spinbox("X:", min_val=0.01, max_val=100, default=1.0)
        self.scale_y = self._create_spinbox("Y:", min_val=0.01, max_val=100, default=1.0)
        self.scale_z = self._create_spinbox("Z:", min_val=0.01, max_val=100, default=1.0)
        scale_layout.addWidget(QLabel("X:"))
        scale_layout.addWidget(self.scale_x)
        scale_layout.addWidget(QLabel("Y:"))
        scale_layout.addWidget(self.scale_y)
        scale_layout.addWidget(QLabel("Z:"))
        scale_layout.addWidget(self.scale_z)
        transform_layout.addLayout(scale_layout)
        
        self.transform_group.setLayout(transform_layout)
        self.transform_group.hide()  # Hidden until object selected
        
    def _create_spinbox(self, label, min_val=-1000, max_val=1000, default=0.0):
        """Helper to create a spinbox with common settings"""
        spinbox = QDoubleSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(0.1)
        spinbox.setMinimumWidth(60)
        
        # Connect to value changed
        spinbox.valueChanged.connect(self._on_spinbox_changed)
        
        return spinbox
        
    def _on_spinbox_changed(self, value):
        """Handle spinbox value changes"""
        if self._updating or not self.current_object:
            return
            
        # Determine which property changed
        sender = self.sender()
        
        # Update object properties
        if sender == self.pos_x:
            self.current_object.position.setX(value)
            self.property_changed.emit("position", self.current_object.position)
        elif sender == self.pos_y:
            self.current_object.position.setY(value)
            self.property_changed.emit("position", self.current_object.position)
        elif sender == self.pos_z:
            self.current_object.position.setZ(value)
            self.property_changed.emit("position", self.current_object.position)
        elif sender == self.rot_x:
            self.current_object.rotation.setX(value)
            self.property_changed.emit("rotation", self.current_object.rotation)
        elif sender == self.rot_y:
            self.current_object.rotation.setY(value)
            self.property_changed.emit("rotation", self.current_object.rotation)
        elif sender == self.rot_z:
            self.current_object.rotation.setZ(value)
            self.property_changed.emit("rotation", self.current_object.rotation)
        elif sender == self.scale_x:
            self.current_object.scale.setX(value)
            self.property_changed.emit("scale", self.current_object.scale)
        elif sender == self.scale_y:
            self.current_object.scale.setY(value)
            self.property_changed.emit("scale", self.current_object.scale)
        elif sender == self.scale_z:
            self.current_object.scale.setZ(value)
            self.property_changed.emit("scale", self.current_object.scale)
    
    def set_object(self, obj):
        """Set the current object to display properties for"""
        self.current_object = obj
        
        if obj is None:
            self.transform_group.hide()
            self.no_selection_label.show()
            if self.transform_group.parent() is None:
                self.properties_layout.addWidget(self.transform_group)
            return
        
        # Show transform group and hide "no selection" label
        self.no_selection_label.hide()
        if self.transform_group.parent() is None:
            self.properties_layout.addWidget(self.transform_group)
        self.transform_group.show()
        
        # Update spinboxes with object values
        self._updating = True
        
        # Position
        self.pos_x.setValue(obj.position.x())
        self.pos_y.setValue(obj.position.y())
        self.pos_z.setValue(obj.position.z())
        
        # Rotation
        self.rot_x.setValue(obj.rotation.x())
        self.rot_y.setValue(obj.rotation.y())
        self.rot_z.setValue(obj.rotation.z())
        
        # Scale
        self.scale_x.setValue(obj.scale.x())
        self.scale_y.setValue(obj.scale.y())
        self.scale_z.setValue(obj.scale.z())
        
        self._updating = False

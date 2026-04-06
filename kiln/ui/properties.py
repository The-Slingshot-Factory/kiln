from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QDoubleSpinBox, 
                             QHBoxLayout, QGroupBox, QScrollArea, QComboBox,
                             QPushButton, QColorDialog, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QVector3D

class PropertiesWidget(QWidget):
    # Signal emitted when a property changes: (property_name, value)
    property_changed = pyqtSignal(str, object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_object = None
        self._updating = False  # Flag to prevent feedback loops
        self._numeric_bindings: list[tuple[object, str, type]] = []
        
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
        self._create_role_group()
        self._create_material_group()
        self._create_actor_group()
        self._create_npc_policy_group()
        
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
        self.pos_y.setEnabled(False)
        self.pos_y.setToolTip("Y position is locked in the editor.")
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

    def _create_role_group(self):
        """Create the Role property group"""
        self.role_group = QGroupBox("Role")
        role_layout = QVBoxLayout()

        self.role_combo = QComboBox()
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)

        role_layout.addWidget(self.role_combo)
        self.role_group.setLayout(role_layout)
        self.role_group.hide()

    def _create_material_group(self):
        """Create the Material/Color property group"""
        self.material_group = QGroupBox("Material")
        material_layout = QVBoxLayout()

        # Color picker
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        
        self.color_button = QPushButton()
        self.color_button.setFixedWidth(60)
        self.color_button.clicked.connect(self._on_color_clicked)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        
        material_layout.addLayout(color_layout)
        self.material_group.setLayout(material_layout)
        self.material_group.hide()

    def _bind_numeric(self, widget, attr_name: str, value_type: type = float):
        self._numeric_bindings.append((widget, attr_name, value_type))

    def _add_numeric_row(self, layout, label: str, widget):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addWidget(widget)
        layout.addLayout(row)

    def _create_actor_group(self):
        """Create actor control properties (car/npc roles)."""
        self.actor_group = QGroupBox("Actor")
        actor_layout = QVBoxLayout()

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Control mode:"))
        self.control_mode_combo = QComboBox()
        self.control_mode_combo.addItem("kinematic", userData="kinematic")
        self.control_mode_combo.addItem("force_torque", userData="force_torque")
        self.control_mode_combo.currentIndexChanged.connect(self._on_control_mode_changed)
        mode_row.addWidget(self.control_mode_combo)
        actor_layout.addLayout(mode_row)

        self.max_speed = self._create_spinbox("", min_val=0.0, max_val=100.0, default=5.0)
        self._bind_numeric(self.max_speed, "max_speed", float)
        self._add_numeric_row(actor_layout, "Max speed:", self.max_speed)

        self.speed_delta = self._create_spinbox("", min_val=0.0, max_val=20.0, default=0.5)
        self._bind_numeric(self.speed_delta, "speed_delta", float)
        self._add_numeric_row(actor_layout, "Speed delta:", self.speed_delta)

        self.turn_rate = self._create_spinbox("", min_val=0.0, max_val=20.0, default=1.5)
        self._bind_numeric(self.turn_rate, "turn_rate", float)
        self._add_numeric_row(actor_layout, "Turn rate:", self.turn_rate)

        self.force = self._create_spinbox("", min_val=0.0, max_val=1000.0, default=30.0)
        self._bind_numeric(self.force, "force", float)
        self._add_numeric_row(actor_layout, "Force:", self.force)

        self.torque = self._create_spinbox("", min_val=0.0, max_val=1000.0, default=10.0)
        self._bind_numeric(self.torque, "torque", float)
        self._add_numeric_row(actor_layout, "Torque:", self.torque)

        self.initial_yaw = self._create_spinbox("", min_val=-6.283, max_val=6.283, default=0.0)
        self._bind_numeric(self.initial_yaw, "initial_yaw", float)
        self._add_numeric_row(actor_layout, "Initial yaw:", self.initial_yaw)

        self.actor_group.setLayout(actor_layout)
        self.actor_group.hide()

    def _create_npc_policy_group(self):
        """Create NPC policy properties (only shown for npc role)."""
        self.npc_policy_group = QGroupBox("NPC Policy")
        policy_layout = QVBoxLayout()

        roam_min_row = QHBoxLayout()
        roam_min_row.addWidget(QLabel("Roam min XY:"))
        self.roam_xy_min_x = self._create_spinbox("", min_val=-1000.0, max_val=1000.0, default=-12.0)
        self.roam_xy_min_y = self._create_spinbox("", min_val=-1000.0, max_val=1000.0, default=-12.0)
        roam_min_row.addWidget(QLabel("X:"))
        roam_min_row.addWidget(self.roam_xy_min_x)
        roam_min_row.addWidget(QLabel("Y:"))
        roam_min_row.addWidget(self.roam_xy_min_y)
        policy_layout.addLayout(roam_min_row)

        roam_max_row = QHBoxLayout()
        roam_max_row.addWidget(QLabel("Roam max XY:"))
        self.roam_xy_max_x = self._create_spinbox("", min_val=-1000.0, max_val=1000.0, default=12.0)
        self.roam_xy_max_y = self._create_spinbox("", min_val=-1000.0, max_val=1000.0, default=12.0)
        roam_max_row.addWidget(QLabel("X:"))
        roam_max_row.addWidget(self.roam_xy_max_x)
        roam_max_row.addWidget(QLabel("Y:"))
        roam_max_row.addWidget(self.roam_xy_max_y)
        policy_layout.addLayout(roam_max_row)

        self.goal_tolerance = self._create_spinbox("", min_val=0.0, max_val=50.0, default=0.5)
        self._bind_numeric(self.goal_tolerance, "goal_tolerance", float)
        self._add_numeric_row(policy_layout, "Goal tolerance:", self.goal_tolerance)

        self.cruise_speed = self._create_spinbox("", min_val=0.0, max_val=100.0, default=4.0)
        self._bind_numeric(self.cruise_speed, "cruise_speed", float)
        self._add_numeric_row(policy_layout, "Cruise speed:", self.cruise_speed)

        self.heading_threshold = self._create_spinbox("", min_val=0.0, max_val=6.283, default=0.25)
        self._bind_numeric(self.heading_threshold, "heading_threshold", float)
        self._add_numeric_row(policy_layout, "Heading threshold:", self.heading_threshold)

        self.raycast_length = self._create_spinbox("", min_val=0.0, max_val=100.0, default=2.0)
        self._bind_numeric(self.raycast_length, "raycast_length", float)
        self._add_numeric_row(policy_layout, "Raycast length:", self.raycast_length)

        self.raycast_angle = self._create_spinbox("", min_val=0.0, max_val=3.1416, default=0.45)
        self._bind_numeric(self.raycast_angle, "raycast_angle", float)
        self._add_numeric_row(policy_layout, "Raycast angle:", self.raycast_angle)

        self.avoid_distance = self._create_spinbox("", min_val=0.0, max_val=50.0, default=1.25)
        self._bind_numeric(self.avoid_distance, "avoid_distance", float)
        self._add_numeric_row(policy_layout, "Avoid distance:", self.avoid_distance)

        self.brake_distance = self._create_spinbox("", min_val=0.0, max_val=50.0, default=0.5)
        self._bind_numeric(self.brake_distance, "brake_distance", float)
        self._add_numeric_row(policy_layout, "Brake distance:", self.brake_distance)

        self.avoid_radius = self._create_spinbox("", min_val=0.0, max_val=50.0, default=1.0)
        self._bind_numeric(self.avoid_radius, "avoid_radius", float)
        self._add_numeric_row(policy_layout, "Avoid radius:", self.avoid_radius)

        self.emergency_brake_radius = self._create_spinbox("", min_val=0.0, max_val=50.0, default=0.6)
        self._bind_numeric(self.emergency_brake_radius, "emergency_brake_radius", float)
        self._add_numeric_row(policy_layout, "Emergency brake radius:", self.emergency_brake_radius)

        self.stuck_steps = self._create_int_spinbox(min_val=0, max_val=10000, default=30)
        self._bind_numeric(self.stuck_steps, "stuck_steps", int)
        self._add_numeric_row(policy_layout, "Stuck steps:", self.stuck_steps)

        self.progress_eps = self._create_spinbox("", min_val=0.0, max_val=1.0, default=0.001)
        self._bind_numeric(self.progress_eps, "progress_eps", float)
        self._add_numeric_row(policy_layout, "Progress eps:", self.progress_eps)

        self.nav_cell_size = self._create_spinbox("", min_val=0.01, max_val=10.0, default=0.5)
        self._bind_numeric(self.nav_cell_size, "nav_cell_size", float)
        self._add_numeric_row(policy_layout, "Nav cell size:", self.nav_cell_size)

        self.nav_inflate = self._create_spinbox("", min_val=0.0, max_val=10.0, default=0.55)
        self._bind_numeric(self.nav_inflate, "nav_inflate", float)
        self._add_numeric_row(policy_layout, "Nav inflate:", self.nav_inflate)

        self.waypoint_tolerance = self._create_spinbox("", min_val=0.0, max_val=10.0, default=0.6)
        self._bind_numeric(self.waypoint_tolerance, "waypoint_tolerance", float)
        self._add_numeric_row(policy_layout, "Waypoint tolerance:", self.waypoint_tolerance)

        self.max_goal_samples = self._create_int_spinbox(min_val=1, max_val=100000, default=50)
        self._bind_numeric(self.max_goal_samples, "max_goal_samples", int)
        self._add_numeric_row(policy_layout, "Max goal samples:", self.max_goal_samples)

        self.npc_policy_group.setLayout(policy_layout)
        self.npc_policy_group.hide()
        
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

    def _create_int_spinbox(self, min_val=0, max_val=10000, default=0):
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default)
        spinbox.setSingleStep(1)
        spinbox.setMinimumWidth(60)
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
        elif sender in (self.roam_xy_min_x, self.roam_xy_min_y):
            self.current_object.roam_xy_min = (float(self.roam_xy_min_x.value()), float(self.roam_xy_min_y.value()))
            self.property_changed.emit("roam_xy_min", self.current_object.roam_xy_min)
        elif sender in (self.roam_xy_max_x, self.roam_xy_max_y):
            self.current_object.roam_xy_max = (float(self.roam_xy_max_x.value()), float(self.roam_xy_max_y.value()))
            self.property_changed.emit("roam_xy_max", self.current_object.roam_xy_max)
        else:
            for widget, attr_name, value_type in self._numeric_bindings:
                if sender == widget:
                    setattr(self.current_object, attr_name, value_type(value))
                    self.property_changed.emit(attr_name, getattr(self.current_object, attr_name))
                    break

    def _on_role_changed(self, index: int):
        """Handle role combo changes."""
        if self._updating or not self.current_object:
            return
        role = self.role_combo.currentData()
        self.current_object.role = role
        self.property_changed.emit("role", role)
        self._toggle_role_dependent_groups()

    def _on_control_mode_changed(self, index: int):
        if self._updating or not self.current_object:
            return
        control_mode = self.control_mode_combo.currentData()
        self.current_object.control_mode = str(control_mode)
        self.property_changed.emit("control_mode", control_mode)

    def _toggle_role_dependent_groups(self):
        role = self.current_object.role if self.current_object else None
        is_actor = role in ("car", "npc")
        self.actor_group.setVisible(is_actor)
        self.npc_policy_group.setVisible(role == "npc")

    def _on_color_clicked(self):
        """Open a color dialog to change the object color."""
        if self._updating or not self.current_object:
            return
            
        color = QColorDialog.getColor(self.current_object.color, self, "Select Object Color")
        if color.isValid():
            self.current_object.color = color
            self._update_color_button_style(color)
            self.property_changed.emit("color", color)

    def _update_color_button_style(self, color):
        """Update the color button's background to match the current color."""
        self.color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #555;")

    def set_object(self, obj):
        """Set the current object to display properties for"""
        self.current_object = obj
        
        if obj is None:
            self.transform_group.hide()
            self.role_group.hide()
            self.actor_group.hide()
            self.npc_policy_group.hide()
            self.no_selection_label.show()
            if self.transform_group.parent() is None:
                self.properties_layout.addWidget(self.transform_group)
            if self.role_group.parent() is None:
                self.properties_layout.addWidget(self.role_group)
            if self.material_group.parent() is None:
                self.properties_layout.addWidget(self.material_group)
            if self.actor_group.parent() is None:
                self.properties_layout.addWidget(self.actor_group)
            if self.npc_policy_group.parent() is None:
                self.properties_layout.addWidget(self.npc_policy_group)
            self.material_group.hide()
            return
        
        # Show transform group and hide "no selection" label
        self.no_selection_label.hide()
        if self.transform_group.parent() is None:
            self.properties_layout.addWidget(self.transform_group)
        self.transform_group.show()

        if self.role_group.parent() is None:
            self.properties_layout.addWidget(self.role_group)
        self.role_group.show()

        if self.material_group.parent() is None:
            self.properties_layout.addWidget(self.material_group)
        self.material_group.show()
        if self.actor_group.parent() is None:
            self.properties_layout.addWidget(self.actor_group)
        if self.npc_policy_group.parent() is None:
            self.properties_layout.addWidget(self.npc_policy_group)
        
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

        # Role - Re-populate based on supported roles
        self.role_combo.clear()
        for r in obj.SUPPORTED_ROLES:
            self.role_combo.addItem("(none)" if r is None else r, userData=r)
            
        idx = self.role_combo.findData(obj.role)
        self.role_combo.setCurrentIndex(max(idx, 0))

        mode_idx = self.control_mode_combo.findData(getattr(obj, "control_mode", "kinematic"))
        self.control_mode_combo.setCurrentIndex(max(mode_idx, 0))

        self.max_speed.setValue(float(getattr(obj, "max_speed", 5.0)))
        self.speed_delta.setValue(float(getattr(obj, "speed_delta", 0.5)))
        self.turn_rate.setValue(float(getattr(obj, "turn_rate", 1.5)))
        self.force.setValue(float(getattr(obj, "force", 30.0)))
        self.torque.setValue(float(getattr(obj, "torque", 10.0)))
        self.initial_yaw.setValue(float(getattr(obj, "initial_yaw", 0.0)))

        roam_min = getattr(obj, "roam_xy_min", (-12.0, -12.0))
        roam_max = getattr(obj, "roam_xy_max", (12.0, 12.0))
        self.roam_xy_min_x.setValue(float(roam_min[0]))
        self.roam_xy_min_y.setValue(float(roam_min[1]))
        self.roam_xy_max_x.setValue(float(roam_max[0]))
        self.roam_xy_max_y.setValue(float(roam_max[1]))
        self.goal_tolerance.setValue(float(getattr(obj, "goal_tolerance", 0.5)))
        self.cruise_speed.setValue(float(getattr(obj, "cruise_speed", 4.0)))
        self.heading_threshold.setValue(float(getattr(obj, "heading_threshold", 0.25)))
        self.raycast_length.setValue(float(getattr(obj, "raycast_length", 2.0)))
        self.raycast_angle.setValue(float(getattr(obj, "raycast_angle", 0.45)))
        self.avoid_distance.setValue(float(getattr(obj, "avoid_distance", 1.25)))
        self.brake_distance.setValue(float(getattr(obj, "brake_distance", 0.5)))
        self.avoid_radius.setValue(float(getattr(obj, "avoid_radius", 1.0)))
        self.emergency_brake_radius.setValue(float(getattr(obj, "emergency_brake_radius", 0.6)))
        self.stuck_steps.setValue(int(getattr(obj, "stuck_steps", 30)))
        self.progress_eps.setValue(float(getattr(obj, "progress_eps", 0.001)))
        self.nav_cell_size.setValue(float(getattr(obj, "nav_cell_size", 0.5)))
        self.nav_inflate.setValue(float(getattr(obj, "nav_inflate", 0.55)))
        self.waypoint_tolerance.setValue(float(getattr(obj, "waypoint_tolerance", 0.6)))
        self.max_goal_samples.setValue(int(getattr(obj, "max_goal_samples", 50)))
        
        # Color
        self._update_color_button_style(obj.color)
        self._toggle_role_dependent_groups()
        
        self._updating = False

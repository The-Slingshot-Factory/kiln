from __future__ import annotations

from enum import Enum, IntEnum


class DiscreteAction(IntEnum):
    """
    Minimal 4-action discrete control space.

    Note: There is intentionally no NOOP for now; the env can add one later if desired.
    """

    ACCELERATE = 0
    DECELERATE = 1
    TURN_LEFT = 2
    TURN_RIGHT = 3


class ControlMode(str, Enum):
    """
    How actions are applied to the underlying rigid body.
    """

    KINEMATIC = "kinematic"  # default: set target linear velocity + yaw-rate
    FORCE_TORQUE = "force_torque"  # optional: apply forces/torques each tick



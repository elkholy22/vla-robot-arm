import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

@dataclass
class RobotState:
    motor_positions: List[float]
    camera_frames: List[np.ndarray]
    # Optional calibrated joint angles (degrees) relative to the current zero/reference.
    # When available the recorder will store these so downstream dataset builders
    # don't need to re-compute kinematics to obtain the joint angles used by the UI.
    joint_angles: Optional[List[float]] = None
    # Optional end-effector Cartesian position [x,y,z] in meters (or same units as model)
    ee_position: Optional[List[float]] = None
    timestamp: float = 0.0

@dataclass
class RobotCommand:
    target_velocities: List[float]
    target_positions: List[List[float]]
    gripper_open: List[bool]
    halt_flag: bool
    timestamp: float

@dataclass
class GoalMessage:
    text_prompt: str
    goal_image: List[np.ndarray]
    task_id: str
    is_update: bool #flag to clear model history

@dataclass
class SystemConfigMessage:
    urdf_xml_content: str
    motor_limits: Dict[str, List[float]]
    motor_port_mapping: Dict[str, int]
    control_frequency_hz: int = 30

class ModelMode(Enum):
    BASE = 0
    SMALL = 1
    FINETUNED = 2
import numpy as np
from dataclasses import dataclass
from typing import List, Dict
from enum import Enum

@dataclass
class RobotState:
    motor_positions: List[float]
    camera_frames: List[np.ndarray] 
    timestamp: float

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
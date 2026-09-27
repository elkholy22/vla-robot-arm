import os
import sys
import time
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import local modules
from core.config_loader import load_config
from hardware.robot_arm import RobotArm
from hardware.camera_manager import camera_manager
from control.heatmap import render_heatmap

# Ensure octolego-ees modules can be imported
try:
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    octo_path = os.path.join(src_dir, "octolego-ees")
    if octo_path not in sys.path:
        sys.path.insert(0, octo_path)
except Exception:
    pass

from shared.classes import RobotState, RobotCommand, GoalMessage, SystemConfigMessage
from pi.pi_recorder import PiDataRecorder

logger = logging.getLogger("arm_controller")

class ControlLeaseManager:
    """Manages exclusive lease-based locking for UI commands."""
    def __init__(self, duration_sec: Optional[float] = None):
        try:
            config = load_config()
            control_cfg = config.get("control", {})
        except Exception:
            control_cfg = {}
        self.duration = float(duration_sec) if duration_sec is not None else float(control_cfg.get("lease_duration_sec", 90.0))
        self.lease_holder_id: Optional[str] = None
        self.last_activity: float = 0.0
        self.lock = threading.Lock()

    def acquire_lease(self, client_id: str) -> bool:
        with self.lock:
            now = time.monotonic()
            if self.lease_holder_id is None or (now - self.last_activity > self.duration):
                self.lease_holder_id = client_id
                self.last_activity = now
                logger.info(f"Lease acquired by {client_id}")
                return True
            if self.lease_holder_id == client_id:
                self.last_activity = now
                return True
            return False

    def validate_lease(self, client_id: str) -> bool:
        with self.lock:
            now = time.monotonic()
            # If no active lease exists or the lease has expired, commands are allowed but we do NOT auto-claim it.
            if self.lease_holder_id is None or (now - self.last_activity > self.duration):
                return True
            # If the current client holds the lease, allow command and refresh activity timestamp.
            if self.lease_holder_id == client_id:
                self.last_activity = now
                return True
            return False

    def release_lease(self, client_id: str) -> bool:
        with self.lock:
            if self.lease_holder_id == client_id:
                self.lease_holder_id = None
                logger.info(f"Lease released by {client_id}")
                return True
            return False

    def get_holder(self) -> str:
        with self.lock:
            now = time.monotonic()
            if self.lease_holder_id and (now - self.last_activity <= self.duration):
                return self.lease_holder_id
            self.lease_holder_id = None
            return "None"


class VLAModerationManager:
    """Handles VLA client registrations, modes, and command moderation."""
    def __init__(self, arm: RobotArm, ui_callback):
        self.arm = arm
        self.ui = ui_callback
        self.mode = "block"  # block, moderated, auto
        self.agents: Dict[str, Dict[str, Any]] = {}  # agent_id -> info
        self.pending_action: Optional[Dict[str, Any]] = None
        self.lock = threading.Lock()

    def register_agent(self, agent_id: str, name: str, options: Dict[str, Any]) -> bool:
        with self.lock:
            self.agents[agent_id] = {
                "name": name,
                "options": options,
                "last_seen": time.monotonic()
            }
            logger.info(f"Registered VLA agent: {name} ({agent_id})")
            self.ui.log(f"VLA Agent Registered: {name} with options {options}")
            return True

    def set_mode(self, mode: str) -> bool:
        if mode not in ["block", "moderated", "auto"]:
            return False
        with self.lock:
            self.mode = mode
            if mode == "block":
                self.pending_action = None
        return True

    def handle_inference_action(self, agent_id: str, target_positions: List[List[float]], target_velocities: List[float]) -> tuple[bool, str]:
        """Routes VLA actions based on safety mode."""
        with self.lock:
            if self.mode == "block":
                return False, "VLA action rejected: mode is BLOCK."

            action = {
                "agent_id": agent_id,
                "target_positions": target_positions,
                "target_velocities": target_velocities,
                "timestamp": time.time()
            }

            if self.mode == "moderated":
                self.pending_action = action
                self.ui.notify_vla_pending(action)
                self.ui.log(f"VLA Action Pending Approval from agent {agent_id}.")
                return True, "Action queued for human moderation approval."

            if self.mode == "auto":
                # Execute immediately
                success, msg = self._execute_action(action)
                return success, msg

        return False, "Unknown state"

    def approve_pending(self) -> tuple[bool, str]:
        with self.lock:
            if not self.pending_action:
                return False, "No pending VLA action to approve."
            action = self.pending_action
            self.pending_action = None
            success, msg = self._execute_action(action)
            self.ui.notify_vla_resolved("approved")
            return success, f"Approved and executed: {msg}"

    def reject_pending(self) -> tuple[bool, str]:
        with self.lock:
            if not self.pending_action:
                return False, "No pending VLA action to reject."
            self.pending_action = None
            self.ui.notify_vla_resolved("rejected")
            self.ui.log("VLA pending action rejected by human.")
            return True, "Pending VLA action rejected successfully."

    def trigger_inference(self) -> tuple[bool, str]:
        """Requests VLA clients to send next action step."""
        with self.lock:
            if not self.agents:
                return False, "No active VLA agents connected."
            # Broad-cast inference trigger event to all agents
            self.ui.trigger_vla_inference()
            return True, "Inference request dispatched to VLA clients."

    def _execute_action(self, action: Dict[str, Any]) -> tuple[bool, str]:
        # Drives coordinates or joint angles
        pos = action["target_positions"]
        if not pos or len(pos[0]) != 3:
            return False, "Invalid joint position length. Must be 3."

        # target_positions is list of lists, apply first step
        deltas = pos[0]
        success, msg = self.arm.apply_joint_delta_command(deltas)
        self.ui.log(f"VLA Execution: {msg}")
        return success, msg


class ArmController:
    def __init__(self, ui_callback):
        self.config = load_config()
        self.ui = ui_callback
        
        # Initialize lease & VLA managers
        self.lease = ControlLeaseManager()
        
        # Initialize physical arm hardware
        self.arm = RobotArm()
        logger.info("Initialized physical RobotArm.")

        self.vla = VLAModerationManager(self.arm, ui_callback)

        # Dataset Recording states
        self.is_capturing = False
        self.capture_count = 0
        self.goal_text = self.config.get("recording", {}).get("default_prompt", "manual control")
        
        save_dir = self.config["recording"]["save_directory"]
        self.recorder = PiDataRecorder(save_dir=save_dir)
        self.capture_lock = threading.Lock()

        # Background state monitoring / logging thread
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def get_telemetry_data(self) -> Dict[str, Any]:
        """Read and construct the current telemetry state."""
        angles = self.arm.get_joint_angles()
        speeds = self.arm.get_speeds()
        ee_pos = self.arm.get_end_effector_position()
        
        with self.capture_lock:
            is_capturing = self.is_capturing
            capture_count = self.capture_count

        return {
            "angles": angles,
            "speeds": speeds,
            "ee_position": ee_pos,
            "limits": self.arm.limits,
            "is_homed": not self.arm.pwm_blocked,
            "pwm_blocked": self.arm.pwm_blocked,
            "is_homing": getattr(self.arm, "is_homing", False),
            "is_calibrating": getattr(self.arm, "is_calibrating", False),
            "is_capturing": is_capturing,
            "capture_count": capture_count,
            "lease_holder": self.lease.get_holder(),
            "vla_mode": self.vla.mode,
            "has_pending_vla": self.vla.pending_action is not None,
            "offsets": self.arm.offsets
        }

    def _monitor_loop(self):
        hz = self.config["recording"]["frequency_hz"]
        interval = 1.0 / hz
        logger.info(f"ArmController monitoring loop active at {hz}Hz")

        last_telemetry_data = None

        while self.running:
            start_time = time.monotonic()
            
            # Read telemetry state
            telemetry_data = self.get_telemetry_data()
            motor_positions = self.arm.get_motor_positions()

            # Helper to check if telemetry changed
            def telemetry_changed(prev: Optional[Dict[str, Any]], curr: Dict[str, Any]) -> bool:
                if prev is None:
                    return True
                
                # Check non-float statuses
                for key in [
                    "is_homed", "pwm_blocked", "is_homing", "is_calibrating", 
                    "is_capturing", "capture_count", "lease_holder", "vla_mode", 
                    "has_pending_vla"
                ]:
                    if prev.get(key) != curr.get(key):
                        return True

                # Check dict/list fields
                for key in ["limits", "offsets"]:
                    if prev.get(key) != curr.get(key):
                        return True
                        
                # Check angles (dict of axis -> float)
                prev_angles = prev.get("angles", {})
                curr_angles = curr.get("angles", {})
                for axis in ["A", "B", "C"]:
                    if abs(prev_angles.get(axis, 0.0) - curr_angles.get(axis, 0.0)) > 0.05:
                        return True

                # Check speeds (dict of axis -> float)
                prev_speeds = prev.get("speeds", {})
                curr_speeds = curr.get("speeds", {})
                for axis in ["A", "B", "C"]:
                    if abs(prev_speeds.get(axis, 0.0) - curr_speeds.get(axis, 0.0)) > 0.01:
                        return True

                # Check ee_position (dict of x, y, z -> float)
                prev_ee = prev.get("ee_position", {})
                curr_ee = curr.get("ee_position", {})
                for coord in ["x", "y", "z"]:
                    if abs(prev_ee.get(coord, 0.0) - curr_ee.get(coord, 0.0)) > 0.001:
                        return True

                return False

            # Check if telemetry has updated (changed)
            if telemetry_changed(last_telemetry_data, telemetry_data):
                self.ui.update_telemetry(telemetry_data)
                last_telemetry_data = telemetry_data

            # If capturing is active, log step
            with self.capture_lock:
                is_capturing = self.is_capturing
            if is_capturing:
                angles = telemetry_data["angles"]
                speeds = telemetry_data["speeds"]
                ee_pos = telemetry_data["ee_position"]
                
                # Capture camera frames as JPEG compressed bytes
                frame0 = camera_manager.get_frame(0)
                frame1 = camera_manager.get_frame(1)
                frames = [frame0, frame1]

                state = RobotState(
                    motor_positions=[motor_positions["A"], motor_positions["B"], motor_positions["C"]],
                    camera_frames=frames,
                    joint_angles=[angles["A"], angles["B"], angles["C"]],
                    ee_position=[ee_pos["x"], ee_pos["y"], ee_pos["z"]],
                    timestamp=time.time()
                )

                targets = self.arm.get_targets()
                target_pos = [[
                    targets["A"] if targets["A"] is not None else angles["A"],
                    targets["B"] if targets["B"] is not None else angles["B"],
                    targets["C"] if targets["C"] is not None else angles["C"]
                ]]
                
                cmd = RobotCommand(
                    target_velocities=[speeds["A"], speeds["B"], speeds["C"]],
                    target_positions=target_pos,
                    gripper_open=[False],
                    halt_flag=telemetry_data["pwm_blocked"],
                    timestamp=time.time()
                )

                should_log = False
                with self.capture_lock:
                    if self.is_capturing:
                        self.capture_count += 1
                        should_log = True

                if should_log:
                    try:
                        self.recorder.log_step(state, cmd)
                    except Exception as e:
                        logger.error(f"Failed to log dataset step: {e}")

            # Sleep remaining interval time
            elapsed = time.monotonic() - start_time
            sleep_time = max(0.001, interval - elapsed)
            time.sleep(sleep_time)

    def toggle_capture(self) -> bool:
        with self.capture_lock:
            if not self.is_capturing:
                # Start episode
                self.capture_count = 0
                task_id = f"ep_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                goal = GoalMessage(text_prompt=self.goal_text, goal_image=[], task_id=task_id, is_update=True)
                
                limits_dict = {}
                for axis, val in self.arm.limits.items():
                    limits_dict[axis] = [val[0], val[1]]
                    
                sys_config = SystemConfigMessage(
                    urdf_xml_content="",
                    motor_limits=limits_dict,
                    motor_port_mapping={"A": 0, "B": 1, "C": 2}
                )

                self.recorder.start_episode(goal, sys_config)
                self.is_capturing = True
                logger.info("Dataset episode capture started.")
            else:
                # Stop episode
                self.recorder.end_episode()
                self.is_capturing = False

                # Render heatmap after stopping capture
                render_heatmap()  

                logger.info("Dataset episode capture stopped.")
            return self.is_capturing

    def set_goal_text(self, text: str):
        self.goal_text = text
        logger.info(f"Goal prompt set: {text}")

    def shutdown(self):
        self.running = False
        if self.is_capturing:
            # Render heatmap after stopping capture
            render_heatmap()
            # Stop episode
            self.recorder.end_episode()
        home_first = self.config.get("robot", {}).get("home_on_shutdown", False)
        logger.info(f"Shutting down arm controller (home_first={home_first})...")
        self.arm.safe_shutdown(home_first=home_first)
        logger.info("ArmController shut down.")

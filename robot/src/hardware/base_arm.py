import os
import time
import logging
import threading
from typing import Optional, Dict, Sequence, Any
from abc import ABC, abstractmethod

from core.config_loader import load_config
from hardware.kinematics import PinocchioKinematics

logger = logging.getLogger("robot_arm")


class BaseRobotArm(ABC):
    def __init__(
        self,
        motor_ee_port="A",
        motor_vert_port="B",
        motor_base_port="C",
        urdf_file="zeroshot_prototype.xml"
    ):
        if getattr(self, "_initialized", False):
            return

        self.config = load_config()
        self.directions = self.config["robot"].get("directions", {"A": 1, "B": 1, "C": 1})
        self.gear_ratios = self.config["robot"]["gear_ratios"]
        self.limits = self.config["robot"]["limits"]
        self.offsets = self.config["robot"]["offsets"]
        self.absolute_offsets = self.config["robot"]["absolute_offsets"]
        self.default_pwm = self.config["robot"]["default_pwm"]
        self.current_pwm = {
            axis: self.default_pwm[axis].copy()
            for axis in ["A", "B", "C"]
        }

        # Abstract motor initialization overridden by subclasses
        self._init_motors(motor_ee_port, motor_vert_port, motor_base_port)

        self.targets = {"A": None, "B": None, "C": None}
        self.jogs = {"A": 0.0, "B": 0.0, "C": 0.0}
        self.jog_scales = {"A": 1.0, "B": 1.0, "C": 1.0}
        self.pwm_blocked = False
        self.is_homing = False
        self.is_calibrating = False
        self.ik_solver = None

        # Stall detection settings (to prevent motor burnout/stripped gears)
        self.STALL_TIMEOUT_SECONDS = 1.5
        self.STALL_MIN_PROGRESS_DEG = 1.0
        self.stall_states = {
            axis: {'command': None, 'last_pos': 0.0, 'last_progress_time': time.monotonic()}
            for axis in ['A', 'B', 'C']
        }

        # Proportional movement control & hysteresis settings
        self.DECEL_THRESHOLD_DEG = 15.0  # Motor degrees where proportional deceleration begins
        self.MIN_PWM = 0.08              # Minimum PWM speed to prevent stalling near target
        self.TOLERANCE_DEG = 2.0         # Deadband tolerance in motor degrees
        self.HYSTERESIS_DEG = 1.0        # Extra degrees needed before re-triggering settled axis
        self.target_settled = {axis: False for axis in ['A', 'B', 'C']}
        self.last_sent_pwm = {axis: None for axis in ['A', 'B', 'C']}

        # Motor encoder offset states
        # The physical arm stores raw absolute positions and calculates continuous counts
        self.pos_dict = {
            "A_offset": self.motor_ee.get_aposition(),
            "B_offset": self.motor_vert.get_aposition(),
            "C_offset": self.motor_base.get_aposition(),
            "A_pos": 0.0,
            "B_pos": 0.0,
            "C_pos": 0.0,
            "A_revs": 0,
            "B_revs": 0,
            "C_revs": 0
        }

        self.position_jump_warnings = []
        self.load_position_data()

        # Load URDF for kinematics from core/ subdirectory
        src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.urdf_file = os.path.join(src_dir, "core", urdf_file)
        self.has_kinematics = False
        try:
            self._get_ik_solver()
            self.has_kinematics = True
        except Exception as e:
            logger.warning(f"Kinematics error: {e}")

        # Start physical hardware feedback and driver loop
        self.running = True
        self.thread = threading.Thread(target=self._hardware_loop, daemon=True)
        self.thread.start()
        logger.info("RobotArm Driver Loop started.")

        self._initialized = True

    def load_position_data(self) -> bool:
        """Load saved motor position tracking data from config.json's position_data key."""
        pos_data = self.config.get("robot", {}).get("position_data", {})
        if not pos_data:
            logger.info("[RobotArm] No saved position data found in config. Starting with current motor positions as zero offsets.")
            return False

        try:
            for axis in ['A', 'B', 'C']:
                pos_key = f'{axis}_pos'
                revs_key = f'{axis}_revs'
                if pos_key in pos_data:
                    self.pos_dict[pos_key] = float(pos_data[pos_key])
                if revs_key in pos_data:
                    self.pos_dict[f"{axis}_revs"] = int(pos_data[revs_key])

            self.check_position_jumps()
            logger.info("[RobotArm] Continuous position data loaded from config.json")
            return True
        except Exception as e:
            logger.warning(f"[RobotArm] Failed to load position data: {e}")
            return False

    def save_position_data(self):
        """Save the current dynamic pos_dict back to config.json persistently."""
        try:
            import core.config_loader as cl
            config = cl.load_config()
            if "robot" not in config:
                config["robot"] = {}
            if "position_data" not in config["robot"]:
                config["robot"]["position_data"] = {}

            for axis in ['A', 'B', 'C']:
                config["robot"]["position_data"][f"{axis}_pos"] = round(self.pos_dict[f"{axis}_pos"], 3)
                config["robot"]["position_data"][f"{axis}_revs"] = int(self.pos_dict[f"{axis}_revs"])

            cl.save_config(config)
            logger.debug("[RobotArm] Position data saved to config.json")
        except Exception as e:
            logger.warning(f"[RobotArm] Failed to save position data to config.json: {e}")

    def check_position_jumps(self):
        """Warn if a motor moved a lot while the program was not running."""
        self.position_jump_warnings = []
        POSITION_JUMP_WARNING_DEG = 30.0  # constant from main
        for axis, motor in self.motors.items():
            current_pos = (
                motor.get_aposition()
                - self.pos_dict[f'{axis}_offset']
                + self.pos_dict[f'{axis}_revs'] * 360
            )
            old_pos = self.pos_dict[f'{axis}_pos']
            delta = current_pos - old_pos
            if abs(delta) > POSITION_JUMP_WARNING_DEG:
                warning = (
                    f"WARNING: {axis} position jump from {old_pos:.1f} to {current_pos:.1f} "
                    f"({delta:+.1f}°). Check motor position or reset offsets."
                )
                self.position_jump_warnings.append(warning)
                logger.warning(warning)
        return self.position_jump_warnings

    @abstractmethod
    def _init_motors(self, motor_ee_port: str, motor_vert_port: str, motor_base_port: str):
        """Initialize motor connections. Must populate self.motor_ee, self.motor_vert, self.motor_base, and self.motors."""
        pass

    def _reset_stall_state(self, axis: str, pos: Optional[float] = None):
        axis = axis.upper()
        self.stall_states[axis] = {
            'command': None,
            'last_pos': self.pos_dict[f'{axis}_pos'] if pos is None else pos,
            'last_progress_time': time.monotonic(),
        }

    def _is_stalled(self, axis: str, command: Any, pos: float) -> bool:
        axis = axis.upper()
        state = self.stall_states[axis]
        now = time.monotonic()

        if state['command'] != command:
            state['command'] = command
            state['last_pos'] = pos
            state['last_progress_time'] = now
            return False

        if abs(pos - state['last_pos']) >= self.STALL_MIN_PROGRESS_DEG:
            state['last_pos'] = pos
            state['last_progress_time'] = now
            return False

        return now - state['last_progress_time'] >= self.STALL_TIMEOUT_SECONDS

    def _stop_stalled_axis(self, axis: str, motor, pos: float, command: Any):
        axis = axis.upper()
        motor.coast()
        self.targets[axis] = None
        self.jogs[axis] = 0.0
        self.target_settled[axis] = True
        self.last_sent_pwm[axis] = None
        self._reset_stall_state(axis, pos=pos)
        logger.warning(
            f"[RobotArm] Motion stalled on axis {axis} while executing {command}. "
            f"Position {pos:.1f}. Coasting axis."
        )

    def _hardware_loop(self):
        while self.running:
            if not self.pwm_blocked:
                # Update continuous counting positions
                for axis, motor in self.motors.items():
                    current_raw = motor.get_aposition()
                    prev_raw = self.pos_dict[f"{axis}_pos"] + self.pos_dict[f"{axis}_offset"] - (self.pos_dict[f"{axis}_revs"] * 360)
                    delta_raw = current_raw - prev_raw

                    if delta_raw < -180:
                        self.pos_dict[f"{axis}_revs"] += 1
                    elif delta_raw > 180:
                        self.pos_dict[f"{axis}_revs"] -= 1

                    self.pos_dict[f"{axis}_pos"] = current_raw - self.pos_dict[f"{axis}_offset"] + (self.pos_dict[f"{axis}_revs"] * 360)

                # Drive motors based on targets/jogs
                for axis, motor in self.motors.items():
                    if self.is_homing:
                        break
                    target = self.targets[axis]
                    jog = self.jogs[axis]
                    pos = self.pos_dict[f"{axis}_pos"]

                    # Check limits (motor degrees)
                    limit_min = self.limits[axis][0] * self.gear_ratios[axis]
                    limit_max = self.limits[axis][1] * self.gear_ratios[axis]

                    if target is not None:
                        error = target - pos
                        abs_err = abs(error)

                        # Deadband hysteresis check: avoid hunting when settled around target
                        if self.target_settled[axis]:
                            if abs_err <= self.TOLERANCE_DEG + self.HYSTERESIS_DEG:
                                continue
                            else:
                                self.target_settled[axis] = False

                        if abs_err <= self.TOLERANCE_DEG:
                            motor.coast()
                            self.targets[axis] = None
                            self.target_settled[axis] = True
                            self.last_sent_pwm[axis] = None
                            self._reset_stall_state(axis, pos=pos)
                        else:
                            # Check stall
                            command = ('target', round(target, 3))
                            if self._is_stalled(axis, command, pos):
                                self._stop_stalled_axis(axis, motor, pos, command)
                                continue

                            speed_sign = 1.0 if error > 0 else -1.0
                            max_pwm = self.current_pwm[axis]["pos"] if speed_sign > 0 else abs(self.current_pwm[axis]["neg"])

                            # Proportional deceleration ramp
                            if abs_err < self.DECEL_THRESHOLD_DEG:
                                factor = (abs_err - self.TOLERANCE_DEG) / max(0.1, self.DECEL_THRESHOLD_DEG - self.TOLERANCE_DEG)
                                factor = max(0.0, min(1.0, factor))
                                effective_pwm = self.MIN_PWM + factor * (max_pwm - self.MIN_PWM)
                            else:
                                effective_pwm = max_pwm

                            pwm_cmd = speed_sign * effective_pwm

                            # Limit bounds check (bypassed in calibration mode)
                            if self.is_calibrating or (speed_sign > 0 and pos < limit_max) or (speed_sign < 0 and pos > limit_min):
                                # Deduplicate commands to prevent flooding serial at 100Hz
                                last_pwm = self.last_sent_pwm[axis]
                                if last_pwm is None or abs(last_pwm - pwm_cmd) > 0.02 or (last_pwm * pwm_cmd <= 0):
                                    motor.pwm(pwm_cmd)
                                    self.last_sent_pwm[axis] = pwm_cmd
                            else:
                                motor.coast()
                                self.targets[axis] = None
                                self.target_settled[axis] = True
                                self.last_sent_pwm[axis] = None
                                self._reset_stall_state(axis, pos=pos)
                    elif jog != 0.0:
                        # Continuous jog drive
                        speed_sign = 1.0 if jog > 0 else -1.0
                        
                        # Check stall
                        command = ('jog', speed_sign, round(self.jog_scales[axis], 3))
                        if self._is_stalled(axis, command, pos):
                            self._stop_stalled_axis(axis, motor, pos, command)
                            continue

                        max_pwm = self.default_pwm[axis]["pos"] if speed_sign > 0 else abs(self.default_pwm[axis]["neg"])
                        pwm_scale = abs(jog) * self.jog_scales[axis]
                        pwm_cmd = speed_sign * max_pwm * pwm_scale
                        
                        if self.is_calibrating or (speed_sign > 0 and pos < limit_max) or (speed_sign < 0 and pos > limit_min):
                            last_pwm = self.last_sent_pwm[axis]
                            if last_pwm is None or abs(last_pwm - pwm_cmd) > 0.02 or (last_pwm * pwm_cmd <= 0):
                                motor.pwm(pwm_cmd)
                                self.last_sent_pwm[axis] = pwm_cmd
                        else:
                            motor.coast()
                            self.jogs[axis] = 0.0
                            self.last_sent_pwm[axis] = None
                            self._reset_stall_state(axis, pos=pos)
                    else:
                        if self.last_sent_pwm[axis] is not None:
                            motor.coast()
                            self.last_sent_pwm[axis] = None
                        self._reset_stall_state(axis, pos=pos)

            time.sleep(0.01)

    def get_joint_angles(self) -> Dict[str, float]:
        return {axis: self.pos_dict[f"{axis}_pos"] / self.gear_ratios[axis] for axis in ["A", "B", "C"]}

    def get_motor_positions(self) -> Dict[str, float]:
        return {axis: self.pos_dict[f"{axis}_pos"] for axis in ["A", "B", "C"]}

    def get_speeds(self) -> Dict[str, float]:
        speeds = {}
        for axis in ["A", "B", "C"]:
            if self.jogs[axis] != 0.0:
                speeds[axis] = abs(self.jogs[axis])
            elif self.targets[axis] is not None:
                speeds[axis] = abs(self.default_pwm[axis]["pos"])
            else:
                speeds[axis] = 0.0
        return speeds

    def get_targets(self) -> Dict[str, Optional[float]]:
        return {axis: (self.targets[axis] / self.gear_ratios[axis] if self.targets[axis] is not None else None) for axis in ["A", "B", "C"]}

    def get_end_effector_position(self) -> Dict[str, float]:
        if not self.has_kinematics:
            return {"x": 0.0, "y": 0.0, "z": 0.0}

        try:
            solver = self._get_ik_solver()
            angles = self.get_joint_angles()
            q_deg = [
                angles['C'] + self.offsets['C'],
                angles['B'] + self.offsets['B'],
                angles['A'] + self.offsets['A']
            ]
            pos = solver.get_current_pos(q_deg)
            return {
                "x": round(float(pos[0]), 4),
                "y": round(float(pos[1]), 4),
                "z": round(float(pos[2]), 4)
            }
        except Exception:
            return {"x": 0.0, "y": 0.0, "z": 0.0}

    def set_pwm(self, axis: str, speed: Optional[float] = None):
        axis = axis.upper()
        if speed is None:
            self.current_pwm[axis] = self.default_pwm[axis].copy()
            return

        speed = float(speed)
        if abs(speed) <= 1.0:
            pos_sign = 1.0 if self.default_pwm[axis]['pos'] >= 0 else -1.0
            neg_sign = 1.0 if self.default_pwm[axis]['neg'] >= 0 else -1.0
            self.current_pwm[axis]['pos'] = pos_sign * abs(speed)
            self.current_pwm[axis]['neg'] = neg_sign * abs(speed)

    def set_target(self, axis: str, degree: float, speed: Optional[float] = None, pwm_scale: Optional[float] = None, relative: bool = False) -> bool:
        axis = axis.upper()
        if self.pwm_blocked or self.is_homing:
            logger.warning("Movement command rejected: PWM blocked or arm is homing.")
            return False

        if relative:
            degree = self.get_joint_angles()[axis] + degree

        if pwm_scale is not None:
            scale = max(0.0, min(1.0, float(pwm_scale)))
            self.current_pwm[axis]['pos'] = self.default_pwm[axis]['pos'] * scale
            self.current_pwm[axis]['neg'] = self.default_pwm[axis]['neg'] * scale
        else:
            self.set_pwm(axis, speed)

        if axis in self.targets:
            if not self.is_calibrating:
                limit_min, limit_max = self.limits[axis]
                if degree < (limit_min - 1e-3) or degree > (limit_max + 1e-3):
                    logger.warning(f"Target degree {degree} exceeds limit bounds.")
                    return False

            target_motor_deg = degree * self.gear_ratios[axis]
            current_pos_deg = self.pos_dict[f"{axis}_pos"]
            if self.target_settled[axis] and abs(target_motor_deg - current_pos_deg) <= (self.TOLERANCE_DEG + self.HYSTERESIS_DEG):
                # Within hysteresis band of settled target; do not re-trigger drive
                self.targets[axis] = None
                return True

            self.targets[axis] = target_motor_deg
            self.target_settled[axis] = False
            self.last_sent_pwm[axis] = None
            self.jogs[axis] = 0.0
            self._reset_stall_state(axis)
            return True
        return False

    def set_jog(self, axis: str, amplitude: float, scale: float = 1.0) -> bool:
        axis = axis.upper()
        if self.pwm_blocked or self.is_homing:
            logger.warning("Jog command rejected: PWM blocked or arm is homing.")
            return False

        if axis in self.jogs:
            multiplier = float(self.directions.get(axis, 1.0))
            if multiplier not in [1.0, -1.0]:
                multiplier = 1.0
            self.jogs[axis] = max(-1.0, min(1.0, float(amplitude) * multiplier))
            self.jog_scales[axis] = max(0.0, min(1.0, float(scale)))
            self.targets[axis] = None
            self.target_settled[axis] = False
            return True
        return False

    def stop_all(self):
        self.pwm_blocked = True
        for axis, motor in self.motors.items():
            self.targets[axis] = None
            self.jogs[axis] = 0.0
            self.jog_scales[axis] = 1.0
            self.current_pwm[axis] = self.default_pwm[axis].copy()
            self._reset_stall_state(axis)
            try:
                motor.pwm(0.0)
            except Exception as e:
                logger.error(f"Error setting pwm to 0 on motor {axis}: {e}")
            try:
                motor.coast()
            except Exception as e:
                logger.error(f"Error coasting motor {axis}: {e}")

    def unblock_pwm(self):
        self.pwm_blocked = False
        for axis in ["A", "B", "C"]:
            self.targets[axis] = None
            self.jogs[axis] = 0.0
            self.jog_scales[axis] = 1.0
            self.current_pwm[axis] = self.default_pwm[axis].copy()
            self._reset_stall_state(axis)

    def set_zero(self):
        for axis, motor in self.motors.items():
            self.pos_dict[f"{axis}_offset"] = motor.get_aposition()
            self.pos_dict[f"{axis}_pos"] = 0.0
            self.pos_dict[f"{axis}_revs"] = 0
            self.targets[axis] = None
            self.jogs[axis] = 0.0
        logger.info("Calibration zero applied successfully.")

    def go_zero(self, speed: Optional[float] = None):
        for axis in ["A", "B", "C"]:
            self.set_target(axis, 0.0, speed)

    def go_absolute_zero(self) -> tuple[bool, str]:
        if getattr(self, 'is_homing', False):
            logger.warning("Homing request rejected: Arm is already actively homing.")
            return False, "Hardware Error: Arm is already homing."
        
        self.is_homing = True
        try:
            logger.info("Driving absolute zero calibration recovery.")
            if hasattr(self, 'session_home_ee'):
                diff_base = self.session_home_base - self.motor_base.get_position()
                diff_vert = self.session_home_vert - self.motor_vert.get_position()
                diff_ee = self.session_home_ee - self.motor_ee.get_position()

                self.motor_base.run_for_degrees(diff_base, speed=15, blocking=False)
                self.motor_vert.run_for_degrees(diff_vert, speed=15, blocking=False)
                self.motor_ee.run_for_degrees(diff_ee, speed=15, blocking=False)

                targets = {
                    "C": self.session_home_base,
                    "B": self.session_home_vert,
                    "A": self.session_home_ee
                }
            else:
                targets = {
                    "C": self.absolute_offsets.get("C", 0),
                    "B": self.absolute_offsets.get("B", 0),
                    "A": self.absolute_offsets.get("A", 0)
                }
                for axis, target_pos in targets.items():
                    self.motors[axis].run_to_position(target_pos, speed=15, direction="shortest", blocking=False)

            start_time = time.monotonic()
            last_pos = {axis: motor.get_position() for axis, motor in self.motors.items()}
            last_progress_time = {axis: start_time for axis in self.motors.keys()}
            settled = {axis: False for axis in self.motors.keys()}

            while not all(settled.values()):
                now = time.monotonic()
                if now - start_time > 8.0:
                    logger.warning("Absolute zero recovery timed out after 8.0s. Coasting motors.")
                    break

                for axis, motor in self.motors.items():
                    if settled[axis]:
                        continue
                    current_pos = motor.get_position()
                    if hasattr(self, 'session_home_ee'):
                        err = abs(current_pos - targets[axis])
                    else:
                        err = abs(motor.get_aposition() - targets[axis])

                    if err <= 8.0:
                        settled[axis] = True
                        try:
                            motor.coast()
                        except Exception:
                            pass
                    else:
                        if abs(current_pos - last_pos[axis]) >= 0.5:
                            last_pos[axis] = current_pos
                            last_progress_time[axis] = now
                        elif now - last_progress_time[axis] > 1.5:
                            logger.warning(f"Axis {axis} stalled during absolute zero recovery at {current_pos:.1f}. Coasting.")
                            settled[axis] = True
                            try:
                                motor.coast()
                            except Exception:
                                pass

                time.sleep(0.05)

            if not hasattr(self, 'session_home_ee'):
                self.session_home_base = self.motor_base.get_position()
                self.session_home_vert = self.motor_vert.get_position()
                self.session_home_ee = self.motor_ee.get_position()

            # Set current values as new offsets
            for axis, motor in self.motors.items():
                self.pos_dict[f"{axis}_offset"] = self.absolute_offsets.get(axis, 0)
                self.pos_dict[f"{axis}_pos"] = 0.0
                self.pos_dict[f"{axis}_revs"] = 0
                self.targets[axis] = None
                self.jogs[axis] = 0.0

            # Save positions
            self.save_position_data()

            logger.info("Absolute offset hardware zero recovery completed.")
            return True, "Hardware successfully restored to config absolute zero offsets."
        except Exception as e:
            logger.exception("Error during absolute zero recovery:")
            return False, f"Failed recovery: {e}"
        finally:
            self.is_homing = False

    def safe_shutdown(self, home_first: bool = False):
        logger.info(f"Initiating safe shutdown (home_first={home_first}). First stopping all motors.")
        self.stop_all()
        
        if home_first:
            logger.info("Running homing sequence before shutdown.")
            self.pwm_blocked = False
            self.go_absolute_zero()
            
        self.stop_all()
        self.running = False
        self.save_position_data()
        logger.info("Driver loop shutdown complete.")

    def apply_joint_delta_command(self, joint_deltas_deg: Sequence[float], pwm_scale: Optional[float] = None) -> tuple[bool, str]:
        if self.pwm_blocked or self.is_homing:
            return False, "Hardware Error: PWM is blocked or arm is homing."

        if len(joint_deltas_deg) != 3:
            return False, "Hardware Error: Expected three joint deltas for axes A, B, and C."

        current_angles = self.get_joint_angles()
        target_angles = {
            axis: current_angles[axis] + float(joint_deltas_deg[idx])
            for idx, axis in enumerate(["A", "B", "C"])
        }

        for axis, target_angle in target_angles.items():
            limit_min, limit_max = self.limits[axis]
            if target_angle < (limit_min - 1e-3) or target_angle > (limit_max + 1e-3):
                return (
                    False,
                    f"Hardware Error: IK target {axis}={target_angle:.3f}° exceeds joint limits "
                    f"({limit_min:.3f}°, {limit_max:.3f}°)."
                )

        for axis, target_angle in target_angles.items():
            if not self.set_target(axis, target_angle, pwm_scale=pwm_scale):
                return False, f"Hardware Error: Could not set IK target for joint {axis}."

        return True, f"Hardware: IK joint delta command accepted. Targets: {target_angles}"

    def _get_ik_solver(self):
        if self.ik_solver is None:
            tolerance = self.config["robot"].get("ik_tolerance_m", 0.015)
            max_iters = self.config["robot"].get("ik_max_iterations", 150)
            self.ik_solver = PinocchioKinematics(
                self.urdf_file,
                offsets=self.offsets,
                limits=self.limits,
                tolerance_m=tolerance,
                max_iterations=max_iters,
            )
        return self.ik_solver

    def move_end_effector_to(
        self, target_xyz: Sequence[float], pwm_scale: Optional[float] = None, relative: bool = False
    ) -> tuple[bool, str]:
        if self.pwm_blocked or self.is_homing:
            return False, "Hardware Error: PWM is blocked or arm is homing."
        try:
            target_xyz = [float(x) for x in target_xyz]
            if len(target_xyz) != 3:
                raise ValueError
        except (TypeError, ValueError):
            return False, "Hardware Error: Target XYZ must be 3 numeric coordinates."

        try:
            current = self.get_joint_angles()
            success, solved, err = self._get_ik_solver().solve_ik_iterative(current, target_xyz, absolute=not relative)
            if not success:
                return False, f"Hardware Error: {err}"

            deltas = [solved[axis] - current[axis] for axis in ["A", "B", "C"]]
            return self.apply_joint_delta_command(deltas, pwm_scale=pwm_scale)
        except Exception as e:
            logger.exception("Failed to calculate IK movement:")
            return False, f"Hardware Error: Failed to calculate IK movement: {e}"

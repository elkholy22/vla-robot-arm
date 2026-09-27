"""
Manual recording for Octo using velocity control.

Forward kinematics are computed during recording. 
Recorded steps therefore include end-effector positions.

Recorded:
- motor positions (calibrated joint angles)
- joint angles
- end-effector position (if kinematics available)
- timestamps
- RGB images
- optional motor velocities
- target_positions (current target joint positions)

Dataset builder behavior:
- It now computes deltas from recorded EE positions: delta = ee_pos[t+1] - ee_pos[t]
- It does NOT run forward kinematics itself anymore.

The saved training action therefore becomes the delta between successive
recorded end-effector positions.
"""

from pi.pi_recorder import PiDataRecorder
from pi.hw import PiConfiguration, HardwareManager
from shared.classes import RobotState, RobotCommand, GoalMessage, SystemConfigMessage
import argparse
import os
import sys
import threading
import time
from inputs import get_gamepad

try:
    import pinocchio as pin
    import numpy as np
except Exception:
    pin = None
    np = None

# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


COMMAND_RATE_HZ = 10
COMMAND_INTERVAL = 1.0 / COMMAND_RATE_HZ

DEADZONE_THRESHOLD = 4000
INPUT_SMOOTHING = 0.2
DEBUG_PRINT_HZ = 5

MAX_MOTOR_SPEED = {
    "A": 20,
    "B": 20,
    "C": 40,
}

running = True
recording = False

# Goal text management: default and current (can be updated via CLI on record)
default_goal_text = "flip the switch to the green side"
current_goal_text = default_goal_text

controller_state = {
    "lx": 0,
    "ly": 0,
    "ry": 0,
}

axis_map = {
    "A": "ry",
    "B": "ly",
    "C": "lx",
}

smoothed_input = {
    "A": 0.0,
    "B": 0.0,
    "C": 0.0,
}

motors = None
cameras = None
recorder = None
hw_manager = None

# Pinocchio kinematics objects (optional)
pin_model = None
pin_data = None
ee_frame_id = None
idx_j1 = None
idx_j2 = None
idx_j3 = None
has_kinematics = False


def normalize(v):
    if v < 0:
        return v / 32768.0
    return v / 32767.0


def apply_deadzone(v):
    if abs(v) < DEADZONE_THRESHOLD:
        return 0
    return v


def stop_all_motors():
    if motors:
        for m in motors.values():
            m.stop()


def gamepad_thread():
    global running
    global recording
    global current_goal_text, default_goal_text

    while running:
        events = get_gamepad()

        for event in events:
            if event.code == "ABS_X":
                controller_state["lx"] = event.state

            elif event.code == "ABS_Y":
                controller_state["ly"] = -event.state

            elif event.code == "ABS_RY":
                controller_state["ry"] = -event.state

            elif event.code == "BTN_TR":
                if event.state == 1:
                    # Prompt CLI for a goal text when starting a recording
                    try:
                        prompt = f"Enter goal text (empty = default: '{default_goal_text}'): "
                        user_input = input(prompt)
                        if user_input is None:
                            user_input = ""
                    except EOFError:
                        user_input = ""
                    user_input = user_input.strip()
                    if user_input == "":
                        current_goal_text = default_goal_text
                    else:
                        current_goal_text = user_input

                    recording = True
                    print(f"[RECORDER] START — goal: {current_goal_text}")

            elif event.code == "BTN_TL":
                if event.state == 1:
                    recording = False
                    print("[RECORDER] STOP")

            elif event.code == "BTN_MODE":
                if event.state == 1:
                    running = False


def capture_robot_state():
    if hw_manager:
        # Read raw state from hardware manager, then override motor/joint angles
        state = hw_manager.read_state()

        try:
            angles = hw_manager.get_joint_angles()
            calibrated_angles = [angles.get(j, 0.0) for j in ["A", "B", "C"]]
            state.motor_positions = calibrated_angles
            state.joint_angles = calibrated_angles

            # Compute end-effector position via Pinocchio if available
            if has_kinematics and pin is not None and pin_model is not None:
                q = np.zeros(pin_model.nq)
                q[idx_j1] = np.radians(
                    calibrated_angles[2])  # motor C -> joint1
                q[idx_j2] = np.radians(
                    calibrated_angles[1])  # motor B -> joint2
                q[idx_j3] = np.radians(
                    calibrated_angles[0])  # motor A -> joint3
                pin.forwardKinematics(pin_model, pin_data, q)
                pin.updateFramePlacements(pin_model, pin_data)
                ee_placement = pin_data.oMf[ee_frame_id]
                state.ee_position = [float(ee_placement.translation[0]), float(
                    ee_placement.translation[1]), float(ee_placement.translation[2])]
        except Exception:
            pass

        return state

    positions = []

    frames = []

    import cv2

    if len(cameras) > 0 and cameras[0]:
        ret, frame = cameras[0].read()
        if ret:
            _, enc = cv2.imencode('.jpg', frame)
            frames.append(enc)
        else:
            frames.append(None)

    if len(cameras) > 1 and cameras[1]:
        try:
            frame = cameras[1].capture_array()
            _, enc = cv2.imencode('.jpg', frame)
            frames.append(enc)
        except Exception:
            frames.append(None)

    return RobotState(
        motor_positions=positions,
        camera_frames=frames,
        timestamp=time.time()
    )


def control_loop(goal_text: str, task_id: str):
    global running
    global recording

    sys_config = SystemConfigMessage(
        urdf_xml_content=PiConfiguration().read_urdf(),
        motor_limits={},
        motor_port_mapping={},
        # control_frequency_hz=COMMAND_RATE_HZ,
    )

    # `GoalMessage` will be created when a recording episode starts using
    # the current `current_goal_text` value (which can be updated via CLI).

    current_speed = {
        "A": 0,
        "B": 0,
        "C": 0,
    }

    last_print = time.time()
    recording_active = False
    last_log_time = 0.0

    while running:

        if recording and not recording_active:
            # Build GoalMessage with the latest CLI-provided goal text
            goal_msg = GoalMessage(
                text_prompt=current_goal_text,
                goal_image=[],
                task_id=task_id,
                is_update=False,
            )
            recorder.start_episode(goal_msg, sys_config)
            recording_active = True

        elif not recording and recording_active:
            recorder.end_episode()
            recording_active = False

        normalized_input = {}

        for motor, axis in axis_map.items():
            val = controller_state[axis]
            val = apply_deadzone(val)
            val = normalize(val)
            normalized_input[motor] = val

        curved_input = {}

        for motor, val in normalized_input.items():
            curved_input[motor] = val ** 3

        for motor, val in curved_input.items():
            smoothed_input[motor] = (
                (1.0 - INPUT_SMOOTHING) * smoothed_input[motor]
                + INPUT_SMOOTHING * val
            )

        target_speed = {}

        for motor, val in smoothed_input.items():
            target_speed[motor] = int(val * MAX_MOTOR_SPEED[motor])

        for motor, speed in target_speed.items():

            if speed != current_speed[motor]:
                current_speed[motor] = speed

                if abs(speed) <= 3:
                    motors[motor].stop()
                else:
                    motors[motor].start(speed)

        if recording:
            now_time = time.time()
            # Log at 10 Hz
            if now_time - last_log_time >= 0.1:
                state = capture_robot_state()

                # Build target_positions in the same format as manual.py: list of position sets
                try:
                    if hw_manager:
                        ja = hw_manager.get_joint_angles()
                        calibrated_positions = [
                            ja.get(n, 0.0) for n in ["A", "B", "C"]]
                        target_positions = [calibrated_positions]
                    else:
                        target_positions = []
                except Exception:
                    target_positions = []

                cmd = RobotCommand(
                    target_velocities=[
                        target_speed["A"],
                        target_speed["B"],
                        target_speed["C"],
                    ],
                    target_positions=target_positions,
                    gripper_open=[False],
                    halt_flag=False,
                    timestamp=now_time,
                )

                try:
                    recorder.log_step(state, cmd)
                except Exception as e:
                    print(f"[RECORDER] Failed to log step: {e}")

                last_log_time = now_time

        now = time.time()

        if now - last_print >= 1 / DEBUG_PRINT_HZ:
            status = "[REC]" if recording else "[   ]"

            print(
                f"{status} "
                f"A={current_speed['A']} "
                f"B={current_speed['B']} "
                f"C={current_speed['C']}"
            )

            last_print = now

        time.sleep(COMMAND_INTERVAL)

    stop_all_motors()

    if recording_active:
        recorder.end_episode()


def main():
    global motors
    global cameras
    global recorder
    global hw_manager
    global pin_model, pin_data, ee_frame_id, idx_j1, idx_j2, idx_j3, has_kinematics
    global default_goal_text, current_goal_text

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--goal-text",
        type=str,
        default="flip the switch to the green side"
    )

    parser.add_argument(
        "--task-id",
        type=str,
        default="manual_velocity_task"
    )

    args = parser.parse_args()

    config = PiConfiguration()

    # Initialize default/current goal text from CLI
    default_goal_text = args.goal_text
    current_goal_text = default_goal_text

    hw_manager = HardwareManager(config)
    hw_manager.initialise_hardware()

    # Initialize Pinocchio kinematics if available
    if pin is not None:
        try:
            # Resolve URDF path similar to PiConfiguration.read_urdf
            folder_dir = os.path.dirname(os.path.abspath(__file__))
            full_urdf_path = config.local_urdf_path
            if not os.path.isabs(full_urdf_path):
                full_urdf_path = os.path.abspath(
                    os.path.join(folder_dir, full_urdf_path))

            if os.path.exists(full_urdf_path):
                pin_model = pin.buildModelFromUrdf(full_urdf_path)
                pin_data = pin_model.createData()
                ee_frame_id = pin_model.getFrameId('end_effector')
                id_j1 = pin_model.getJointId('joint1')
                id_j2 = pin_model.getJointId('joint2')
                id_j3 = pin_model.getJointId('joint3')
                idx_j1 = pin_model.joints[id_j1].idx_q
                idx_j2 = pin_model.joints[id_j2].idx_q
                idx_j3 = pin_model.joints[id_j3].idx_q
                has_kinematics = True
                print(
                    f"[Kinematics] URDF loaded for recording from {full_urdf_path}")
            else:
                print(f"[Kinematics] URDF not found at {full_urdf_path}")
        except Exception as e:
            print(f"[Kinematics] Failed to initialize Pinocchio: {e}")

    motors = hw_manager.motors
    cameras = hw_manager.cameras

    recorder = PiDataRecorder(save_dir=config.data_save_path)

    threading.Thread(target=gamepad_thread, daemon=True).start()

    try:
        control_loop(args.goal_text, args.task_id)

    finally:
        stop_all_motors()
        print("Shutdown complete")


if __name__ == "__main__":
    main()

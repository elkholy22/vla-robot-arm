from buildhat import Motor
from inputs import get_gamepad
import time
import threading

COMMAND_RATE_HZ = 30    # commands per second
COMMAND_INTERVAL = 1.0 / COMMAND_RATE_HZ
DEADZONE_THRESHOLD = 4000
DEBUG_PRINT_HZ = 5

MAX_MOTOR_SPEED = {     # degrees per second
    "A": 20,
    "B": 20,
    "C": 40
}

""" MAX_MOTOR_ANGLES = {
    "A": (-45, 45),
    "B": (-45, 45)
} """

INPUT_SMOOTHING = 0.2   # 1.0 = no smoothing, 0.0 = no update

motors = {
    "A": Motor("A"),
    "B": Motor("B"),
    "C": Motor("C")
}

running = True
reset = False

# Current controller joystick position
controller_state = {
    "ry": 0,    # right joystick vertical (motor A, end-effector)
    "ly": 0,    # left joystick vertical (motor B, elbow joint)
    "lx": 0     # left joystick horizontal (motor C, shoulder joint)
}

axis_map = {
    "A": "ry",
    "B": "ly",
    "C": "lx"
}

# Smoothed controller value
smoothed_input = {
    "A": 0.0,
    "B": 0.0,
    "C": 0.0
}

def normalize(value):
    if value < 0:
        return value / 32768.0
    else:
        return value / 32767.0

def apply_deadzone(value):
    if abs(value) < DEADZONE_THRESHOLD:
        return 0
    else:
        return value
    
""" def is_in_bounds(motor):
    (low, high) = MAX_MOTOR_ANGLES.get(motor)
    pos = motors.get[motor].get_aposition
    if pos <= low or pos >= high:
        return False
    else:
        return True """

def stop_all_motors():
    for motor in motors.values():
        motor.stop()

def reset_all_motors():
    stop_all_motors()

    time.sleep(0.2)

    motors["C"].run_to_position(90, speed=10)
    motors["B"].run_to_position(0, speed=10)
    motors["A"].run_to_position(-120, speed=10)

    time.sleep(1)

def gamepad_thread():
    global running
    global reset
    global controller_state

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
                        reset = True
                elif event.code == "BTN_TL":
                    if event.state == 1:
                        running = False

def control_loop():
    global running
    global reset
    global smoothed_input
    
    last_print = time.time()

    current_speed = {
        "A": 0,
        "B": 0,
        "C": 0
    }

    while running:
        if reset:
            reset_all_motors()
            print("============ RESET ============")
            reset = False

        normalized_input = {}
        for motor, axis in axis_map.items():
            value = controller_state[axis]
            value = apply_deadzone(value)
            value = normalize(value)
            normalized_input[motor] = value

        curved_input = {}
        for motor, value in normalized_input.items():
            curved_input[motor] = value ** 3

        for motor, value in curved_input.items():
            smoothed_input[motor] = (
                (1.0 - INPUT_SMOOTHING)
                * smoothed_input[motor]
                + INPUT_SMOOTHING
                * value
            )

        target_speed = {}
        for motor, value in smoothed_input.items():
            target_speed[motor] = int(value * MAX_MOTOR_SPEED[motor])

        for motor, speed in target_speed.items():
            if speed != current_speed[motor]:
                current_speed[motor] = speed
                """ if abs(speed) <= 1 or not is_in_bounds(motor): """
                if abs(speed) <= 3:
                    motors[motor].stop()                
                else:
                    motors[motor].start(speed)

        current_time = time.time()

        if (current_time - last_print >= 1 / DEBUG_PRINT_HZ):
            print(
                " | ".join(
                    f"{motor}: "
                    f"input={normalized_input[motor]:.2f} "
                    f"speed={current_speed[motor]}"
                    for motor in ["A", "B", "C"]
                )
            )
            last_print = current_time

        time.sleep(COMMAND_INTERVAL)

    stop_all_motors()

try:
    # Start Threads
    threading.Thread(
        target=gamepad_thread,
        daemon=True
    ).start()

    control_loop()
finally:
    stop_all_motors()
    
    print("============ STOP ============")
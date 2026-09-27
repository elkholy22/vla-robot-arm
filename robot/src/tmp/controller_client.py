import asyncio
import websockets
from inputs import get_gamepad
import threading
import time
import json

POSITION_UPDATE_RATE_HZ = 10     # updates to target positions per second
POSITION_UPDATE_INTERVAL = 1.0 / POSITION_UPDATE_RATE_HZ
POSITION_SEND_RATE_HZ = 0.5
POSITION_SEND_INTERVAL = 1.0 / POSITION_UPDATE_RATE_HZ
DEADZONE_THRESHOLD = 0
INPUT_SMOOTHING = 0.8   # 1.0 = no smoothing, 0.0 = no update

state_lock = threading.Lock()
running = threading.Event()
running.set()
reset = threading.Event()
calibrate = threading.Event()

MAX_MOTOR_SPEED = {     # degrees per second
    "A": 40,
    "B": 40,
    "C": 60
}

GEAR_RATIOS = {
    "A": 5,
    "B": 5,
    "C": 7
}

""" MAX_MOTOR_ANGLES = {
    "A": (-85 * GEAR_RATIOS["A"], 85 * GEAR_RATIOS["A"]),
    "B": (-85 * GEAR_RATIOS["B"], 50 * GEAR_RATIOS["B"]),
    "C": (-180 * GEAR_RATIOS["C"], 180 * GEAR_RATIOS["C"])
} """

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

home_angles = {"A": 0.0, "B": 0.0, "C": 0.0}

motor_limits = {"A": [-85 * GEAR_RATIOS["A"], 85 * GEAR_RATIOS["A"]],
                "B": [-85 * GEAR_RATIOS["B"], 50 * GEAR_RATIOS["B"]],
                "C": [-180 * GEAR_RATIOS["C"], 180 * GEAR_RATIOS["C"]]}

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
    
def validate_position(motor, target):
    low = motor_limits[motor][0]
    high = motor_limits[motor][1]

    return max(low, min(high, target))

# Converts motor limits from joint angles to motor angles
def convert_motor_limits():
    global motor_limits

    motor_limits = {
        motor: [
            lims[0] * GEAR_RATIOS[motor] + home_angles[motor],
            lims[1] * GEAR_RATIOS[motor] + home_angles[motor]
        ]
        for motor, lims in motor_limits.items()
    }

def gamepad_thread():
    global running
    global reset
    global controller_state
    global calibrate

    while running.is_set():
        events = get_gamepad()

        # state_lock mutexfor writing controller state
        for event in events:
                if event.code == "ABS_X":
                    with state_lock:
                        controller_state["lx"] = event.state
                elif event.code == "ABS_Y":
                    with state_lock:
                        controller_state["ly"] = -event.state
                elif event.code == "ABS_RY":
                    with state_lock:
                        controller_state["ry"] = -event.state
                elif event.code == "BTN_EAST":      # B (calibrate)
                    with state_lock:
                        calibrate.set()
                elif event.code == "BTN_TR":        # Right Bumper (reset)
                    if event.state == 1:
                        reset.set()
                elif event.code == "BTN_TL":        # Left Bumper (stop)
                    if event.state == 1:
                        running.clear()

async def control_loop():
    global running
    global reset
    global home_angles
    global motor_limits

    last_calc_time = time.monotonic()

    smoothed_input = {motor: 0.0 for motor in axis_map.keys()}
    target_position = {motor: 0.0 for motor in axis_map.keys()}

    async with websockets.connect(
        "ws://10.217.217.181:9000/ws"
    ) as ws:
        try:
            # Receive initial state (home angles and motor limits) from server
            data_json = await ws.recv() 
            data = json.loads(data_json)
            # For start-up: use received current angles as mock home angles
            angles = data["angles"]
            home_angles.update(angles)
            # Use received motor limits as maximum angles
            limits = data["limits"]
            motor_limits.update(limits)
            # json data consists of joint angles --> convert to motor limits relative to home position
            convert_motor_limits()

            last_send_time = 0

            while running.is_set():
                    current_calc_time = time.monotonic()
                    dt = current_calc_time - last_calc_time
                    last_calc_time = current_calc_time

                    dt = min(dt, 0.1)       # restrict time delta to avoid sudden jumps

                    if reset.is_set():
                        await ws.send("zero")
                        reset.clear()

                    if calibrate.is_set():
                        await ws.send("home")
                        data_json = await ws.recv()
                        data = json.loads(data_json)
                        home_angles_json = data["home_angles"]
                        home_angles.update(zip(home_angles, home_angles_json))
                        convert_motor_limits()
                        calibrate.clear()

                    # state_lock mutex for reading controller state
                    with state_lock:
                        current_values = controller_state.copy()

                    normalized_input = {}
                    for motor, axis in axis_map.items():
                        value = current_values[axis]
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

                    # calculate target positions and make sure target positions don't surpass angle limits
                    for motor in target_speed.keys():
                        target_position[motor] += target_speed[motor] * dt      # integrate speed to get position
                        target_position[motor] = validate_position(motor, target_position[motor])

                    print(f"Target pos: {target_position}")

                    if current_calc_time - last_send_time >= POSITION_SEND_INTERVAL:
                        for motor, pos in target_position.items():
                            await ws.send(f"move {motor} {pos} {target_speed[motor]}")
                        last_send_time = current_calc_time
                        
                    await asyncio.sleep(POSITION_UPDATE_INTERVAL)
        finally:  
            await ws.send("stop")

# start gamepad thread
t = threading.Thread(
    target=gamepad_thread,
    daemon=False
)
t.start()

try:
    # start communication thread
    asyncio.run(control_loop())
except KeyboardInterrupt:
    # stop program via CTRL + C
    running.clear()
finally:
    # join threads
    t.join(timeout=1.0)
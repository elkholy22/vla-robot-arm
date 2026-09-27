import asyncio
import websockets
from inputs import get_gamepad
import threading
import time

POSITION_UPDATE_RATE_HZ = 10     # updates to target positions per second
POSITION_UPDATE_INTERVAL = 1.0 / POSITION_UPDATE_RATE_HZ
DEADZONE_THRESHOLD = 0
INPUT_SMOOTHING = 0.5   # 1.0 = no smoothing, 0.0 = no update

state_lock = threading.Lock()
running = threading.Event()
running.set()
reset = threading.Event()

MAX_MOTOR_SPEED = {     # degrees per second
    "A": 20,
    "B": 20,
    "C": 40
}

MAX_MOTOR_ANGLES = {
    "A": (-85, 85),
    "B": (-85, 50),
    "C": (-180, 180)
}

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
    low = MAX_MOTOR_ANGLES[motor][0]
    high = MAX_MOTOR_ANGLES[motor][1]

    return max(low, min(high, target))

def gamepad_thread():
    global running
    global reset
    global controller_state

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
                elif event.code == "BTN_BR":
                    # BTN_BR toggles recording (maps to backend "capture")
                    if event.state == 1:
                        # set a flag in controller_state so sender can act
                        with state_lock:
                            controller_state.setdefault("capture_press", 0)
                            controller_state["capture_press"] += 1
                elif event.code == "BTN_TR":
                    if event.state == 1:
                        with state_lock:
                            reset.set()
                elif event.code == "BTN_TL":
                    if event.state == 1:
                        running.clear()

async def send_targets():
    global running
    global reset

    last_time = time.monotonic()

    smoothed_input = {motor: 0.0 for motor in axis_map.keys()}
    target_position = {motor: 0.0 for motor in axis_map.keys()}

    async with websockets.connect(
        "ws://127.0.0.1:9000/ws"
    ) as ws:
        try:
            while running.is_set():
                    send_zero = False
                    send_capture = False

                    now = time.monotonic()
                    dt = now - last_time
                    last_time = now

                    dt = min(dt, 0.1)   # restrict time delta to avoid sudden jumps

                    # state_lock mutex for reset
                    if reset.is_set():
                        send_zero = True
                        reset.clear()

                    # state_lock mutex for reading controller state
                    with state_lock:
                        current_values = controller_state.copy()
                        # check capture press counter
                        if current_values.get("capture_press", 0) > 0:
                            send_capture = True
                            # consume presses
                            controller_state["capture_press"] = 0

                    # send zero command separately outside mutex
                    if send_zero:
                        await ws.send("zero")

                    # send capture toggle if requested
                    if send_capture:
                        await ws.send("capture")

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
                        target_position[motor] += target_speed[motor] * dt    # integrate speed to get position
                        target_position[motor] = validate_position(motor, target_position[motor])

                    for motor, pos in target_position.items():
                        await ws.send(f"move {motor} {pos} {target_speed[motor]}")

                    await asyncio.sleep(POSITION_UPDATE_INTERVAL)
        finally:  
            await ws.send("stop")

# start gamepad thread
t = threading.Thread(
    target=gamepad_thread,
    daemon=False
)
t.start()

# start communication thread
asyncio.run(send_targets())

# join threads
t.join()
import atexit
import signal
import json
from buildhat import Motor
import keyboard
import time


motor_a = Motor('A')
motor_b = Motor('B')
motor_c = Motor('C')

zero_a = motor_a.get_position()
zero_b = motor_b.get_position()
zero_c = motor_c.get_position()

target_a = None
target_b = None
target_c = None

stop_a_high = False
stop_a_low = False
stop_b_high = False
stop_b_low = False
stop_c_high = False
stop_c_low = False

HYSTERESIS = 15  # degrees to move away before clearing limit flag

min_a = -5 * 45
max_a = 5 * 45
min_b = -5 * 50
max_b = 5 * 20  # downward limit, important
min_c = -7 * 45  # placeholder limit
max_c = 7 * 45

current_pos_dict = {
    'A_pos': 0,
    'B_pos': 0,
    'C_pos': 0,
    'A_revs': 0,
    'B_revs': 0,
    'C_revs': 0,
    'A_offset': motor_a.get_aposition(),
    'B_offset': motor_b.get_aposition(),
    'C_offset': motor_c.get_aposition()
}

# Saving position on exit:


def save_data(signum=None, frame=None):
    """Save current_pos_dict to JSON on exit or Ctrl+C"""
    try:
        with open('motor_positions.json', 'w') as f:
            json.dump(current_pos_dict, f, indent=2)
        print("\nData saved to motor_positions.json")
    except Exception as e:
        print(f"Error saving: {e}")
    if signum is not None:  # Only exit if called by signal
        exit(0)


# Register handlers
signal.signal(signal.SIGINT, save_data)  # Ctrl+C
atexit.register(save_data)  # Normal exit
###

# Loading the saved position file:
try:
    with open('motor_positions.json', 'r') as f:
        current_pos_dict = json.load(f)
        for axis, motor in [('A', motor_a), ('B', motor_b), ('C', motor_c)]:
            current_pos = motor.get_aposition(
            ) - current_pos_dict[f'{axis}_offset'] + current_pos_dict[f'{axis}_revs'] * 360
            old_pos = current_pos_dict[f'{axis}_pos']
            if abs(current_pos - old_pos) > 30:
                print(
                    f"WARNING: {axis} position jump from {old_pos} to {current_pos}. Check motor position or reset offsets.")
except FileNotFoundError:
    print("No saved position file found. Starting with current motor positions as zero.")


def update_counted_apos_dict(current_pos_dict: dict, set_zero: bool = False):
    for axis, motor in [('A', motor_a), ('B', motor_b), ('C', motor_c)]:
        if set_zero:
            current_pos_dict[f'{axis}_offset'] = motor.get_aposition()
            current_pos_dict[f'{axis}_pos'] = 0
            current_pos_dict[f'{axis}_revs'] = 0
            continue

        current_raw = motor.get_aposition()

        # Reconstruct what the previous raw absolute position was from our stored state
        prev_raw = current_pos_dict[f'{axis}_pos'] + current_pos_dict[f'{axis}_offset'] - (
            current_pos_dict[f'{axis}_revs'] * 360)

        delta_raw = current_raw - prev_raw

        # Track wrap-arounds using raw encoder deltas
        if delta_raw < -180:
            # Wrapped forward (e.g., from 179 to -180 -> delta is ~ -359)
            current_pos_dict[f'{axis}_revs'] += 1
        elif delta_raw > 180:
            # Wrapped backward (e.g., from -179 to 180 -> delta is ~ 359)
            current_pos_dict[f'{axis}_revs'] -= 1

        # Compute final accumulated position
        current_pos_dict[f'{axis}_pos'] = current_raw - \
            current_pos_dict[f'{axis}_offset'] + \
            (current_pos_dict[f'{axis}_revs'] * 360)

    return current_pos_dict


while True:
    current_pos_dict = update_counted_apos_dict(current_pos_dict)

    # Changed from: delta_a = motor_a.get_position() - zero_a
    delta_a = current_pos_dict['A_pos']
    # Changed from: delta_b = motor_b.get_position() - zero_b
    delta_b = current_pos_dict['B_pos']
    # Changed from: delta_c = motor_c.get_position() - zero_c
    delta_c = current_pos_dict['C_pos']

    # Axis A limits with hysteresis
    if delta_a > max_a:
        motor_a.coast()
        stop_a_high = True
    elif delta_a < min_a:
        motor_a.coast()
        stop_a_low = True
    elif stop_a_high and delta_a < max_a - HYSTERESIS:
        stop_a_high = False
    elif stop_a_low and delta_a > min_a + HYSTERESIS:
        stop_a_low = False

    # Axis B limits with hysteresis
    if delta_b > max_b:
        motor_b.coast()
        stop_b_high = True
    elif delta_b < min_b:
        motor_b.coast()
        stop_b_low = True
    elif stop_b_high and delta_b < max_b - HYSTERESIS:
        stop_b_high = False
    elif stop_b_low and delta_b > min_b + HYSTERESIS:
        stop_b_low = False

    # Axis C limits with hysteresis
    if delta_c > max_c:
        motor_c.coast()
        stop_c_high = True
    elif delta_c < min_c:
        motor_c.coast()
        stop_c_low = True
    elif stop_c_high and delta_c < max_c - HYSTERESIS:
        stop_c_high = False
    elif stop_c_low and delta_c > min_c + HYSTERESIS:
        stop_c_low = False

    if keyboard.is_pressed("q") or (target_a is not None and delta_a > target_a):
        if not stop_a_high:
            motor_a.pwm(0.2)
        else:
            motor_a.coast()
    elif keyboard.is_pressed("e") or (target_a is not None and delta_a < target_a):
        if not stop_a_low:
            motor_a.pwm(-0.3)
        else:
            motor_a.coast()
    else:
        motor_a.coast()

    if keyboard.is_pressed("s") or (target_b is not None and delta_b > target_b):
        if not stop_b_high:
            motor_b.pwm(0.2)
        else:
            motor_b.coast()
    elif keyboard.is_pressed("w") or (target_b is not None and delta_b < target_b):
        if not stop_b_low:
            motor_b.pwm(-0.5)
        else:
            motor_b.coast()
    else:
        motor_b.coast()

    if keyboard.is_pressed("d") or (target_c is not None and delta_c > target_c):
        if not stop_c_high:
            motor_c.pwm(0.3)
        else:
            motor_c.coast()
    elif keyboard.is_pressed("a") or (target_c is not None and delta_c < target_c):
        if not stop_c_low:
            motor_c.pwm(-0.3)
        else:
            motor_c.coast()
    else:
        motor_c.coast()

    print("A:", delta_a, "B:", delta_b, "C:", delta_c)
    time.sleep(0.01)

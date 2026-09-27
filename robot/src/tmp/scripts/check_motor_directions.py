import json
import sys
from buildhat import Motor

DEGREES = 20.0
SPEED = 10

AXIS_DESCRIPTIONS = {
    "A": (
        "joint3, +Y axis",
        "Did the end-effector link move UP or DOWN relative to the B link?",
        {"up": -1, "u": -1, "down": 1, "d": 1},
    ),
    "B": (
        "joint2, +Y axis",
        "Did the main arm link move UP or DOWN?",
        {"up": -1, "u": -1, "down": 1, "d": 1},
    ),
    "C": (
        "joint1, +Z axis",
        "Viewed from above, while standing behind the robot and looking along +X, did the arm move LEFT or RIGHT?",
        {"left": 1, "l": 1, "right": -1, "r": -1},
    ),
}

def ask_observed_direction(axis: str) -> int:
    joint_description, question, answers = AXIS_DESCRIPTIONS[axis]
    print(f"\nMotor {axis}: {joint_description}\n{question}")
    while True:
        answer = input("> ").strip().lower()
        if answer in answers:
            return answers[answer]

def test_motor(axis: str, motor) -> int:
    start_position = float(motor.get_position())
    motor.run_for_degrees(DEGREES, speed=SPEED, blocking=True)
    
    direction = ask_observed_direction(axis)
    
    current_position = float(motor.get_position())
    return_delta = start_position - current_position
    motor.run_for_degrees(return_delta, speed=SPEED, blocking=True)
    motor.coast()
    
    return direction

def main() -> int:
    motors = {axis: Motor(axis) for axis in ("A", "B", "C")}
    directions = {}

    for axis in ("A", "B", "C"):
        directions[axis] = test_motor(axis, motors[axis])

    for motor in motors.values():
        motor.coast()

    print("\n" + json.dumps({"directions": directions}, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())

from buildhat import Motor
import json
import time

motor_ee = Motor('A')
motor_vert = Motor('B')
motor_base = Motor('C')

# Release motor holding torque so they can be turned by hand initially
motor_ee.pwm(0)
motor_vert.pwm(0)
motor_base.pwm(0)

print("PHASE 1: ZERO CALIBRATION")
print("The motors are released. Align each joint to its Witness Mark.")

input("1. Align the BASE joint to its Witness Mark. Press ENTER...")
offset_base = motor_base.get_aposition()
motor_base.run_to_position(offset_base, speed=15, direction="shortest")
print("   -> Base locked.")

input("2. Align the VERTICAL joint to its Witness Mark and hold it. Press ENTER...")
offset_vert = motor_vert.get_aposition()
motor_vert.run_to_position(offset_vert, speed=15, direction="shortest")
time.sleep(0.5)
baseline_rel_vert = motor_vert.get_position()
print("   -> Vertical locked.")

input("3. Align the END-EFFECTOR joint to its Witness Mark and hold it. Press ENTER...")
offset_ee = motor_ee.get_aposition()
motor_ee.run_to_position(offset_ee, speed=15, direction="shortest")
time.sleep(0.5)
baseline_rel_ee = motor_ee.get_position()
print("   -> End-Effector locked.")

print(f"\n[Absolute Zeros] EE: {offset_ee}°, Vert: {offset_vert}°, Base: {offset_base}°")
print("The robot is now rigidly locked at the global zero position.")
time.sleep(2) 


print("\nPHASE 2: VERTICAL JOINT LIMITS")
print("Releasing ONLY the Vertical joint. Base and EE remain locked.")
motor_vert.pwm(0)

input("1. Manually push the Vertical joint to its maximum UPPER limit. Press ENTER...")
upper_rel_vert = motor_vert.get_position()
upper_limit_vert = upper_rel_vert - baseline_rel_vert

input("2. Manually push the Vertical joint to its LOWER limit (Worst Case for EE). Press ENTER...")
lower_rel_vert = motor_vert.get_position()
lower_limit_vert = lower_rel_vert - baseline_rel_vert
lower_abs_vert = motor_vert.get_aposition()

# LOCK the vertical joint at this worst-case lower limit
motor_vert.run_to_position(lower_abs_vert, speed=15, direction="shortest")

print(f"[Vertical Limits] Upper: {upper_limit_vert}°, Lower: {lower_limit_vert}°")
print("Vertical joint is now locked at its lowest position to establish a safe EE baseline.")

print("\nPHASE 3: END-EFFECTOR (EE) LIMITS")
print("Releasing ONLY the EE joint.")
motor_ee.pwm(0)

input("1. Manually push the EE joint to its maximum UPPER limit. Press ENTER...")
upper_rel_ee = motor_ee.get_position()
upper_limit_ee = upper_rel_ee - baseline_rel_ee

input("2. Manually push the EE joint to its LOWER limit (Careful with the table/base!). Press ENTER...")
lower_rel_ee = motor_ee.get_position()
lower_limit_ee = lower_rel_ee - baseline_rel_ee

print(f"[EE Limits (Conservative)] Upper: {upper_limit_ee}°, Lower: {lower_limit_ee}°")

print("\nCalibration complete. Releasing all motors to prevent overheating.")
motor_base.pwm(0)
motor_vert.pwm(0)
motor_ee.pwm(0)

print("\nSaving Calibration Data")

calibration_data = {
    "absolute_offsets": {
        "A": offset_ee,
        "B": offset_vert,
        "C": offset_base
    },
    "motor_limits_relative": {
        "A": {
            "lower": lower_limit_ee,
            "upper": upper_limit_ee
        },
        "B": {
            "lower": lower_limit_vert,
            "upper": upper_limit_vert
        }
    }
}

filename = "zero_offsets.json"

try:
    with open(filename, 'w') as f:
        json.dump(calibration_data, f, indent=4)
    print(f"SUCCESS: Offsets and relative limits have been saved to '{filename}'.")
except Exception as e:
    print(f"FAILED to save calibration data: {e}")


print("\nPHASE 4: AUTOMATIC RETURN TO ZERO")
print("Unwinding gear trains back to absolute zero phase...")

return_deg_ee = baseline_rel_ee - motor_ee.get_position()
return_deg_vert = baseline_rel_vert - motor_vert.get_position()

print("   -> Lifting Vertical arm to zero...")
motor_vert.run_for_degrees(return_deg_vert, speed=15)

print("   -> Returning End-Effector to zero...")
motor_ee.run_for_degrees(return_deg_ee, speed=15)

print("Robot is back at global zero phase.")

#Proof of functionality, no longer needed
import json
import time
import os
from buildhat import Motor

class RobotArm:
    def __init__(self, config_file="zero_offsets.json"):
        self.config_file = config_file
        self.offsets = {}
        self.limits = {}
        
        self._load_config()
        
        print("[RobotArm] Initializing motors...")
        self.motor_ee = Motor('A')
        self.motor_vert = Motor('B')
        self.motor_base = Motor('C')
        
        self._lock_to_zero()

    def _load_config(self):
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file '{self.config_file}' not found. Run startup_homing.py first.")
            
        with open(self.config_file, 'r') as f:
            data = json.load(f)
            self.offsets = data.get("absolute_offsets", {})
            self.limits = data.get("motor_limits_relative", {})
            
        print(f"[RobotArm] Loaded zero offsets: {self.offsets}")

    def _lock_to_zero(self):
        print("[RobotArm] Locking to global absolute zero position...")
        
        self.motor_base.run_to_position(self.offsets["C"], speed=15, direction="shortest")
        self.motor_vert.run_to_position(self.offsets["B"], speed=15, direction="shortest")
        self.motor_ee.run_to_position(self.offsets["A"], speed=15, direction="shortest")
        
        time.sleep(1) # Allow settling
        
        self.session_home_ee = self.motor_ee.get_position()
        self.session_home_vert = self.motor_vert.get_position()
        self.session_home_base = self.motor_base.get_position()
        
        print("[RobotArm] Hardware is ready. Relative session baselines established.")

    def safe_shutdown(self):
        print("\n[RobotArm] Shutting down...")

        diff_ee = self.session_home_ee - self.motor_ee.get_position()
        diff_vert = self.session_home_vert - self.motor_vert.get_position()
        diff_base = self.session_home_base - self.motor_base.get_position()
        
        print("[RobotArm] Unwinding to true zero...")
        
        self.motor_ee.run_for_degrees(diff_ee, speed=15)
        self.motor_vert.run_for_degrees(diff_vert, speed=15)
        self.motor_base.run_for_degrees(diff_base, speed=15)
        
        time.sleep(2) 
        
        print("[RobotArm] Releasing motor torque...")
        self.motor_ee.pwm(0)
        self.motor_vert.pwm(0)
        self.motor_base.pwm(0)
        
        print("[RobotArm] Shutdown complete.")

    def get_operational_state(self):
        """This is the only state function the inference model and kinematics should use,
           used to get the relative values of the motors from the zero position during operation"""
        return {
            "A": self.motor_ee.get_position() - self.session_home_ee,
            "B": self.motor_vert.get_position() - self.session_home_vert,
            "C": self.motor_base.get_position() - self.session_home_base
        }

if __name__ == "__main__":
    try:
        print("=== Starting RobotArm Controller Test ===")
        arm = RobotArm()
        
        print("\n[TEST] Robot is now locked at zero.")
        print("[TEST] Press Ctrl+C in this terminal to test the safe shutdown sequence.")
        
        while True:
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n[TEST] KeyboardInterrupt detected! Routing to safe shutdown...")
        arm.safe_shutdown()
        print("=== Test Complete ===")

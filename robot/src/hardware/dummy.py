import time
import threading
from hardware.robot_arm import RobotArm


class DummyMotor:
    def __init__(self, port: str):
        self.port = port
        self.current_angle = 0.0
        self.target_speed = 0.0
        self.last_update = time.time()
        self.lock = threading.Lock()
        self._motion_id = 0

    def _update_position(self):
        with self.lock:
            now = time.time()
            dt = now - self.last_update
            self.last_update = now
            self.current_angle += self.target_speed * dt

    def get_aposition(self) -> float:
        self._update_position()
        with self.lock:
            # Wrap to [-180, 180]
            val = (self.current_angle + 180) % 360 - 180
            return float(val)

    def get_position(self) -> float:
        self._update_position()
        with self.lock:
            return float(self.current_angle)

    def coast(self):
        with self.lock:
            self._motion_id += 1
            self.target_speed = 0.0

    def pwm(self, speed: float):
        with self.lock:
            self._motion_id += 1
            scaled_speed = speed
            if abs(speed) > 1.0:
                scaled_speed = speed / 100.0
            self.target_speed = scaled_speed * 500.0
            self.last_update = time.time()

    def _run_motion(self, start_angle: float, target_angle: float, duration: float, motion_id: int):
        start_time = time.time()
        end_time = start_time + duration
        diff = target_angle - start_angle
        
        while True:
            with self.lock:
                if self._motion_id != motion_id:
                    return
            now = time.time()
            if now >= end_time:
                break
            
            elapsed = now - start_time
            fraction = elapsed / duration
            current = start_angle + diff * fraction
            
            with self.lock:
                self.current_angle = current
                self.last_update = now
                
            time.sleep(0.01)
            
        with self.lock:
            if self._motion_id == motion_id:
                self.current_angle = target_angle
                self.target_speed = 0.0
                self.last_update = time.time()

    def run_to_position(self, pos: float, speed: int = 15, direction: str = "shortest", blocking: bool = True):
        self._update_position()
        with self.lock:
            self._motion_id += 1
            current_id = self._motion_id
            start_angle = self.current_angle
            target_angle = pos
            deg_per_sec = (speed / 100.0) * 500.0 if speed > 0 else 75.0
            diff = target_angle - start_angle
            if diff == 0:
                return
            duration = abs(diff) / deg_per_sec

        if blocking:
            self._run_motion(start_angle, target_angle, duration, current_id)
        else:
            t = threading.Thread(target=self._run_motion, args=(start_angle, target_angle, duration, current_id), daemon=True)
            t.start()

    def run_for_degrees(self, degrees: float, speed: int = 15, blocking: bool = True):
        self._update_position()
        with self.lock:
            target_pos = self.current_angle + degrees
        self.run_to_position(target_pos, speed=speed, blocking=blocking)


class DummyRobotArm(RobotArm):
    def _init_motors(self, motor_ee_port: str, motor_vert_port: str, motor_base_port: str):
        self.motor_ee = DummyMotor(motor_ee_port)
        self.motor_vert = DummyMotor(motor_vert_port)
        self.motor_base = DummyMotor(motor_base_port)
        self.motors = {"A": self.motor_ee, "B": self.motor_vert, "C": self.motor_base}

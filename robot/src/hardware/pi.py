from buildhat import Motor
from hardware.robot_arm import RobotArm


class PiRobotArm(RobotArm):
    def _init_motors(self, motor_ee_port: str, motor_vert_port: str, motor_base_port: str):
        self.motor_ee = Motor(motor_ee_port)
        self.motor_vert = Motor(motor_vert_port)
        self.motor_base = Motor(motor_base_port)
        self.motors = {"A": self.motor_ee, "B": self.motor_vert, "C": self.motor_base}

import logging
from hardware.base_arm import BaseRobotArm

logger = logging.getLogger("robot_arm")


class RobotArm(BaseRobotArm):
    def __new__(
        cls,
        motor_ee_port="A",
        motor_vert_port="B",
        motor_base_port="C",
        urdf_file="zeroshot_prototype.xml"
    ):
        # If we are instantiating a subclass, delegate to object allocation
        if cls is not RobotArm:
            return super().__new__(cls)

        try:
            from hardware.pi import PiRobotArm
            logger.info("Connecting BuildHAT motors...")
            return PiRobotArm(
                motor_ee_port=motor_ee_port,
                motor_vert_port=motor_vert_port,
                motor_base_port=motor_base_port,
                urdf_file=urdf_file
            )
        except (ImportError, Exception) as e:
            logger.warning(
                f"Failed to connect physical BuildHAT motors ({e}). "
                "Falling back to DummyRobotArm simulation."
            )
            from hardware.dummy import DummyRobotArm
            return DummyRobotArm(
                motor_ee_port=motor_ee_port,
                motor_vert_port=motor_vert_port,
                motor_base_port=motor_base_port,
                urdf_file=urdf_file
            )

    def _init_motors(self, motor_ee_port: str, motor_vert_port: str, motor_base_port: str):
        # This base method is not called directly since __new__ redirects instantiation to subclasses.
        # It exists to satisfy the BaseRobotArm abstract method requirement.
        pass

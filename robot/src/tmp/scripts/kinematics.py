import pinocchio as pin
import numpy as np

urdf_path = "geometry.urdf"
model = pin.buildModelFromUrdf(urdf_path)
data = model.createData()


def fk(q_joint_rad):
    q = pin.neutral(model)
    q[0] = q_joint_rad[0]  # J1
    q[1] = q_joint_rad[1]  # J2
    q[2] = q_joint_rad[2]  # J3
    pin.forwardKinematics(model, data, q)
    pin.updateFramePlacements(model, data)
    ee_id = model.getFrameId("end_effector")
    return data.oMf[ee_id]


def validate():
    print("=== VALIDIERUNG ===\n")

    # TEST 1: q = [0, 0, 0]
    # EE: x = 0.024 + 0.120 = 0.144
    #      y = 0.088
    #      z = 0.444 + 0.444 = 0.888
    T = fk([0.0, 0.0, 0.0])
    print("Test 1 - Nullkonfiguration:")
    print(f"  got:      {T.translation.round(4)}")
    print("  expected: [0.144, 0.088, 0.888]\n")

    # TEST 2: J1 = 90°, J2=J3=0
    # J1 dreht um Z: X-Anteile -> Y, Y-Anteile -> -X
    # x = -0.088, y = 0.144, z = 0.888
    T = fk([np.pi/2, 0.0, 0.0])
    print("Test 2 - J1=90°, J2=J3=0:")
    print(f"  got:      {T.translation.round(4)}")
    print("  expected: [-0.088,  0.144, 0.888]\n")

    # TEST 3: J2 = 90°, J1=J3=0
    # J2 klappt Arm nach oben (X -> Z)
    # x = 0.024, y = 0.088, z = 0.888 + 0.120 = 1.008
    T = fk([0.0, np.pi/2, 0.0])
    print("Test 3 - J2=90°, J1=J3=0:")
    print(f"  got:      {T.translation.round(4)}")
    print("  expected: [0.024,  0.088, 1.008]\n")

    # TEST 4: J3 = 90°, J1=J2=0
    # J3 dreht Kreuzarm: Y-Offset -> Z-Offset
    # x = 0.144, y = 0.0, z = 0.888 + 0.088 = 0.976
    T = fk([0.0, 0.0, np.pi/2])
    print("Test 4 - J3=90°, J1=J2=0:")
    print(f"  got:      {T.translation.round(4)}")
    print("  expected: [0.144,  0.000, 0.976]\n")


validate()

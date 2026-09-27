import os
import numpy as np
import pinocchio as pin

class PinocchioKinematics:
    """
    Kinematics solver using Pinocchio for all forward kinematics, 
    Jacobian calculations, and iterative DLS IK resolution.
    """
    def __init__(self, urdf_path, offsets=None, limits=None, tolerance_m=0.015, max_iterations=150):
        self.offsets = offsets or {"A": 75.0, "B": -24.0, "C": 0.0}
        self.limits = limits or {
            "A": [-45.0, 45.0], "B": [-50.0, 20.0], "C": [-45.0, 45.0]
        }
        self.damping = 1e-6
        self.tolerance_m = tolerance_m
        self.max_iterations = max_iterations
        
        if not os.path.exists(urdf_path):
            raise FileNotFoundError(f"URDF file not found: {urdf_path}")
            
        self.model = pin.buildModelFromUrdf(urdf_path)
        self.data = self.model.createData()
        self.ee_frame_id = self.model.getFrameId("end_effector")
        
        # Map joint names to Pinocchio idx_q indices
        self.joints = ["joint1", "joint2", "joint3"]
        self.idx_q = [self.model.joints[self.model.getJointId(j)].idx_q for j in self.joints]

    def _to_q_rad(self, q_deg):
        q_rad = np.zeros(self.model.nq)
        for idx, val in zip(self.idx_q, q_deg):
            q_rad[idx] = np.radians(val)
        return q_rad

    def get_current_pos(self, q_deg):
        q_rad = self._to_q_rad(q_deg)
        pin.forwardKinematics(self.model, self.data, q_rad)
        pin.updateFramePlacements(self.model, self.data)
        return self.data.oMf[self.ee_frame_id].translation.copy()

    def get_jacobian(self, q_deg):
        q_rad = self._to_q_rad(q_deg)
        pin.forwardKinematics(self.model, self.data, q_rad)
        pin.updateFramePlacements(self.model, self.data)
        J = pin.computeFrameJacobian(
            self.model, self.data, q_rad, self.ee_frame_id, pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )
        return J[:3, :]

    def solve_ik_iterative(self, current_angles, target_xyz, absolute=True):
        """Solves Inverse Kinematics iteratively using Damped Least Squares."""
        q_sol = np.array([current_angles[axis] + self.offsets[axis] for axis in ["C", "B", "A"]], dtype=float)
        goal_xyz = np.array(target_xyz, dtype=float) if absolute else (self.get_current_pos(q_sol) + np.array(target_xyz, dtype=float))

        eps = self.tolerance_m
        max_iters = self.max_iterations
        step_size = 0.2
        success = False

        for _ in range(max_iters):
            current_xyz = self.get_current_pos(q_sol)
            error_xyz = goal_xyz - current_xyz
            if np.linalg.norm(error_xyz) < eps:
                success = True
                break

            J = self.get_jacobian(q_sol)
            try:
                v = np.linalg.solve(J.dot(J.T) + np.eye(3) * self.damping, error_xyz)
                dq_deg = np.degrees(J.T.dot(v))
            except np.linalg.LinAlgError:
                return False, {}, "IK Solver encountered numerical singularity."

            q_sol += step_size * dq_deg

            # Clamp boundaries
            for idx, axis in enumerate(["C", "B", "A"]):
                l_min, l_max = self.limits[axis]
                joint_val = np.clip(q_sol[idx] - self.offsets[axis], l_min, l_max)
                q_sol[idx] = joint_val + self.offsets[axis]

        solved_angles = {axis: q_sol[idx] - self.offsets[axis] for idx, axis in enumerate(["C", "B", "A"])}
        if not success:
            err = np.linalg.norm(goal_xyz - self.get_current_pos(q_sol)) * 1000
            return False, solved_angles, f"IK Solver failed to converge. Final error: {err:.3f} mm."

        return True, solved_angles, ""

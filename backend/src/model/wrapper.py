from abc import ABC, abstractmethod
from typing import List
import numpy as np
import time
import cv2
import jax
from octo.model.octo_model import OctoModel

import pinocchio as pin

from shared.classes import RobotState, RobotCommand, GoalMessage, SystemConfigMessage, ModelMode

class InverseKinematicsSolver:
    def __init__(self):
        self.urdf_content = None
        self.ik_model = None
        self.data = None
        self.endeffector = None
        self.damping = 1e-6
        self.eps = 1e-4
        self.max_iters = 1000
        self.learn_rate = 1.0


    def load_urdf_from_string(self, xml_content: str):
        try:
            self.urdf_content = xml_content
            self.ik_model = pin.buildModelFromXML(self.urdf_content)
            self.data = self.ik_model.createData()
            print("IK Solver: Robot URDF loaded successfully.")
            # eventuell herausnehmen wenn kein gripper -> stattdessen cross oder check (if-else) herausnehmen
            if self.ik_model.existFrame("end_effector"):
                self.endeffector = self.ik_model.getFrameId("end_effector")
                print(self.ik_model.names)
            else:
                raise ValueError("IK Solver: Endeffector Link 'gripper' not found. Check URDF file.")
        except Exception as e:
            print(f"IK: Solver: failed to load URDF for IK solver: {e}")
    
    def get_current_pos(self, current_joint_angles: List[float]) -> List[float]:
        """get current pos vom endeffektor über angles mithilfe von forward kinematics + pinocchio"""
        if not self.ik_model or not self.endeffector:
            print("IK: Solver: failed to get current xyz position. No model or no endeffector found.")
            return [0.0] * 3
        current_angles = np.radians(current_joint_angles)
        pin.forwardKinematics(self.ik_model, self.data, current_angles)
        pin.updateFramePlacements(self.ik_model, self.data)
        translated = self.data.oMf[self.endeffector].translation
        return translated.flatten().tolist()
        
    # inverse kinematics
    def calculate_joint_angles_delta(self, current_angles: List[float], delta_xyz: List[float]) -> List[float]:
        """berechnet die benötigten Gelenkwinkel-Änderungen, damit der Endeffektor sich um delta_xyz bewegt (relativ zum aktuellen Ziel) -> delta_joint_angles"""
        if not self.ik_model or not self.endeffector:
            print("IK Solver: failed to calculate relative target joint angles. No model or no endeffector found.")
            return [0.0] * 3
        
        print("Current joint angles:")
        print(current_angles)
        current_q = np.radians(current_angles)
        delta_pos = np.array(delta_xyz)
        pin.forwardKinematics(self.ik_model, self.data, current_q)
        pin.updateFramePlacements(self.ik_model, self.data)
        Jacobian = pin.computeFrameJacobian(
            self.ik_model,
            self.data,
            current_q,
            self.endeffector,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED)
        Jacobian_xyz = Jacobian[:3, :]

        #delta = J.T * inv(J*J.T + damping*I) * delta_x (least squares inverse)
        JxJ_t = Jacobian_xyz.dot(Jacobian_xyz.T)
        damp_matrix = np.eye(3) * self.damping

        #delta_pos = (Jacobian_t + damping)*v
        v = np.linalg.solve(JxJ_t + damp_matrix, delta_pos)
        delta_angles = Jacobian_xyz.T.dot(v)
        output = np.degrees(delta_angles).flatten().tolist()
        print("Calculated delta:")
        print(output)
        return output

class IModelPolicy(ABC):
    """Abstrakte Klasse, die die Schnittstelle definiert, die jede Modell-Policy implementieren muss, um mit dem RemoteNetworkClient zu kommunizieren. """
    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def configure_robot(self, config: SystemConfigMessage):
        pass

    @abstractmethod
    def set_goal(self, goal: GoalMessage):
        pass

    @abstractmethod
    def predict_action(self, state: RobotState) -> RobotCommand:
        pass

class MockWrapper(IModelPolicy):
    # MockWrapper ist eine alternative zu OctoWrapper, die es erlaubt, 
    # manuell Zielkoordinaten einzugeben und damit die IK zu testen, 
    # ohne dass tatsächlich ein trainiertes Modell benötigt wird. 
    # Nützlich für Debugging und Tests der restlichen Pipeline ohne Abhängigkeit von Octo.
    def __init__(self):
        self.ik_solver = InverseKinematicsSolver()
        self.task = None
        self.port_mapping = {}
        self.mode = 1
        
    def initialize(self):
        print("Loading Mock Wrapper...")
        print("Only use with action_horizon = 1!")
        
    def configure_robot(self, config: SystemConfigMessage):
        print("MockWrapper: configuring IK solver with received URDF.")
        self.ik_solver.load_urdf_from_string(config.urdf_xml_content)
        self.port_mapping = config.motor_port_mapping

    def set_goal(self, goal: GoalMessage):
        print(f"MockWrapper: Processing Goal -> '{goal.text_prompt}'")
        print("Enter target xyz coordinates (default: delta xyz) and gripper pos (0: closed, 1: open) seperated by spaces...")
        print("Enter abs to switch to absolute target coordinates")
        print("Enter dlt to switch to delta target coordinates")

    # im cli koordinaten eingeben x, y, z in metern und 0 oder 1 für gripper position
    # mocken quasi ne policy um den z.B. inverse kinematics zu mocken 
    def predict_action(self, state: RobotState) -> RobotCommand:
        target_angles = []
        while True:
            user_in = input("Target coordinates > ").strip()
            try:
                # used to allow abs, removed since
                if user_in == "dlt":
                    self.mode = 1
                    continue

                if user_in == "":
                    targets = [0.0] * 4
                else:
                    targets = [float(x.strip()) for x in user_in.split(' ')]
                    if self.mode == 1:
                        print("MockWrapper: Calculating joint angle delta using ik solver...")
                        delta_joint = self.ik_solver.calculate_joint_angles_delta(state.motor_positions[:self.ik_solver.ik_model.nq], delta_xyz=targets[:3])
                        for i in range(4):
                            target_angles.append(delta_joint)
                        print("MockWrapper: Calculated delta angles:")
                        print(delta_joint)
                
                return RobotCommand(
                    target_velocities=[0.0] * len(targets),
                    target_positions=target_angles,
                    gripper_open=[bool(targets[3] > 0), False, False, False],
                    halt_flag=False,
                    timestamp=time.time()
                )
                
            except ValueError:
                print("Invalid input format. Use space separated numbers.")
                print("Sending 0 command to maintain loop...")
                zero_position = []
                for i in range(4):
                    zero_position.append([0.0] * 3)
                
                return RobotCommand(
                    target_velocities=[0.0] * 4,
                    target_positions=zero_position,
                    gripper_open=[False, False, False, False],
                    halt_flag=False,
                    timestamp=time.time()
                )

class OctoWrapper(IModelPolicy):
    def __init__(self, checkpoint_path: str, octomode, action_gain: float = 2.0, tasktype = 1, usewrist = True, step = None, window_size = 1, action_horizon = 50):
        self.checkpoint_path = checkpoint_path
        self.step = step
        self.ik_solver = InverseKinematicsSolver()
        self.task = None
        self.observation_history = []
        # enum base, small oder finetuned verwenden
        self.octomode = octomode
        # für die motoren, wird evtl. nicht verwendet
        self.port_mapping = {}
        # counter für jede inferenz
        self.timestep = 0
        # wie viele past_observations octo verwendet für inferenz (lieber runter als rübergehen)
        self.window_size = window_size
        self.action_horizon = action_horizon
        self.action_gain = action_gain
        self.task_type = tasktype
        self.use_wrist = usewrist
        self.use_proprio = (octomode == ModelMode.FINETUNED)
    
    def initialize(self):
        if self.octomode == ModelMode.BASE:
            print("Loading OCTO-BASE Model...")
            self.model = OctoModel.load_pretrained("hf://rail-berkeley/octo-base-1.5")
        elif self.octomode == ModelMode.SMALL:
            print("Loading OCTO-SMALL Model...")
            self.model = OctoModel.load_pretrained("hf://rail-berkeley/octo-small-1.5")
        elif self.octomode == ModelMode.FINETUNED:
            print(f"Loading OCTO Model from {self.checkpoint_path} (step={self.step})...")
            self.model = OctoModel.load_pretrained(self.checkpoint_path, step=self.step)
        else:
            print("Could not load Octo model. Please specify mode...")
        pass

    def configure_robot(self, config: SystemConfigMessage):
        print("OctoWrapper: Configuring IK solver with received URDF.")
        self.ik_solver.load_urdf_from_string(config.urdf_xml_content)
        self.port_mapping = config.motor_port_mapping

    def set_goal(self, goal: GoalMessage):
        print(f"OctoWrapper: Processing Goal -> '{goal.text_prompt}'")
        if goal.is_update:
            self.observation_history = []
        
        #TODO: Run image through Octo Encoder for image goal
        if self.task_type == 1:
            self.task = self.model.create_tasks(texts=[goal.text_prompt])
        elif self.task_type == 2:
            print("Loading goal image...")
            goal_image_processed = self._preprocess(goal.goal_image, 256, True)
            print("Batching goal image...")
            batched_img = np.expand_dims(goal_image_processed, axis=0)
            batched_goal_image = {"image_primary": batched_img}
            print(batched_goal_image["image_primary"].shape)
            print("Creating goal image task...")
            self.task = self.model.create_tasks(goals=batched_goal_image)
    # hier wird tatsächlich mit octo interagiert
    def predict_action(self, state: RobotState) -> RobotCommand:
        self.timestep += 1
        has_wrist = False
        print("Preprocessing images...")
        processed_imgs = []
        processed_imgs.append(self._preprocess(state.camera_frames[0], 256, True))
        if len(state.camera_frames) > 1:
            processed_imgs.append(self._preprocess(state.camera_frames[1], 128, True))
            has_wrist = True
        
        print("Updating history...")
        self.observation_history.append(processed_imgs)

        if len(self.observation_history) < self.window_size:
            history = [self.observation_history[0]] * (self.window_size - len(self.observation_history)) + self.observation_history
        else:
            history = self.observation_history[-self.window_size:]

        img_primary = np.stack([step[0] for step in history])[None, ...]
        cur_timestep = self.timestep
        # window_size timesteps ending at the current one
        timestep_arr = np.arange(
            cur_timestep - self.window_size + 1, cur_timestep + 1, dtype=np.int32
        )[None, ...]

        ws = self.window_size
        print(f"[WRAP] img_primary shape={img_primary.shape} mean={img_primary.mean():.1f}")

        observation = {
            "image_primary": img_primary,
            "timestep": timestep_arr,
            "task_completed": np.zeros((1, ws, self.action_horizon), dtype=bool),
            "pad_mask_dict": {
                "image_primary": np.ones((1, ws), dtype=bool),
                "image_wrist": np.zeros((1, ws), dtype=bool),
                "timestep": np.ones((1, ws), dtype=bool)
            },
            "timestep_pad_mask": np.full((1, ws), True, dtype=bool)
        }
        # Proprio only for the finetuned model (base/small have no proprio tokenizer/stats)
        if self.use_proprio:
            proprio_raw = np.asarray(state.motor_positions[:3], dtype=np.float32)
            p_stats = self.model.dataset_statistics["proprio"]
            proprio_mean = np.array(p_stats["mean"], dtype=np.float32)
            proprio_std = np.array(p_stats["std"], dtype=np.float32)
            proprio_now = (proprio_raw - proprio_mean) / (proprio_std + 1e-8)
            proprio_arr = np.tile(proprio_now, (self.window_size, 1))[None, ...]
            print(f"[WRAP] proprio_raw={proprio_raw}  normalized={proprio_now}")
            observation["proprio"] = proprio_arr
            observation["pad_mask_dict"]["proprio"] = np.ones((1, ws), dtype=bool)
        if has_wrist and self.use_wrist:
            img_wrist = np.stack([step[1] for step in history])[None, ...]
            observation["image_wrist"] = img_wrist
            # erstmal zeros werden später beschrieben mit ones falls wir diese verwenden später

            observation["pad_mask_dict"]["image_wrist"] = np.ones((1, self.window_size), dtype=bool)
        elif not self.use_wrist:
            pass
        else:
            mock_wrist = np.zeros((1, self.window_size, 128, 128, 3), dtype=np.uint8)
            observation["image_wrist"] = mock_wrist

        print("Inferencing...")
        if self.model and jax:
            # action stats key differs: finetuned has flat "action";
            # raw octo may nest it (e.g. "bridge_dataset" -> "action").
            if "action" in self.model.dataset_statistics:
                action_stats = self.model.dataset_statistics["action"]
            else:
                action_stats = None
                for k, sub in self.model.dataset_statistics.items():
                    if isinstance(sub, dict) and "action" in sub:
                        action_stats = sub["action"]
                        break
                if action_stats is None:
                    action_stats = self.model.dataset_statistics[
                        list(self.model.dataset_statistics.keys())[0]]
            actions = self.model.sample_actions(
                observation,
                self.task,
                unnormalization_statistics=action_stats,
                rng=jax.random.PRNGKey(self.timestep))
            action_metric = np.array(actions[0])
        else:
            action_metric = np.array([0.01, 0.02, 0.01, 0.0, 0.0, 0.0, 1.0])
        print(action_metric)
        print(f"[WRAP] action[0] raw={action_metric[0][:3]}  after_gain={action_metric[0][:3]*self.action_gain}")
        cartesian_deltas = []
        gripper_open_arr = []
        for i in range(len(action_metric)):
            delta_xyz = action_metric[i][:3] * self.action_gain
            cartesian_deltas.append(list(delta_xyz))
            gripper_open_arr.append(bool(action_metric[i][6] > 0.5))
        print(f"[WRAP] cartesian delta[0]={cartesian_deltas[0]}")
        return RobotCommand(
            target_velocities=[0.0]*4, #in zero-shot OCTO we do not get vel
            target_positions=cartesian_deltas,
            gripper_open=gripper_open_arr,
            halt_flag=False,
            timestamp=state.timestamp
        )

    def _preprocess(self, jpeg_bytes, size, bgrconv):
        if isinstance(jpeg_bytes, list):
            if len(jpeg_bytes) > 0 and isinstance(jpeg_bytes[0], bytes):
                data = np.frombuffer(jpeg_bytes[0], dtype=np.uint8)
            else:
                data = np.array(jpeg_bytes, dtype=np.uint8)
        else:
            data = np.frombuffer(jpeg_bytes, np.uint8)
            
        data = data.flatten()
        
        if data.size == 0:
            print("Warning: Received empty image data")
            return np.zeros((size, size, 3), dtype=np.uint8)
        
        
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)

        if img is None:
            print("Warning: Image decoding failed (corrupted or incomplete data).")
            return np.zeros((size, size, 3), dtype=np.uint8)
        #check if BGR to RGB conversion is needed
        if bgrconv:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        height, width, _ = img.shape
        min_dim = min(height, width)
        start_x = (width - min_dim) // 2
        start_y = (height - min_dim) // 2
        cropped = img[start_y:start_y + min_dim, start_x:start_x + min_dim]
        return cv2.resize(cropped, (size, size))

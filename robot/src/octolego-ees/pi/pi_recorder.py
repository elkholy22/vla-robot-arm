import os
import pickle
import json
import sys
import shutil
import queue
import threading
from dataclasses import asdict
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.classes import RobotState, RobotCommand, GoalMessage, SystemConfigMessage

class PiDataRecorder:
    def __init__(self, save_dir: str = "pi_recorded_data"):
        self.base_path = save_dir
        self.current_episode_path = None
        self.episode_counter = 0
        self.step_counter = 0
        self.language_instruction = None
        self.last_finished_episode_path = None

        os.makedirs(self.base_path, exist_ok=True)
        
        # Async background writer queue & thread
        self.write_queue = queue.Queue()
        self.running = True
        self.worker_thread = threading.Thread(target=self._write_worker, daemon=True)
        self.worker_thread.start()

    def _write_worker(self):
        while self.running:
            try:
                item = self.write_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            file_path, step_data = item
            try:
                with open(file_path, "wb") as f:
                    pickle.dump(step_data, f)
                print(f"Step {step_data['step_id']} saved")
            except Exception as e:
                print(f"[PiRecorder] Error saving step to {file_path}: {e}")
            finally:
                self.write_queue.task_done()

    def start_episode(self, goal: GoalMessage, sys_config: SystemConfigMessage):
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{timestamp}_ep_{self.episode_counter}"
        
        self.current_episode_path = os.path.join(self.base_path, folder_name)
        os.makedirs(self.current_episode_path, exist_ok=True)
        self.step_counter = 0
        self.episode_counter += 1

        print(f"[PiRecorder] Starting Episode: {folder_name}")

        self.language_instruction = goal.text_prompt if goal.text_prompt else "No instruction provided"
        
        metadata = {
            "source": "raspberry_pi",
            "goal_text": self.language_instruction,
            "task_id": goal.task_id,
            "start_time": timestamp,
            "motor_limits": sys_config.motor_limits,
            "config_port_mapping": "saved_in_urdf",
            #"control_frequency_hz": sys_config.control_frequency_hz,
        }
        
        if goal.goal_image is not None:
            with open(os.path.join(self.current_episode_path, "goal_image.pkl"), "wb") as f:
                pickle.dump(goal.goal_image, f)

        with open(os.path.join(self.current_episode_path, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=4)


    def log_step(self, state: RobotState, command: RobotCommand):
        if not self.current_episode_path:
            return

        raw_motor_positions = getattr(state, 'motor_positions', None)
        calibrated_angles = getattr(state, 'joint_angles', None)

        # Prefer end-effector position passed in via `state.ee_position`.
        ee_pos = getattr(state, 'ee_position', None)

        step_data = {
            "step_id": self.step_counter,
            "timestamp": state.timestamp,
            "state": asdict(state),
            "raw_motor_positions": raw_motor_positions,
            "calibrated_joint_angles": calibrated_angles,
            "ee_position": ee_pos,
            "command": asdict(command),
            "language_instruction": self.language_instruction,
        }

        # evtl. noch überarbeiten
        filename = f"step_{self.step_counter:05d}.pkl"
        file_path = os.path.join(self.current_episode_path, filename)

        # Queue the step data for async writing
        self.write_queue.put((file_path, step_data))
        self.step_counter += 1

    def end_episode(self):
        if self.current_episode_path:
            # Drain the queue to ensure all steps are saved before finalizing
            self.write_queue.join()
            print(f"[PiRecorder] Episode finished. Saved {self.step_counter} steps.")
            if self.step_counter == 0:
                try:
                    shutil.rmtree(self.current_episode_path)
                    print(f"[PiRecorder] Cleaned up empty episode folder: {self.current_episode_path}")
                except Exception as e:
                    print(f"[PiRecorder] Failed to clean up empty folder: {e}")
                if self.episode_counter > 0:
                    self.episode_counter -= 1
                self.current_episode_path = None
            else:
                # remember last finished episode path in case we want to delete it
                self.last_finished_episode_path = self.current_episode_path
                self.current_episode_path = None

    def delete_last_episode(self) -> bool:
        """Delete only the most recently saved episode directory (if any).

        Returns True if a directory was deleted, False otherwise.
        This will never delete an episode that is currently being recorded.
        """
        # Ensure any pending writes are complete first
        self.write_queue.join()

        # List episode folders in base path
        try:
            entries = [d for d in os.listdir(self.base_path)
                       if os.path.isdir(os.path.join(self.base_path, d))]
        except FileNotFoundError:
            print(f"[PiRecorder] Base path {self.base_path} does not exist.")
            return False

        if not entries:
            print("[PiRecorder] No episodes to delete.")
            return False

        # Exclude current episode if recording is in progress
        cur_basename = None
        if self.current_episode_path:
            cur_basename = os.path.basename(self.current_episode_path)

        candidates = [d for d in entries if d != cur_basename]
        if not candidates:
            print("[PiRecorder] No finished episodes to delete (current episode excluded).")
            return False

        # Choose the most recently modified folder
        latest = max(candidates, key=lambda d: os.path.getmtime(os.path.join(self.base_path, d)))
        path_to_delete = os.path.join(self.base_path, latest)

        try:
            shutil.rmtree(path_to_delete)
            print(f"[PiRecorder] Deleted last episode: {latest}")
            # adjust internal counter if possible
            if hasattr(self, 'episode_counter') and self.episode_counter > 0:
                self.episode_counter -= 1
            # clear remembered finished path if it matches
            if getattr(self, 'last_finished_episode_path', None) and \
               os.path.basename(self.last_finished_episode_path) == latest:
                self.last_finished_episode_path = None
            return True
        except Exception as e:
            print(f"[PiRecorder] Failed to delete {path_to_delete}: {e}")
            return False
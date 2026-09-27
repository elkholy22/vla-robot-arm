
import glob
import json
import os
import pickle
from pathlib import Path

import cv2
import numpy as np
import tensorflow_datasets as tfds
import tensorflow_hub as hub

# Now using pinocchio to compute forward kinematics for end-effector position in state calculation
# since we're using delta joint angles as actions, we need to compute the corresponding delta end-effector position for the dataset
# so that OCTO can later use the delta end-effector position as the training action

import pinocchio as pin


class SwitcherDataset(tfds.core.GeneratorBasedBuilder):

    VERSION = tfds.core.Version('2.0.0')

    RELEASE_NOTES = {
        '2.0.0': 'Forward kinematics based Cartesian actions.'
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._embed = hub.load(
            "https://tfhub.dev/google/universal-sentence-encoder-large/5"
        )

        self._root_dir = Path(__file__).resolve().parents[2]

        self._raw_path = (
            self._root_dir / 'pi' / 'pi_recorded_data'
        )

        urdf_path = (
            self._root_dir
            / 'pi'
            / 'zeroshot_prototype.xml'
        )

        with open(urdf_path, 'r') as f:
            f.read()

        self.ik_model = pin.buildModelFromUrdf(str(urdf_path))
        self.data = self.ik_model.createData()

        self.ee_frame = self.ik_model.getFrameId("end_effector")

    def _info(self):

        return self.dataset_info_from_configs(
            features=tfds.features.FeaturesDict({

                'steps': tfds.features.Dataset({

                    'observation': tfds.features.FeaturesDict({

                        'image': tfds.features.Image(
                            shape=(256, 256, 3),
                            dtype=np.uint8,
                            encoding_format='png',
                        ),

                        'wrist_image': tfds.features.Image(
                            shape=(128, 128, 3),
                            dtype=np.uint8,
                            encoding_format='png',
                        ),

                        'state': tfds.features.Tensor(
                            shape=(3,),
                            dtype=np.float32,
                        ),
                    }),

                    'action': tfds.features.Tensor(
                        shape=(7,),
                        dtype=np.float32,
                        doc='dx dy dz droll dpitch dyaw end_effector'
                    ),

                    'discount': tfds.features.Scalar(dtype=np.float32),
                    'reward': tfds.features.Scalar(dtype=np.float32),
                    'is_first': tfds.features.Scalar(dtype=np.bool_),
                    'is_last': tfds.features.Scalar(dtype=np.bool_),
                    'is_terminal': tfds.features.Scalar(dtype=np.bool_),

                    'language_instruction': tfds.features.Text(),

                    'language_embedding': tfds.features.Tensor(
                        shape=(512,),
                        dtype=np.float32,
                    ),
                }),

                'episode_metadata': tfds.features.FeaturesDict({
                    'file_path': tfds.features.Text(),
                    'task_id': tfds.features.Text(),
                    'start_time': tfds.features.Text(),
                })
            })
        )

    def _split_generators(self, dl_manager):

        return {
            'train': self._generate_examples(
                str(self._raw_path / 'train' / '*')
            ),

            'val': self._generate_examples(
                str(self._raw_path / 'val' / '*')
            ),
        }

    def _decode_frame(self, frame):

        if frame is None:
            return np.zeros((64, 64, 3), dtype=np.uint8)

        if isinstance(frame, np.ndarray):
            if frame.ndim == 1:
                arr = frame
            else:
                return frame

        elif isinstance(frame, (bytes, bytearray)):
            arr = np.frombuffer(frame, dtype=np.uint8)

        else:
            arr = np.asarray(frame, dtype=np.uint8).flatten()

        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if img is None:
            return np.zeros((64, 64, 3), dtype=np.uint8)

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        return img

    def _fk_xyz(self, joint_angles_deg):

        q = np.radians(joint_angles_deg)

        pin.forwardKinematics(
            self.ik_model,
            self.data,
            q,
        )

        pin.updateFramePlacements(
            self.ik_model,
            self.data,
        )

        xyz = self.data.oMf[self.ee_frame].translation

        return xyz.copy()

    def _generate_examples(self, path):

        episode_paths = glob.glob(path)

        for episode_path in episode_paths:

            metadata_path = os.path.join(
                episode_path,
                'metadata.json'
            )

            if not os.path.exists(metadata_path):
                continue

            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            step_paths = sorted(
                glob.glob(os.path.join(episode_path, 'step_*.pkl'))
            )

            if len(step_paths) < 2:
                continue

            raw_steps = []

            for sp in step_paths:
                with open(sp, 'rb') as f:
                    raw_steps.append(pickle.load(f))

            episode = []

            for i in range(len(raw_steps) - 1):

                cur = raw_steps[i]
                nxt = raw_steps[i + 1]

                raw = np.asarray(
                    cur['state']['motor_positions'],
                    dtype=np.float32,
                )[:3]

                q_t = np.array([
                    raw[2],   # C -> joint1
                    raw[1],   # B -> joint2
                    raw[0],   # A -> joint3
                ], dtype=np.float32)

                raw_next = np.asarray(
                    nxt['state']['motor_positions'],
                    dtype=np.float32,
                )[:3]

                q_t1 = np.array([
                    raw_next[2],
                    raw_next[1],
                    raw_next[0],
                ], dtype=np.float32)

                ee_t = self._fk_xyz(q_t)
                ee_t1 = self._fk_xyz(q_t1)

                delta_xyz = ee_t1 - ee_t

                delta_xyz = np.clip(
                    delta_xyz,
                    -0.05,
                    0.05,
                )

                action = np.asarray([
                    delta_xyz[0],
                    delta_xyz[1],
                    delta_xyz[2],
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ], dtype=np.float32)

                frames = cur['state'].get('camera_frames', [])

                image = (
                    self._decode_frame(frames[0])
                    if len(frames) > 0
                    else np.zeros((64, 64, 3), dtype=np.uint8)
                )

                wrist_image = (
                    self._decode_frame(frames[1])
                    if len(frames) > 1
                    else np.zeros((64, 64, 3), dtype=np.uint8)
                )

                instruction = metadata.get(
                    'goal_text',
                    'perform task'
                )

                embedding = self._embed([instruction])[0].numpy()

                episode.append({

                    'observation': {
                        'image': image,
                        'wrist_image': wrist_image,
                        'state': q_t,
                    },

                    'action': action,

                    'discount': 1.0,
                    'reward': float(i == len(raw_steps) - 2),
                    'is_first': i == 0,
                    'is_last': i == len(raw_steps) - 2,
                    'is_terminal': i == len(raw_steps) - 2,

                    'language_instruction': instruction,
                    'language_embedding': embedding,
                })

            yield episode_path, {
                'steps': episode,
                'episode_metadata': {
                    'file_path': episode_path,
                    'task_id': metadata.get('task_id', ''),
                    'start_time': metadata.get('start_time', ''),
                }
            }
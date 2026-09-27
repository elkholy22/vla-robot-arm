
import glob
import json
import os
import pickle
from pathlib import Path

import cv2
import numpy as np
import tensorflow_datasets as tfds
import tensorflow_hub as hub


class SwitcherDataset(tfds.core.GeneratorBasedBuilder):

    VERSION = tfds.core.Version('2.0.0')

    RELEASE_NOTES = {
        '2.0.0': 'Kinematics based Octo dataset format.'
    }

    IMAGE_SIZE = 256
    WRIST_SIZE = 128

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._embed = hub.load(
            "https://tfhub.dev/google/universal-sentence-encoder-large/5"
        )

        self._root_dir = Path(__file__).resolve().parents[2]

        self._raw_path = self._root_dir / 'pi' / 'pi_recorded_data'

    # ======================================================
    # DATASET INFO
    # ======================================================

    def _info(self):

        return self.dataset_info_from_configs(
            features=tfds.features.FeaturesDict({

                'steps': tfds.features.Dataset({

                    'observation': tfds.features.FeaturesDict({

                        'image_primary': tfds.features.Image(
                            shape=(256, 256, 3),
                            dtype=np.uint8,
                            encoding_format='jpeg',
                        ),

                        'image_wrist': tfds.features.Image(
                            shape=(128, 128, 3),
                            dtype=np.uint8,
                            encoding_format='jpeg',
                        ),

                        'joint_position': tfds.features.Tensor(
                            shape=(3,),
                            dtype=np.float32,
                        ),

                        'ee_position': tfds.features.Tensor(
                            shape=(3,),
                            dtype=np.float32,
                        ),
                    }),

                    # IMPORTANT:
                    # action = delta xyz
                    # exactly like octo predicts later
                    'action': tfds.features.Tensor(
                        shape=(7,),
                        dtype=np.float32,
                    ),

                    'discount': tfds.features.Scalar(
                        dtype=np.float32
                    ),

                    'reward': tfds.features.Scalar(
                        dtype=np.float32
                    ),

                    'is_first': tfds.features.Scalar(
                        dtype=np.bool_
                    ),

                    'is_last': tfds.features.Scalar(
                        dtype=np.bool_
                    ),

                    'is_terminal': tfds.features.Scalar(
                        dtype=np.bool_
                    ),

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

    # ======================================================
    # SPLITS
    # ======================================================

    def _split_generators(self, dl_manager):

        return {
            'train': self._generate_examples(
                str(self._raw_path / 'train' / '*')
            ),

            'val': self._generate_examples(
                str(self._raw_path / 'val' / '*')
            ),
        }

    # ======================================================
    # IMAGE DECODING
    # ======================================================

    def _decode_frame(self, frame, size):

        if frame is None:
            return np.zeros((size, size, 3), dtype=np.uint8)

        if isinstance(frame, np.ndarray):
            arr = frame

        elif isinstance(frame, bytes):
            arr = np.frombuffer(frame, dtype=np.uint8)

        else:
            arr = np.asarray(frame, dtype=np.uint8)

        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if img is None:
            return np.zeros((size, size, 3), dtype=np.uint8)

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        h, w, _ = img.shape

        crop = min(h, w)

        sx = (w - crop) // 2
        sy = (h - crop) // 2

        img = img[sy:sy+crop, sx:sx+crop]

        img = cv2.resize(img, (size, size))

        return img.astype(np.uint8)

    # ======================================================
    # EXAMPLES
    # ======================================================

    def _generate_examples(self, path):

        episode_paths = glob.glob(path)

        for episode_path in episode_paths:

            metadata_path = os.path.join(episode_path, 'metadata.json')

            if not os.path.exists(metadata_path):
                continue

            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            step_paths = sorted(
                glob.glob(os.path.join(episode_path, 'step_*.pkl'))
            )

            if len(step_paths) == 0:
                continue

            episode_steps = []

            for i, step_path in enumerate(step_paths):

                with open(step_path, 'rb') as f:
                    step = pickle.load(f)

                state = step['state']
                step['command']
                extra = step.get('extra_data', {})

                frames = state.get('camera_frames', [])

                image_primary = self._decode_frame(
                    frames[0] if len(frames) > 0 else None,
                    self.IMAGE_SIZE
                )

                image_wrist = self._decode_frame(
                    frames[1] if len(frames) > 1 else None,
                    self.WRIST_SIZE
                )

                joint_position = np.asarray(
                    state.get('motor_positions', [0, 0, 0]),
                    dtype=np.float32
                )[:3]

                ee_position = np.asarray(
                    extra.get('ee_position', [0, 0, 0]),
                    dtype=np.float32
                )

                delta_xyz = np.asarray(
                    extra.get('delta_xyz', [0, 0, 0]),
                    dtype=np.float32
                )

                # octo style action
                # [dx dy dz droll dpitch dyaw gripper]
                action = np.asarray([
                    delta_xyz[0],
                    delta_xyz[1],
                    delta_xyz[2],
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ], dtype=np.float32)

                language_instruction = metadata.get(
                    'goal_text',
                    'move the robot arm'
                )

                language_embedding = self._embed(
                    [language_instruction]
                )[0].numpy()

                episode_steps.append({

                    'observation': {
                        'image_primary': image_primary,
                        'image_wrist': image_wrist,
                        'joint_position': joint_position,
                        'ee_position': ee_position,
                    },

                    'action': action,

                    'discount': 1.0,

                    'reward': float(i == (len(step_paths) - 1)),

                    'is_first': i == 0,

                    'is_last': i == (len(step_paths) - 1),

                    'is_terminal': i == (len(step_paths) - 1),

                    'language_instruction': language_instruction,

                    'language_embedding': language_embedding,
                })

            sample = {
                'steps': episode_steps,
                'episode_metadata': {
                    'file_path': episode_path,
                    'task_id': metadata.get('task_id', ''),
                    'start_time': metadata.get('start_time', ''),
                }
            }

            yield episode_path, sample
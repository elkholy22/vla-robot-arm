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

                    # Action is Octo-compatible Cartesian delta of end-effector
                    # followed by roll/pitch/yaw (unused) and a terminal flag.
                    # Format: [dx, dy, dz, droll, dpitch, dyaw, end_effector_exists]
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

    def _decode_frame(self, frame, target_size=None):
        if frame is None:
            h, w = target_size if target_size else (64, 64)
            return np.zeros((h, w, 3), dtype=np.uint8)

        if isinstance(frame, np.ndarray):
            if frame.ndim == 1:
                arr = frame
            else:
                img = frame
                if target_size is not None:
                    img = cv2.resize(
                        img,
                        (target_size[1], target_size[0]),
                        interpolation=cv2.INTER_AREA,
                    )
                return img

        elif isinstance(frame, (bytes, bytearray)):
            arr = np.frombuffer(frame, dtype=np.uint8)

        else:
            arr = np.asarray(frame, dtype=np.uint8).flatten()

        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if img is None:
            h, w = target_size if target_size else (64, 64)
            return np.zeros((h, w, 3), dtype=np.uint8)

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if target_size is not None:
            img = cv2.resize(
                img,
                (target_size[1], target_size[0]),
                interpolation=cv2.INTER_AREA,
            )

        return img

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

                # Prefer recorded end-effector positions if present.
                ee_cur = cur.get('ee_position')
                ee_nxt = nxt.get('ee_position')

                ee_cur = np.asarray(ee_cur, dtype=np.float32)
                ee_nxt = np.asarray(ee_nxt, dtype=np.float32)

                delta_xyz = ee_nxt - ee_cur

                delta_xyz = np.clip(
                    delta_xyz,
                    -0.05,
                    0.05,
                )

                # Build Octo-compatible 7-dim action: dx,dy,dz, droll,dpitch,dyaw, flag
                action = np.asarray([
                    float(delta_xyz[0]),
                    float(delta_xyz[1]),
                    float(delta_xyz[2]),
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ], dtype=np.float32)

                frames = cur['state'].get('camera_frames', [])

                image = (
                    self._decode_frame(
                        frames[0],
                        target_size=(256, 256),
                    )
                    if len(frames) > 0
                    else np.zeros((256, 256, 3), dtype=np.uint8)
                )

                wrist_image = (
                    self._decode_frame(
                        frames[1],
                        target_size=(128, 128),
                    )
                    if len(frames) > 1
                    else np.zeros((128, 128, 3), dtype=np.uint8)
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
                        'state': ee_cur,
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

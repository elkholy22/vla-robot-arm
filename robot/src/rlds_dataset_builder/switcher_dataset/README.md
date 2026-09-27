# Switcher Dataset: LEGO Robot Manipulation

The **Switcher Dataset** contains demonstrations of object-manipulation tasks collected using a 3-DOF LEGO robot. The robot is equipped with an end-effector designed to flip a switch.

The dataset includes:

* Motor-position feedback from all three actuators
* RGB images from a main camera and a wrist-mounted camera
* Motor commands and halt signals
* Language instructions describing the task goal
* Complete task demonstrations from start to finish

## Table of Contents

1. [Robot Hardware](#robot-hardware)
2. [Dataset Recording](#dataset-recording)
3. [Raw Recording Format](#raw-recording-format)
4. [Train and Validation Splits](#train-and-validation-splits)
5. [RLDS Dataset Format](#rlds-dataset-format)
6. [Building the Dataset](#building-the-dataset)
7. [Dataset Schema](#dataset-schema)
8. [Data Processing](#data-processing)
9. [Usage Notes](#usage-notes)
10. [Recorded Dataset](#recorded-dataset)
11. [Loading the Dataset](#loading-the-dataset)
12. [Training Preprocessing Example](#training-preprocessing-example)
13. [Simple Iteration Example](#simple-iteration-example)

---

## Robot Hardware

### Actuators

The robot is controlled by three motors:

| Motor       | Function                                                      |
| ----------- | ------------------------------------------------------------- |
| **Motor A** | Moves the end-effector vertically up and down                 |
| **Motor B** | Rotates the arm vertically, changing the manipulator's height |
| **Motor C** | Rotates the end-effector horizontally to the left and right   |

### Sensors

The robot uses:

* Two RGB cameras:

  * Main camera
  * Wrist-mounted camera
* Camera images captured at approximately 10 Hz
* Motor-position feedback from all three actuators

---

## Dataset Recording

Episodes are produced through the UI backend located under `robot/src/`.

Recordings are initiated using a button in the frontend application. The corresponding recording logic is distributed across the backend code in `robot/src/`.

> **Important:** Recordings are not created directly with `pi_recorder.py`.

The following components are deprecated or no longer used for recording:

* The legacy `pi_recorder.py` script is deprecated.
* The `src/octolego-ees` directory is no longer used for recording.

Each recorded episode contains:

* A single manipulation task, such as `"flip the switch to the green side"`
* Continuous motor states and camera images captured at approximately 10 Hz
* Motor commands consisting of:

  * `target_positions` for motors A, B, and C
  * A halt flag
* A language instruction describing the task goal

---

## Raw Recording Format

Raw recordings created by the backend UI are saved under:

```text
robot/src/pi_recorded_data/
```

Each episode is stored in a separate directory.

### Recording Folder Structure

```text
pi_recorded_data/
├── 20260524_143022_Pi_Ep000_flip_the_switch/
│   ├── metadata.json           # Episode metadata: goal, task_id, etc.
│   ├── goal_image.pkl          # Optional goal image
│   ├── step_00000.pkl          # State and command for step 0
│   ├── step_00001.pkl
│   └── ...
├── 20260524_143500_Pi_Ep001_pick_up_ball/
│   └── ...
```

### Episode Metadata

The `metadata.json` file contains episode-level information such as:

* Task goal
* Task identifier
* Language instruction
* Recording metadata

The optional `goal_image.pkl` file stores the goal image associated with the episode.

### Step Files

Each `step_*.pkl` file contains:

* `state`

  * Motor positions
  * Camera frames
  * Timestamp
* `command`

  * Target positions for motors A, B, and C
  * Halt flag
  * Timestamp
* `language_instruction`

  * Task instruction copied from the episode metadata

---

## Train and Validation Splits

After recording, use `split_recordings.py` to organize the episodes into training and validation splits.

The script is located under:

```text
robot/src/rlds_dataset_builder
```

Run:

```bash
cd robot/src/rlds_dataset_builder/
python split_recordings.py --train-ratio 0.9 --seed 42
```

This command moves complete episode directories into:

```text
pi_recorded_data/
├── train/    # 90% of the episodes
└── val/      # 10% of the episodes
```

Episodes are **never divided between splits**. Each recording remains intact and is assigned entirely to either the training or validation split.

---

## RLDS Dataset Format

The raw recordings are converted to the **RLDS format** using TensorFlow Datasets.

This makes the dataset compatible with Octo and provides a structure analogous to datasets used for Open X-Embodiment training.

---

## Building the Dataset

From the dataset-builder directory, run:

```bash
cd robot/src/rlds_dataset_builder/switcher_dataset/
tfds build --overwrite
```

The generated TensorFlow Dataset files are written to:

```text
~/tensorflow_datasets/switcher_dataset/
```

---

## Dataset Schema

Each RLDS example represents one episode and contains:

* A sequence of steps under `steps`
* Episode-level metadata

### Per-Step Data

#### `observation`

Each step contains an `observation` dictionary with:

| Field         |           Shape | Description                                 |
| ------------- | --------------: | ------------------------------------------- |
| `image`       | `256 × 256 × 3` | RGB image from the main camera              |
| `wrist_image` | `128 × 128 × 3` | RGB image from the wrist camera             |
| `state`       |             `3` | End-effector position `(x, y, z)` in meters |

#### `action`

The action is represented as a seven-dimensional vector:

```text
[dx, dy, dz, droll, dpitch, dyaw, end_effector_flag]
```

Its components are:

| Component                 | Description                                                                                   |
| ------------------------- | --------------------------------------------------------------------------------------------- |
| `dx`, `dy`, `dz`          | Cartesian end-effector displacement between consecutive steps, in meters                      |
| `droll`, `dpitch`, `dyaw` | Unused by the 3-DOF robot and therefore set to `0.0`                                          |
| `end_effector_flag`       | Action flag; `1.0` indicates the end-effector/action flag and is used as a terminal indicator |

The termination values are:

* `0.0`: Continue the episode
* `1.0`: End the episode

#### Additional Step Fields

| Field                  | Description                                          |
| ---------------------- | ---------------------------------------------------- |
| `discount`             | Always set to `1.0`                                  |
| `reward`               | `1.0` on the final step and `0.0` otherwise          |
| `is_first`             | Indicates the first step of an episode               |
| `is_last`              | Indicates the final step of an episode               |
| `is_terminal`          | Indicates episode termination                        |
| `language_instruction` | Text description of the task                         |
| `language_embedding`   | 512-dimensional Universal Sentence Encoder embedding |

The reward is a demonstration reward and assumes successful completion at the end of an episode.

### Episode Metadata

Each episode also contains:

| Field        | Description                                      |
| ------------ | ------------------------------------------------ |
| `file_path`  | Path to the original episode directory           |
| `task_id`    | Task identifier, for example `"pick_up_ball"`    |
| `start_time` | Timestamp at which the episode recording started |

---

## Data Processing

The dataset builder, `switcher_dataset.py`, performs the following processing steps.

### 1. Episode Loading

Episode directories are loaded from:

```text
pi_recorded_data/train/
pi_recorded_data/val/
```

### 2. Image Decoding

JPEG-encoded camera frames are decoded and converted to RGB NumPy arrays.

### 3. State Extraction

The three-dimensional motor state is extracted from the raw recordings.

### 4. Action Composition

The Cartesian end-effector displacement between consecutive steps is calculated.

A seven-dimensional action vector is then created:

```text
[dx, dy, dz, 0, 0, 0, flag]
```

The Cartesian delta values are expressed in meters.

### 5. Language Embedding

Universal Sentence Encoder embeddings are generated from the task descriptions.

Each embedding contains 512 values.

### 6. Reward Assignment

The reward is set to:

* `0.0` for all intermediate steps
* `1.0` when the episode terminates

This reward structure is based on the assumption that each recorded demonstration successfully completes the task.

---

## Usage Notes

* Language instructions are repeated for every step for downstream convenience, even though they apply to the complete episode.
* Images may be variable-sized. Additional resizing or cropping can be performed using downstream transforms.
* Each episode is a complete demonstration containing the full execution of one task from start to finish.

---

## Recorded Dataset

The recorded dataset can be downloaded here:

[Switcher Dataset with 206 examples](https://tubcloud.tu-berlin.de/s/nMXSfnCNqNxdt9b)

The generated data is stored under:

```text
switcher_dataset/2.0.0/
├── dataset_info.json                                   # Dataset metadata
├── features.json                                       # Feature description
├── switcher_dataset-train.tfrecord-00000-of-00008      # Training data, shard 1 of 8
├── switcher_dataset-train.tfrecord-00001-of-00008      # Training data, shard 2 of 8
├── switcher_dataset-train.tfrecord-00002-of-00008      # Training data, shard 3 of 8
├── switcher_dataset-train.tfrecord-00003-of-00008      # Training data, shard 4 of 8
├── switcher_dataset-train.tfrecord-00004-of-00008      # Training data, shard 5 of 8
├── switcher_dataset-train.tfrecord-00005-of-00008      # Training data, shard 6 of 8
├── switcher_dataset-train.tfrecord-00006-of-00008      # Training data, shard 7 of 8
├── switcher_dataset-train.tfrecord-00007-of-00008      # Training data, shard 8 of 8
└── switcher_dataset-val.tfrecord-00000-of-00001        # Validation data
```

The training data is split across eight TFRecord shards.

---

## Loading the Dataset

Load the training and validation splits using TensorFlow Datasets:

```python
import tensorflow_datasets as tfds

ds_train = tfds.load("switcher_dataset", split="train")
ds_val = tfds.load("switcher_dataset", split="val")
```

---

## Training Preprocessing Example

The following example converts the main-camera images to `float32`, normalizes them to the range `[0, 1]`, and prepares the dataset for training.

```python
import tensorflow as tf
import tensorflow_datasets as tfds


def preprocess(example):
    example["steps"]["observation"]["image"] = tf.cast(
        example["steps"]["observation"]["image"], tf.float32
    ) / 255.0
    return example


ds_train = tfds.load("switcher_dataset", split="train")
ds_train = ds_train.map(preprocess)

batch_size = 32

ds_train = ds_train.shuffle(100)
ds_train = ds_train.batch(batch_size)
ds_train = ds_train.prefetch(tf.data.AUTOTUNE)

for episode in ds_train:
    steps = episode["steps"]

    images = steps["observation"]["image"]
    # Shape: (batch, num_steps, 256, 256, 3)

    wrist_images = steps["observation"]["wrist_image"]
    # Shape: (batch, num_steps, 128, 128, 3)

    actions = steps["action"]
    # Shape: (batch, num_steps, 7)

    states = steps["observation"]["state"]
    # Shape: (batch, num_steps, 3)

    instructions = steps["language_instruction"]
    # Text instructions
```

---

## Simple Iteration Example

The following example loads one episode and iterates over its individual steps:

```python
import tensorflow_datasets as tfds


ds = tfds.load("switcher_dataset", split="train")

for episode in ds.take(1):
    for step in episode["steps"]:
        image = step["observation"]["image"].numpy()
        # Main camera image, shape: (256, 256, 3)

        wrist_image = step["observation"]["wrist_image"].numpy()
        # Wrist camera image, shape: (128, 128, 3)

        action = step["action"].numpy()
        # [dx, dy, dz, roll, pitch, yaw, gripper]

        state = step["observation"]["state"].numpy()
        # Joint angles or end-effector state

        instruction = (
            step["language_instruction"]
            .numpy()
            .decode()
        )
```

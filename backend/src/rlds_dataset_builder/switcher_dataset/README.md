# Switcher Dataset: LEGO Robot Manipulation

This dataset contains demonstrations of object manipulation tasks collected from a 3-DOF LEGO robot equipped with an end-effector for pushing/moving objects.

## Robot Hardware

The robot is controlled by three actuators:
- **Motor A**: End-effector vertical movement (up/down)
- **Motor B**: Arm vertical rotation — changes the manipulator's height  
- **Motor C**: Horizontal rotation — rotates the end-effector left/right

**Sensors**:
- 2× RGB cameras (main camera + wrist camera), capturing 64×64 images at 30 Hz
- Motor position feedback from all 3 actuators

## Dataset Collection

Episodes are recorded using `pi_recorder.py` on a Raspberry Pi controller. Each episode captures:
- A single manipulation task (e.g., "flip the switch to the green side")
- Continuous state (motor positions) and images at ~30 Hz
- Motor commands (`target_positions` for A, B, C + halt flag)
- Language instruction describing the task goal

### Recording Folder Structure

Raw recordings are saved to `pi_recorded_data/` as episode folders:

```
pi_recorded_data/
├── 20260524_143022_Pi_Ep000_flip_the_switch/
│   ├── metadata.json           # Episode metadata (goal, task_id, etc.)
│   ├── goal_image.pkl          # Goal image (optional)
│   ├── step_00000.pkl          # State + command for step 0
│   ├── step_00001.pkl
│   └── ...
├── 20260524_143500_Pi_Ep001_pick_up_ball/
│   └── ...
```

Each `step_*.pkl` contains:
- `state`: Motor positions, camera frames, timestamp
- `command`: Target positions for A/B/C, halt flag, timestamp
- `language_instruction`: The task instruction (copied from episode metadata)

### Dataset Splits

After recording, use `split_recordings.py` to organize episodes into train/validation splits:

```bash
cd pi/
python split_recordings.py --train-ratio 0.9 --seed 42
```

This moves **whole episodes** into:
- `pi_recorded_data/train/` (90%)
- `pi_recorded_data/val/` (10%)

Episodes are **never split** — each recording stays intact.

## RLDS Dataset Format

The dataset is converted to **RLDS format** (TensorFlow Datasets) for compatibility with OpenX-embodiment training.

### Building the Dataset

From the dataset builder directory:

```bash
cd robot/octolego-ees/rlds_dataset_builder/switcher_dataset/
tfds build --overwrite
```

This creates TFRecord files in `~/tensorflow_datasets/switcher_dataset/`.

### Dataset Schema

Each RLDS example contains:

**Per-step data** (`steps`):
- `observation`:
  - `image`: 64×64×3 RGB from main camera
  - `wrist_image`: 64×64×3 RGB from wrist camera
  - `state`: 3-D vector [motor A, B, C positions] in degrees
- `action`: 4-D vector [target A, B, C positions, terminate flag]
  - Terminate flag: 0.0 = continue, 1.0 = end episode
- `discount`: 1.0 (always)
- `reward`: 1.0 on final step, 0.0 otherwise (demonstration reward)
- `is_first` / `is_last` / `is_terminal`: Episode boundary flags
- `language_instruction`: Text description of the task
- `language_embedding`: Universal Sentence Encoder embedding (512-D)

**Episode metadata**:
- `file_path`: Path to original episode folder
- `task_id`: Task identifier (e.g., "pick_up_ball")
- `start_time`: Episode recording timestamp

## Data Processing

The builder (`switcher_dataset_builder.py`) performs:

1. **Episode Loading**: Reads episode folders from `pi_recorded_data/train/` and `pi_recorded_data/val/`
2. **Image Decoding**: Converts JPEG-encoded frames to RGB numpy arrays
3. **State Extraction**: Extracts 3-DOF motor positions from raw recordings
4. **Action Composition**: Combines `target_positions` + `halt_flag` into 4-D action vector
5. **Language Embedding**: Generates universal sentence encoder embeddings for task descriptions
6. **Reward Assignment**: Sets reward = 1.0 on episode termination (demonstration assumption)

## Usage Notes

- **Language instructions** are repeated for every step (for downstream convenience) even though they're episode-wide
- **Images** are variable-sized; frame resizing/cropping can be done in downstream transforms
- Episodes are **complete demonstrations** — each contains a full task execution from start to finish

# Live Inference

This folder contains the inference client that drives the LEGO arm with a
(fine-tuned) Octo model.

- `cln.py`: the inference client
- `wrapper.py`: the OctoWrapper that loads the model and runs prediction


## Part A - How inference works

### The setup

Inference is split across two machines:

- The Web-UI (`main.py`) runs and owns the hardware. It streams live camera frames
  and telemetry, and it executes movement commands (including the inverse
  kinematics).
- `cln.py` runs the model. It connects to the Web-UI over WebSocket, pulls fresh
  camera frames, runs the Octo model, and sends target positions back.

`cln.py` sends Cartesian end-effector targets with a `moveee` command. It does not
do inverse kinematics itself; the Web-UI turns those Cartesian targets into joint
motion.

### What the model produces

Given the current camera view(s), the arm's proprioceptive state, and the language
instruction, the model predicts a sequence of per-step Cartesian deltas
(dx, dy, dz), `action_horizon` steps long. These are relative moves: each step is
added on top of the previous target.

### Receding Horizon Control (RHC)

Predicting a whole sequence and executing only the first step is not enough to
complete the motion (the arm hesitates). Executing the whole predicted sequence
blindly is also bad, because the world changes as the arm moves. RHC is the middle
ground:

1. Grab a fresh camera frame and telemetry.
2. Run the model to get a sequence of deltas.
3. Execute only the first `EXEC_HORIZON` deltas, accumulating them into absolute
   `moveee` targets (starting from the current end-effector position).
4. Throw the rest away, grab a fresh frame, and re-infer. Repeat until
   `MAX_TOTAL_STEPS`.

So the arm always acts on a recent observation, but still moves in short coherent
bursts instead of one tiny step at a time. This matches the team decision to run
the action horizon sequentially without accumulating a queue.

### Model modes and proprio

`cln.py` supports three modes through one pipeline:

- Fine-tuned: our adapted model. It uses proprioception (the arm state) as input.
- Small / Base: the raw pretrained Octo. These have no proprio input, so proprio
  is skipped automatically.

Because the raw base/small models do not know our robot, they produce erratic
motion. They are useful for comparison, not for a reliable demo.

### Consistency (why it matters)

The model must run with the same `window_size` and `action_horizon` it was trained
with. These change the input and output shapes, so a mismatch causes shape errors
or wrong predictions. The instruction must also match the one used in training.


## Part B - How to run inference

### Prerequisites

- The Web-UI (`main.py`) must be running (the client connects to it and pulls
  frames from it).
- You need a fine-tuned checkpoint: a run folder plus a step (e.g. `49999`).

### Start it

```bash
cd ~/backend/src/model
python cln.py
```

`cln.py` then asks a series of questions. Defaults are in parentheses; press Enter
to accept.

- Model mode (`s` small / `b` base / Enter = fine-tuned)
- Checkpoint path (only asked for fine-tuned): the run folder, e.g.
  `/home/lego-team-1/finetune_output/20260712_2049_small_aug_full_nowrist_w1`
- Checkpoint step (only asked for fine-tuned): e.g. `49999`
- Action gain (Enter = 2.0)
- Task type (`1` text / `2` image / Enter = 1)
- Wrist cam (`y`/`n`/Enter = yes)
- Window size: MUST match training
- Action horizon: MUST match training
- Web-UI IP (Enter = default)
- Goal / instruction: MUST match the training instruction

The defaults for checkpoint path and step are set at the top of `cln.py`
(`CHECKPOINT`, `STEP`), but you can override both at the prompts without editing
the file.

### RHC parameters

These are constants near the top of `cln.py`:

- `EXEC_HORIZON` (default 8): steps executed per inference. Higher is smoother but
  corrects less; lower corrects more but replans more (noisier).
- `STEP_DELAY` (default 0.3s): wait between `moveee` commands so the arm and camera
  can catch up.
- `MAX_TOTAL_STEPS` (default 200): safety limit on the continuous loop.

### Matching the checkpoint

Before running, check the run's `config.txt` for its `window_size` and
`action_horizon`, and enter the same values at the prompts. Also pick the model
mode that matches the checkpoint (a small run needs small mode, a base run needs
base mode).

# Fine-tuning & Evaluation

This folder contains the training and offline-evaluation code for adapting the
Octo Vision-Language-Action model to our 3-DOF LEGO arm.

- `run_finetune.sh`: Docker wrapper that launches a training run
- `finetune.py`: the actual fine-tuning script
- `eval_offline.py`: offline evaluation (base vs fine-tuned on held-out data)


## Part A - How fine-tuning works

### The idea

Octo is a large model pretrained on many robot datasets. It does not know our
robot. Fine-tuning continues training Octo on our own demonstrations so it learns
to produce the right actions for our arm and our lever task.

We do not train from scratch. We start from the pretrained Octo weights and adapt
them. This is why training is fast and needs relatively little data.

### What the model sees and predicts

- Input (observation): the primary camera view (optionally also the wrist camera),
  a language instruction (e.g. "flip the switch from green to red"), and the arm's
  proprioceptive state.
- Output (action): a sequence of `action_horizon` steps, each a 7-dim action
  (xyz + rotation + gripper). `ACTION_DIM = 7`.

### Model surgery (why some layers are re-initialised)

We change parts of Octo, so those parts cannot be copied from the pretrained
weights and are initialised fresh:

- We add a proprioception tokenizer (a LowdimObsTokenizer on the `proprio` key).
  The pretrained model has no proprio projection, so those parameters start fresh.
- We replace the action head with a DiffusionActionHead sized to our
  `action_horizon` and `ACTION_DIM`, so the head layers start fresh.

Everything that matches (the transformer, the image encoders) is loaded from the
pretrained weights via `merge_params`. At startup you will see log lines like
"Param missing in pre-trained model, skipping" and "Param with differing shape,
skipping". These are expected and confirm the proprio input and the action head
are being treated as new.

### What is frozen (full vs frozen runs)

This is worth being precise about:

- The language backbone (`hf_model`) is ALWAYS frozen. It is in Octo's default
  `frozen_keys`, so it is frozen regardless of any flag. This is standard, to
  preserve the pretrained language understanding. (This is why the startup log
  reports a large number of frozen parameters.)
- The main transformer is trained by default. Our "full" runs use
  `--freeze_transformer=False` (the default), so the transformer is trained.
- Setting `--freeze_transformer=True` additionally freezes the main transformer
  (`BlockTransformer_0`). These are our "frozen" runs, where only the heads and
  tokenizers are trained.

So "full" does not mean nothing is frozen; it means the transformer is trained
while the language backbone stays frozen (Octo default).

### Key training details (from the code)

- Action head: DiffusionActionHead with `diffusion_steps=20`,
  `n_diffusion_samples=1`. For this head, loss and MSE are the same quantity.
- Action normalization: the first 6 action dims are normalised, the gripper (7th)
  is left unnormalised (`action_normalization_mask=[True]*6 + [False]`).
- Optimizer: AdamW with cosine-decay learning rate, linear warmup, and gradient
  clipping to global norm 1.0.
- Validation runs every `eval_interval` steps over the full validation split (no
  augmentation), averaging all batches instead of one noisy batch.
- Checkpoints are saved every 5000 steps, plus a final checkpoint at the end.

### Reading the metrics (W&B)

- `loss` / MSE: same thing for the diffusion head. Use the lowest-loss checkpoint.
- `action_mae_xyz`: a coarse sanity metric computed from sampled actions. Good for
  a big base-vs-fine-tuned gap, not for splitting hairs between checkpoints.
- `grad_norm`: shows the training process, not model quality. Spikes are normal
  (clipping keeps them bounded).

### What actually matters

For real arm behaviour, the amount and consistency of the training data matters
more than the hyperparameters. A larger, cleaner dataset helps the hesitant or
jittery behaviour more than tuning `action_horizon` or `window_size`.


## Part B - How to run fine-tuning

### Quick start

```bash
cd ~/backend/src/finetuning

DATA_DIR=~/data/switcher_dataset WANDB_NAME="my_run" \
  ./run_finetune.sh --model small --nouse_wrist --action_horizon=50 --window_size=1 --batch_size=8
```

Output goes to `~/finetune_output/<timestamp>_<name>/`.

### What `run_finetune.sh` does

- Picks the dataset directory. If `DATA_DIR` is set, it uses that; otherwise it
  auto-selects the newest `~/data/switcher_*` folder. Set `DATA_DIR` explicitly
  for any dataset not named `switcher_*` (e.g. `~/data/new_datasets`), because the
  auto-selection only matches `switcher_*`.
- Mounts that host folder into the container as `/data`. This is why every
  `config.txt` shows `"data_dir": "/data"`: that is the path inside the container,
  not on the host.
- Runs `finetune.py` inside the Docker image with the flags you pass through.
- Forwards these env vars into the container: `WANDB_API_KEY`, `WANDB_MODE`,
  `WANDB_NAME`, `XLA_FLAGS`, `XLA_PYTHON_CLIENT_MEM_FRACTION`. Host env vars are
  otherwise not visible inside Docker.

### The flags you usually set

| Flag | Meaning | Default | Typical |
| --- | --- | --- | --- |
| `--model` | `small` or `base` (run_finetune.sh) | small | `small` |
| `--nouse_wrist` | train without the wrist camera | wrist on | set to drop wrist |
| `--action_horizon` | future steps predicted per step | `4` | `50` |
| `--window_size` | past timesteps the model observes | `1` | `1` |
| `--batch_size` | sequences per step (lower if OOM) | `16` | `8` |

Note the code default for `--action_horizon` is 4, so if you want 50 you must set
it explicitly.

### Other flags you can tune from the command line

These all have sensible defaults and are set the same way (e.g.
`--learning_rate=1e-4`):

| Flag | Meaning | Default |
| --- | --- | --- |
| `--train_steps` | total finetuning steps | `50000` |
| `--learning_rate` | peak LR after warmup | `3e-4` |
| `--warmup_steps` | linear LR warmup before decay | `2000` |
| `--weight_decay` | AdamW weight decay (regularization) | `0.01` |
| `--eval_interval` | validate every N steps (0 disables) | `500` |
| `--augment` | image augmentation on/off | `True` |
| `--aug_strength` | augmentation magnitude (0=none, 1=default, 2=aggressive) | `1.0` |
| `--use_proprio` | include proprioception as input | `True` |
| `--freeze_transformer` | also freeze the main transformer ("frozen" runs) | `False` |
| `--seed` | random seed (for reproducibility / variance studies) | `42` |
| `--use_wrist` | use wrist camera (`--nouse_wrist` to disable) | `True` |

To disable a boolean flag use the `--noFLAG` form, e.g. `--noaugment`,
`--nouse_proprio`.

When you run `finetune.py`, it prints the resolved config and (in an interactive
terminal) lets you edit any single setting before training starts, or press Enter
to start.

### Outputs

Each run folder contains:

- Checkpoint folders every 5000 steps: `4999`, `9999`, ... `49999`
- `config.txt`: the exact config used (the source of truth for a run)
- `config.json`, `dataset_statistics.json`, `example_batch.msgpack`: needed for inference
- `run.log`: the training log

Note: the folder NAME does not always reflect every flag (it may say `w1` even for
other window sizes). Always check `config.txt` for the real config of a run.

### Choosing config

- `action_horizon=50` fits our episodes (typical length ~130 steps).
- `window_size=1` is fine for this quasi-static task; `2` matches Octo pretraining
  but adds little here and uses more memory.
- For selecting the checkpoint to use: take the late / lowest-loss one (`49999`).


## Part C - Offline evaluation

### What it does

`eval_offline.py` compares predicted actions against ground-truth actions on a
held-out validation split. It is how we show, quantitatively, that fine-tuning
worked: the fine-tuned model's actions are much closer to ground truth than the
base model's.

### How to run

Run on the validation split, pointing at the run's checkpoint and matching the
model size. Override the old defaults explicitly:

```bash
python eval_offline.py \
  --checkpoint /home/lego-team-1/finetune_output/<run_folder> \
  --step 49999 \
  --base_id hf://rail-berkeley/octo-small-1.5 \
  --data_dir /home/lego-team-1/data/<dataset_folder> \
  --split val \
  --window_size 1
```

- `--base_id` must match the model size of the run (octo-small-1.5 for a small
  run, octo-base-1.5 for a base run).
- `--data_dir` must be the dataset the run was trained on (check its `config.txt`;
  the host path is your `~/data/...` folder, not `/data`).
- `--split val` and `--window_size` must match the run.

### Interpreting the result

The base model and the fine-tuned model are evaluated the same way. A large drop
in mean action error from base to fine-tuned is the evidence of learning. Because
`action_mae_xyz` is coarse, treat it as a clear base-vs-fine-tuned comparison, not
a precise score.

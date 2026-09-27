#!/usr/bin/env bash
#
# run_finetune.sh - one-command wrapper to launch an Octo finetune in the
# backend Docker image on themachine. Handles the docker boilerplate (mounts,
# --gpus, image pull) so you only pass finetune flags.
#
# Usage:
#   ./run_finetune.sh                       # defaults (both cameras)
#   ./run_finetune.sh --nouse_wrist         # primary camera only
#   ./run_finetune.sh --train_steps=200     # quick smoke test
#   DATA_DIR=~/my_rlds ./run_finetune.sh    # override dataset path
#
# Any flags after the command are passed straight through to
# finetune.py, so every script flag still works.

set -euo pipefail

# Overridable defaults 
IMAGE="${IMAGE:-git.tu-berlin.de:5000/ees-vla-team-1/backend:latest}"

DATA_DIR_AUTO=0
if [ -z "${DATA_DIR:-}" ]; then
  DATA_DIR=$(ls -dt "$HOME"/data/switcher_* 2>/dev/null | head -n1)
  DATA_DIR_AUTO=1
fi

DATA_DIR="${DATA_DIR:-$HOME/data/switcher_rlds}"
ROBOT_DIR="${ROBOT_DIR:-$HOME/robot}"
SCRIPT="${SCRIPT:-/workspace/robot/src/octolego-ees/finetuning/finetune.py}"
PRETRAINED="${PRETRAINED:-hf://rail-berkeley/octo-small-1.5}"
MODEL_ARG="small"
PASS_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --model=*)  MODEL_ARG="${1#*=}" ;;
    --model)    MODEL_ARG="$2"; shift ;;
    *)          PASS_ARGS+=("$1") ;;
  esac
  shift
done

case "$MODEL_ARG" in
  small) PRETRAINED="hf://rail-berkeley/octo-small-1.5"; MODEL=small ;;
  base)  PRETRAINED="hf://rail-berkeley/octo-base-1.5";  MODEL=base ;;
  *)     echo "ERROR: --model must be small or base (got: $MODEL_ARG)" >&2; exit 1 ;;
esac
ARGS="${PASS_ARGS[*]}"

if echo "$ARGS" | grep -q -- "--noaugment"; then
  AUG=noaug
else
  AUG=aug
  STR=$(echo "$ARGS" | grep -oE -- "--aug_strength=[0-9.]+" | cut -d= -f2 || true)
  [ -n "$STR" ] && [ "$STR" != "1.0" ] && AUG="aug${STR}"
fi

if echo "$ARGS" | grep -q -- "--freeze_transformer"; then FREEZE=frozen; else FREEZE=full; fi

LR=$(echo "$ARGS" | grep -oE -- "--learning_rate=[0-9.eE-]+" | cut -d= -f2 || true)
LR_TAG=""; [ -n "$LR" ] && LR_TAG="_lr${LR}"

CAM_TAG=""; echo "$ARGS" | grep -q -- "--nouse_wrist" && CAM_TAG="_nowrist"

PROP_TAG=""; echo "$ARGS" | grep -q -- "--nouse_proprio" && PROP_TAG="_noprop"

WIN=$(echo "$ARGS" | grep -oE -- "--window_size=[0-9]+" | cut -d= -f2 || true)
WIN_TAG=""; [ -n "$WIN" ] && WIN_TAG="_w${WIN}"

WD=$(echo "$ARGS" | grep -oE -- "--weight_decay=[0-9.eE-]+" | cut -d= -f2 || true)
WD_TAG=""; [ -n "$WD" ] && [ "$WD" != "0.0" ] && WD_TAG="_wd${WD}"

SEED=$(echo "$ARGS" | grep -oE -- "--seed=[0-9]+" | cut -d= -f2 || true)
SEED_TAG=""; [ -n "$SEED" ] && SEED_TAG="_s${SEED}"

WARM=$(echo "$ARGS" | grep -oE -- "--warmup_steps=[0-9]+" | cut -d= -f2 || true)
WARM_TAG=""; [ -n "$WARM" ] && WARM_TAG="_warm${WARM}"

TAG="${MODEL}_${AUG}_${FREEZE}${LR_TAG}${CAM_TAG}${PROP_TAG}${WIN_TAG}${WD_TAG}${SEED_TAG}${WARM_TAG}"
WANDB_NAME="${WANDB_NAME:-$TAG}"
export WANDB_NAME
SAVE_DIR="${SAVE_DIR:-$HOME/finetune_output/$(date +%Y%m%d_%H%M)_${TAG}}"

# Guard checks: fail early with a clear message
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found on this machine." >&2
  exit 1
fi
if [ ! -d "$DATA_DIR" ]; then
  echo "ERROR: dataset dir not found: $DATA_DIR" >&2
  echo "  Set DATA_DIR=/path/to/built_tfds (must contain switcher_dataset/2.0.0/*.tfrecord)" >&2
  exit 1
fi
if [ ! -d "$ROBOT_DIR/.git" ]; then
  echo "ERROR: robot repo not found at $ROBOT_DIR (set ROBOT_DIR)." >&2
  exit 1
fi

mkdir -p "$SAVE_DIR"

ROBOT_SHA="unknown"
if [ -d "$ROBOT_DIR/.git" ]; then
  ROBOT_SHA=$(cd "$ROBOT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo unknown)
fi

echo "=================================================="
echo "  image     : $IMAGE"
echo "  data_dir  : $DATA_DIR  -> /data"
if [ "$DATA_DIR_AUTO" = "1" ]; then
  echo "              (auto-selected newest; override with DATA_DIR=...)"
fi
echo "  robot     : $ROBOT_DIR -> /workspace/robot"
echo "  robot_sha : $ROBOT_SHA"
echo "  save_dir  : $SAVE_DIR  -> /save"
echo "  extra args: ${PASS_ARGS[*]}"
echo "=================================================="


echo "Pulling latest image..."
docker pull "$IMAGE" || echo "WARNING: pull failed, using local image if present."


docker run --rm --gpus all \
  -e WANDB_API_KEY \
  -e WANDB_MODE \
  -e WANDB_NAME \
  -e XLA_FLAGS \
  -e XLA_PYTHON_CLIENT_MEM_FRACTION \
  -v "$DATA_DIR":/data \
  -v "$ROBOT_DIR":/workspace/robot \
  -v "$SAVE_DIR":/save \
  "$IMAGE" \
  python "$SCRIPT" \
    --pretrained_path="$PRETRAINED" \
    --data_dir=/data \
    --save_dir=/save \
    "${PASS_ARGS[@]}" 2>&1 | tee "$SAVE_DIR/run.log"
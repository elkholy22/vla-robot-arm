#!/usr/bin/env bash


# run_ablation.sh : so this code here runs a big sweep of finetuning runs with different flags to do an ablation study. Each run is launched in sequence and will be named by its config. At the end, you should have a big collection of runs in the save directory that you can analyze to understand which design decisions matter most for performance. You can also add/remove runs from this script as you see fit. 


# Usage:  ./run_ablation.sh

set -uo pipefail   # NOT -e: one failed run must not kill the whole sweep
cd "$(dirname "$0")"

run() {
  echo ">>> $* $(date +%H:%M)"
  ./run_finetune.sh "$@" < /dev/null || echo "!!! FAILED: $* (continuing)"
}

# one-axis sweep
run
run --noaugment
run --aug_strength=0.5
run --aug_strength=2.0
run --freeze_transformer
run --learning_rate=1e-5
run --learning_rate=1e-4
run --nouse_wrist
run --nouse_proprio
run --window_size=1
run --window_size=3
run --weight_decay=0.01
run --weight_decay=0.1
run --warmup_steps=500

# seed variance
run --seed=42
run --seed=7

# base model
run --model base
run --model base --freeze_transformer
run --model base --weight_decay=0.01
run --model base --noaugment

# regularizer interactions
run --freeze_transformer --weight_decay=0.01
run --noaugment --freeze_transformer
run --freeze_transformer --learning_rate=1e-4
run --weight_decay=0.1 --aug_strength=2.0
run --nouse_wrist --nouse_proprio
run --window_size=3 --freeze_transformer

echo "=== ABLATION COMPLETE $(date +%H:%M) ==="
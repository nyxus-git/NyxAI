#!/usr/bin/env bash
set -euo pipefail

# Overnight QLoRA Fine-Tuning Runner for NyxAI
# Usage:
#   ./training/scripts/run_overnight.sh
#   MODEL_ID=Qwen/Qwen2.5-7B-Instruct ./training/scripts/run_overnight.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-3B-Instruct}"
EPOCHS="${EPOCHS:-3}"
MAX_SEQ_LEN="${MAX_SEQ_LEN:-1024}"
OUTPUT_DIR="${OUTPUT_DIR:-training/experiments/nyxai-lora}"
LOG_FILE="training/experiments/train_$(date +%Y%m%d_%H%M%S).log"

mkdir -p training/experiments

echo "=== NyxAI Overnight QLoRA Setup ==="
echo "Model:       $MODEL_ID"
echo "Epochs:      $EPOCHS"
echo "Max Seq Len: $MAX_SEQ_LEN"
echo "Output Dir:  $OUTPUT_DIR"
echo "Log File:    $LOG_FILE"

# 1. Free VRAM from any loaded Ollama models
if command -v ollama >/dev/null 2>&1; then
    echo "Stopping loaded Ollama models to free VRAM..."
    for m in $(ollama ps 2>/dev/null | awk 'NR>1 {print $1}'); do
        ollama stop "$m" || true
    done
fi

# 2. Rebuild and validate dataset
echo "Building and validating dataset..."
.venv/bin/python training/scripts/dataset_builder.py
.venv/bin/python training/scripts/validate_dataset.py --input training/datasets/processed/train.jsonl
.venv/bin/python training/scripts/validate_dataset.py --input training/datasets/processed/val.jsonl

# 3. Start QLoRA training
echo "Starting QLoRA training (logging to $LOG_FILE)..."
.venv/bin/python training/scripts/train_lora.py \
    --model_id "$MODEL_ID" \
    --data_path training/datasets/processed/train.jsonl \
    --val_path training/datasets/processed/val.jsonl \
    --output_dir "$OUTPUT_DIR" \
    --epochs "$EPOCHS" \
    --max_seq_len "$MAX_SEQ_LEN" \
    2>&1 | tee "$LOG_FILE"

echo "=== Training Complete! Adapters saved to $OUTPUT_DIR ==="


"""
training/scripts/evaluate.py

Script to evaluate the fine-tuned model's tool calling accuracy.
Reads a JSONL evaluation dataset, extracts the expected assistant response,
prompts the model with the user/system context, and compares the output.

Usage:
    python training/scripts/evaluate.py \
        --model Qwen/Qwen2.5-3B-Instruct \
        --adapter training/experiments/nyxai-lora \
        --eval_data training/datasets/processed/eval.jsonl
"""

import os
import json
import argparse
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def load_eval_data(file_path):
    dataset = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    dataset.append(data["messages"])
                except Exception as e:
                    print(f"Error parsing line: {e}")
    return dataset

def main():
    parser = argparse.ArgumentParser(description="Evaluate tool calling accuracy")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-3B-Instruct", help="Base model ID")
    parser.add_argument("--adapter", type=str, default=None, help="Path to LoRA adapters (optional)")
    parser.add_argument("--eval_data", type=str, default="training/datasets/processed/eval.jsonl", help="Evaluation dataset")

    args = parser.parse_args()

    if not os.path.exists(args.eval_data):
        print(f"Evaluation data not found at {args.eval_data}")
        return

    print("Loading model in FP16 (or 4-bit if needed, here FP16 for speed)...")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        device_map="auto",
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )

    if args.adapter and os.path.exists(args.adapter):
        print(f"Loading LoRA adapters from {args.adapter}...")
        model = PeftModel.from_pretrained(model, args.adapter)
        model = model.merge_and_unload()
    else:
        print("No adapters provided. Evaluating BASE model.")

    eval_data = load_eval_data(args.eval_data)
    print(f"Loaded {len(eval_data)} evaluation samples.")

    correct = 0
    total = len(eval_data)
    total_time = 0.0

    print("\n--- Starting Evaluation ---")
    for idx, messages in enumerate(eval_data):
        # Extract the ground truth assistant message (last message)
        if messages[-1]["role"] != "assistant":
            print(f"Sample {idx}: Last message is not 'assistant'. Skipping.")
            total -= 1
            continue
            
        ground_truth = messages[-1]["content"].strip()
        
        # Prepare the prompt without the assistant's response
        prompt_messages = messages[:-1]
        
        prompt_text = tokenizer.apply_chat_template(
            prompt_messages, tokenize=False, add_generation_prompt=True
        )
        
        inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)
        
        start_time = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=150,
                temperature=0.1,  # Low temp for deterministic tool calling
                pad_token_id=tokenizer.eos_token_id
            )
        elapsed = time.time() - start_time
        total_time += elapsed

        # Extract only the newly generated tokens
        generated_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
        prediction = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

        # Simple string matching for evaluation (could be replaced by JSON schema matching)
        is_correct = ground_truth in prediction or prediction in ground_truth

        if is_correct:
            correct += 1
            print(f"[{idx+1}/{total}] ✅ PASS ({elapsed:.2f}s)")
        else:
            print(f"[{idx+1}/{total}] ❌ FAIL ({elapsed:.2f}s)")
            print(f"   Expected: {ground_truth}")
            print(f"   Got:      {prediction}")

    accuracy = (correct / total) * 100 if total > 0 else 0
    avg_time = total_time / total if total > 0 else 0

    print("\n--- Evaluation Results ---")
    print(f"Total Samples: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.2f}%")
    print(f"Average Latency: {avg_time:.2f}s/sample")

if __name__ == "__main__":
    main()

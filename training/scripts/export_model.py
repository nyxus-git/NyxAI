"""
training/scripts/export_model.py

Script to merge the trained LoRA adapters back into the base model 
and save it as a standalone HuggingFace model.
The merged model can later be converted to GGUF format for Ollama usage.

Usage:
    python training/scripts/export_model.py \
        --base_model Qwen/Qwen2.5-3B-Instruct \
        --adapter_dir training/experiments/nyxai-lora \
        --output_dir training/experiments/nyxai-merged
"""

import os
import argparse
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def main():
    parser = argparse.ArgumentParser(description="Merge LoRA adapters into base model")
    parser.add_argument("--base_model", type=str, default="Qwen/Qwen2.5-3B-Instruct", help="HuggingFace base model ID")
    parser.add_argument("--adapter_dir", type=str, default="training/experiments/nyxai-lora", help="Path to trained LoRA adapters")
    parser.add_argument("--output_dir", type=str, default="training/experiments/nyxai-merged", help="Output directory for merged model")

    args = parser.parse_args()

    if not os.path.exists(args.adapter_dir):
        print(f"Error: Adapter directory '{args.adapter_dir}' does not exist.")
        return

    print(f"Loading base model '{args.base_model}' in FP16...")
    # Load the base model in fp16 to ensure we can merge without bitsandbytes limitations
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float16,
        device_map="cpu",  # Loading on CPU since we just need to merge and save
        trust_remote_code=True,
    )

    print(f"Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)

    print(f"Loading PeftModel from '{args.adapter_dir}'...")
    peft_model = PeftModel.from_pretrained(
        base_model,
        args.adapter_dir,
        torch_dtype=torch.float16,
    )

    print("Merging adapters into base model weights...")
    merged_model = peft_model.merge_and_unload()

    print(f"Saving merged model to '{args.output_dir}'...")
    os.makedirs(args.output_dir, exist_ok=True)
    merged_model.save_pretrained(args.output_dir, max_shard_size="2GB")
    tokenizer.save_pretrained(args.output_dir)

    print("Success! The model is now ready to be converted to GGUF for Ollama.")
    print("Example conversion command using llama.cpp:")
    print(f"  python3 /path/to/llama.cpp/convert_hf_to_gguf.py {args.output_dir} --outfile nyxai-3b-q4_k_m.gguf --outtype q8_0")

if __name__ == "__main__":
    main()

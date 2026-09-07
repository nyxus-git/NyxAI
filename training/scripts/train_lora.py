"""
training/scripts/train_lora.py

Script to fine-tune the NyxAI model using QLoRA.
Designed to run on a 6GB VRAM GPU (e.g., RTX 4050) by aggressively utilizing:
- 4-bit quantization (BitsAndBytes)
- Gradient Checkpointing
- Small batch size + Gradient Accumulation
- Parameter-Efficient Fine-Tuning (LoRA)

Usage:
    python training/scripts/train_lora.py --model_id Qwen/Qwen2.5-3B-Instruct --data_path training/datasets/processed/train.jsonl
"""

import os
import argparse
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig

def main():
    parser = argparse.ArgumentParser(description="Fine-tune NyxAI using QLoRA")
    parser.add_argument("--model_id", type=str, default="Qwen/Qwen2.5-3B-Instruct", help="HuggingFace model ID")
    parser.add_argument("--data_path", type=str, default="training/datasets/processed/train.jsonl", help="Path to JSONL dataset")
    parser.add_argument("--output_dir", type=str, default="training/experiments/nyxai-lora", help="Output directory for LoRA adapters")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=1, help="Per-device micro-batch size")
    parser.add_argument("--grad_accum", type=int, default=8, help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--max_seq_len", type=int, default=1024, help="Maximum sequence length to save VRAM")

    args = parser.parse_args()

    if not os.path.exists(args.data_path):
        print(f"Dataset not found at {args.data_path}")
        return

    print("Loading dataset...")
    # The dataset format expects a 'messages' column
    dataset = load_dataset("json", data_files={"train": args.data_path})

    print(f"Configuring 4-bit quantization for VRAM optimization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )

    print(f"Loading tokenizer and model: {args.model_id}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    # Prepare model for k-bit training
    model = prepare_model_for_kbit_training(model)

    print("Configuring LoRA...")
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    def format_chat_template(example):
        example["text"] = tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )
        return example

    print("Applying chat template formatting...")
    dataset = dataset.map(format_chat_template)

    print("Setting up training arguments...")
    training_args = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        max_grad_norm=0.3,
        warmup_ratio=0.03,
        logging_steps=10,
        save_strategy="epoch",
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        max_seq_length=args.max_seq_len,
        dataset_text_field="text",
    )

    print("Initializing SFTTrainer...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset["train"],
        args=training_args,
        tokenizer=tokenizer,
    )

    # Mute warnings from gradient checkpointing
    model.config.use_cache = False

    print("Starting training...")
    trainer.train()

    print(f"Saving fine-tuned adapters to {args.output_dir}")
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print("Done!")

if __name__ == "__main__":
    main()

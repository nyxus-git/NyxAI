"""
training/scripts/dataset_builder.py

Utility script to compile raw dialogue data into HuggingFace JSONL format.
The output format is:
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

Usage:
    python training/scripts/dataset_builder.py --input training/datasets/raw/ --output training/datasets/processed/train.jsonl
"""

import json
import os
import argparse
from pathlib import Path

DEFAULT_SYSTEM_PROMPT = (
    "You are NyxAI, a local-first AI companion and intelligent desktop agent designed for Linux. "
    "You communicate in English, Hindi, Marathi, and Hinglish. "
    "You are friendly, helpful, and capable of executing desktop automation tools."
)

def create_message_block(user_text: str, assistant_text: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> dict:
    """Create a single conversation block."""
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text}
        ]
    }

def process_raw_file(file_path: Path) -> list[dict]:
    """
    Process a single raw file.
    Assumes a format of a list of dicts: [{"user": "...", "assistant": "...", "system": "(optional)..."}]
    """
    dataset = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                print(f"Warning: {file_path} is not a JSON list. Skipping.")
                return []
            
            for item in data:
                if "user" in item and "assistant" in item:
                    sys_prompt = item.get("system", DEFAULT_SYSTEM_PROMPT)
                    dataset.append(create_message_block(item["user"], item["assistant"], sys_prompt))
                else:
                    print(f"Warning: Skipping invalid item in {file_path}: {item}")
    except json.JSONDecodeError as e:
        print(f"Error parsing {file_path}: {e}")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return dataset

def main():
    parser = argparse.ArgumentParser(description="Build JSONL dataset for fine-tuning")
    parser.add_argument("--input", type=str, default="training/datasets/raw", help="Input directory containing raw JSON files")
    parser.add_argument("--output", type=str, default="training/datasets/processed/train.jsonl", help="Output JSONL file path")
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_file = Path(args.output)
    
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input directory {input_dir} does not exist.")
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    all_conversations = []
    
    print(f"Scanning for JSON files in {input_dir}...")
    for file_path in input_dir.glob("*.json"):
        print(f"Processing {file_path.name}...")
        conversations = process_raw_file(file_path)
        all_conversations.extend(conversations)
        
    print(f"Total conversations collected: {len(all_conversations)}")
    
    if all_conversations:
        with open(output_file, "w", encoding="utf-8") as f:
            for conv in all_conversations:
                f.write(json.dumps(conv, ensure_ascii=False) + "\n")
        print(f"Successfully wrote {len(all_conversations)} records to {output_file}")
    else:
        print("No valid conversations found. Dataset not created.")

if __name__ == "__main__":
    main()

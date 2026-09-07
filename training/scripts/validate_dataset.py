"""
training/scripts/validate_dataset.py

Utility script to validate a HuggingFace JSONL dataset before training.
Checks:
- Valid JSONL format.
- Presence of "messages" array.
- Each message contains "role" and "content".
- Valid roles: "system", "user", "assistant".
- Basic statistics (e.g., number of conversations, max messages per convo).

Usage:
    python training/scripts/validate_dataset.py --input training/datasets/processed/train.jsonl
"""

import json
import argparse
from pathlib import Path

def validate_dataset(file_path: Path):
    if not file_path.exists():
        print(f"Error: Dataset file {file_path} not found.")
        return

    valid_roles = {"system", "user", "assistant"}
    num_conversations = 0
    errors = 0
    max_messages = 0
    total_messages = 0

    print(f"Validating {file_path}...\n")

    with open(file_path, "r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Line {line_idx}: JSON Decode Error - {e}")
                errors += 1
                continue

            if "messages" not in data:
                print(f"Line {line_idx}: Missing 'messages' key.")
                errors += 1
                continue

            messages = data["messages"]
            if not isinstance(messages, list):
                print(f"Line {line_idx}: 'messages' must be a list.")
                errors += 1
                continue

            num_conversations += 1
            total_messages += len(messages)
            max_messages = max(max_messages, len(messages))

            for msg_idx, msg in enumerate(messages):
                if not isinstance(msg, dict):
                    print(f"Line {line_idx}, Msg {msg_idx}: Message is not a dict.")
                    errors += 1
                    continue
                
                if "role" not in msg or "content" not in msg:
                    print(f"Line {line_idx}, Msg {msg_idx}: Missing 'role' or 'content'.")
                    errors += 1
                    continue
                
                if msg["role"] not in valid_roles:
                    print(f"Line {line_idx}, Msg {msg_idx}: Invalid role '{msg['role']}'. Must be one of {valid_roles}.")
                    errors += 1

    print("--- Validation Results ---")
    print(f"Total Conversations: {num_conversations}")
    print(f"Total Messages: {total_messages}")
    print(f"Max Messages in a Conversation: {max_messages}")
    print(f"Total Errors Found: {errors}")
    
    if errors == 0:
        print("\n✅ Dataset is valid and ready for training!")
    else:
        print("\n❌ Dataset has errors. Please fix them before training.")

def main():
    parser = argparse.ArgumentParser(description="Validate JSONL dataset for fine-tuning")
    parser.add_argument("--input", type=str, default="training/datasets/processed/train.jsonl", help="Input JSONL file path")
    args = parser.parse_args()
    
    validate_dataset(Path(args.input))

if __name__ == "__main__":
    main()

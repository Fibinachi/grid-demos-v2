#!/usr/bin/env python3
import json
import os
from pathlib import Path

CHUNKS_DIR = Path("E:/grid/data/directories/chunks")
OUTPUT_DIR = CHUNKS_DIR / "split"
OUTPUT_DIR.mkdir(exist_ok=True)

for chunk_file in sorted(CHUNKS_DIR.glob("chunk_*.json")):
    with open(chunk_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chunk_name = chunk_file.stem
    for i, start in enumerate(range(0, len(data), 5000), 1):
        end = start + 5000
        chunk_data = data[start:end]
        out_file = OUTPUT_DIR / f"{chunk_name}_part{i}.json"
        with open(out_file, 'w') as f:
            json.dump(chunk_data, f)
        print(f"Created {out_file.name}: {len(chunk_data)} lines")

print("Done splitting chunks into 5000-line segments")
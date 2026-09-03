#!/usr/bin/env python3
"""
Create 25K-line chunks from formatted files - streaming all years.

Usage:
    python scripts/ingest/_create_all_chunks.py --lines 25000
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
CHUNK_DIR = Path("E:/grid/data/directories/chunks")

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--lines', type=int, default=25000)
    args = ap.parse_args()
    
    CHUNK_DIR.mkdir(exist_ok=True)
    
    # Remove old chunks
    for f in CHUNK_DIR.glob("chunk_*.json"):
        f.unlink()
    
    # Collect years
    years = set()
    for f in RAW_DIR.glob('*_formatted.txt'):
        try:
            name = f.stem
            if name.startswith('catholic_dir_'):
                name = name.replace('catholic_dir_', '')
            years.add(int(name.split('_')[0]))
        except:
            pass
    
    chunk_num = 1
    chunk = []
    
    for y in sorted(years):
        fp = RAW_DIR / f"{y}_formatted.txt"
        if not fp.exists():
            fp = RAW_DIR / f"catholic_dir_{y}_formatted.txt"
        if not fp.exists():
            continue
        
        text = fp.read_text(encoding='utf-8', errors='replace')
        text = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', text)  # Join hyphens
        
        for line in text.splitlines():
            line = re.sub(r'\s+', ' ', line.strip())
            if len(line) > 3:
                chunk.append((y, line))
                
                if len(chunk) >= args.lines:
                    out = CHUNK_DIR / f"chunk_{chunk_num:03d}.json"
                    out.write_text(json.dumps(chunk, ensure_ascii=False), encoding='utf-8')
                    print(f"Chunk {chunk_num:03d}: {len(chunk)} lines")
                    chunk = []
                    chunk_num += 1
        
        # Progress indicator
        if y % 10 == 0:
            print(f"  Year {y} done (chunk {chunk_num})")
    
    # Final chunk
    if chunk:
        out = CHUNK_DIR / f"chunk_{chunk_num:03d}.json"
        out.write_text(json.dumps(chunk, ensure_ascii=False), encoding='utf-8')
        print(f"Chunk {chunk_num:03d}: {len(chunk)} lines (final)")
    
    print(f"\nDone. Total chunks: {chunk_num}")

if __name__ == '__main__':
    main()
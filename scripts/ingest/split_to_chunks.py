#!/usr/bin/env python3
"""
Split cleaned years into 25K-line chunks for review.

Usage:
    python scripts/ingest/split_to_chunks.py --year 1872 --lines 25000
    python scripts/ingest/split_to_chunks.py --all --lines 25000
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def get_lines(year):
    fp = RAW_DIR / f"{year}_formatted.txt"
    if not fp.exists():
        fp = RAW_DIR / f"catholic_dir_{year}_formatted.txt"
    if not fp.exists():
        return []
    
    text = fp.read_text(encoding='utf-8', errors='replace')
    lines = []
    
    for line in text.splitlines():
        line = re.sub(r'\s+', ' ', line.strip())
        if len(line) > 5:
            lines.append(line)
    
    return lines

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
    p.add_argument('--lines', type=int, default=25000, help='Lines per chunk')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        lines = get_lines(args.year)
        out = OUTPUT_DIR / f"year_{args.year}.json"
        out.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{args.year}: {len(lines)} lines saved")
        return
    
    if args.all:
        # Remove existing chunks
        for f in OUTPUT_DIR.glob("chunk_*.json"):
            f.unlink()
        
        # Collect all (year, line) pairs
        all_lines = []
        years = set()
        for f in RAW_DIR.glob('*_formatted.txt'):
            try:
                name = f.stem
                if name.startswith('catholic_dir_'):
                    name = name.replace('catholic_dir_', '')
                years.add(int(name.split('_')[0]))
            except:
                pass
        
        for y in sorted(years):
            lines = get_lines(y)
            if lines:
                all_lines.extend([(y, line) for line in lines])
                print(f"Year {y}: {len(lines)} lines")
        
        total = len(all_lines)
        print(f"\nTotal: {total} lines")
        
        # Split into chunks
        for i in range(0, total, args.lines):
            chunk = all_lines[i:i + args.lines]
            chunk_num = i // args.lines + 1
            out = OUTPUT_DIR / f"chunk_{chunk_num:03d}.json"
            out.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"{out.name}: {len(chunk)} lines")

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Create 25K-line chunks from formatted files for systematic re-processing.

Usage:
    python scripts/ingest/_create_chunks_for_years.py --year 1872 --lines 25000
    python scripts/ingest/_create_chunks_for_years.py --all --lines 25000
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
CHUNK_DIR = Path("E:/grid/data/directories/chunks")

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, help='Process single year')
    ap.add_argument('--all', action='store_true', help='Process all years')
    ap.add_argument('--lines', type=int, default=25000, help='Lines per chunk')
    args = ap.parse_args()
    
    CHUNK_DIR.mkdir(exist_ok=True)
    
    if args.all:
        # Collect all years
        years = set()
        for f in RAW_DIR.glob('*_formatted.txt'):
            try:
                name = f.stem
                if name.startswith('catholic_dir_'):
                    name = name.replace('catholic_dir_', '')
                years.add(int(name.split('_')[0]))
            except:
                pass
        
        # Remove old chunks
        for f in CHUNK_DIR.glob("chunk_*.json"):
            f.unlink()
        
        all_lines = []
        for y in sorted(years):
            fp = RAW_DIR / f"{y}_formatted.txt"
            if not fp.exists():
                fp = RAW_DIR / f"catholic_dir_{y}_formatted.txt"
            if not fp.exists():
                continue
            
            text = fp.read_text(encoding='utf-8', errors='replace')
            # Join hyphenated line breaks
            text = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', text)
            
            for line in text.splitlines():
                line = re.sub(r'\s+', ' ', line.strip())
                if len(line) > 3:
                    all_lines.append((y, line))
            print(f"  {y}: {len([l for l in all_lines if l[0]==y])} lines")
        
        total = len(all_lines)
        print(f"\nTotal {total:,} lines")
        
        # Split into chunks
        chunk_num = 1
        for i in range(0, total, args.lines):
            chunk = all_lines[i:i + args.lines]
            if chunk:
                out = CHUNK_DIR / f"chunk_{chunk_num:03d}.json"
                out.write_text(json.dumps(chunk, ensure_ascii=False), encoding='utf-8')
                print(f"  {out.name}: {len(chunk)} lines")
                chunk_num += 1
    
    elif args.year:
        y = args.year
        fp = RAW_DIR / f"{y}_formatted.txt"
        if not fp.exists():
            fp = RAW_DIR / f"catholic_dir_{y}_formatted.txt"
        if not fp.exists():
            print(f"Not found: {y}_formatted.txt")
            return
        
        text = fp.read_text(encoding='utf-8', errors='replace')
        # Join hyphenated line breaks
        text = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', text)
        
        lines = []
        for line in text.splitlines():
            line = re.sub(r'\s+', ' ', line.strip())
            if len(line) > 3:
                lines.append((y, line))
        
        # Save as single file
        out = CHUNK_DIR / f"year_{y}.json"
        out.write_text(json.dumps(lines, ensure_ascii=False), encoding='utf-8')
        print(f"  {y}: {len(lines)} lines → {out.name}")

if __name__ == '__main__':
    main()
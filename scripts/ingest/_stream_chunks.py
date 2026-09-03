#!/usr/bin/env python3
"""
Create 25K-line chunks from formatted files - streaming approach.

Usage:
    python scripts/ingest/_stream_chunks.py --year 1872 --lines 25000
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
CHUNK_DIR = Path("E:/grid/data/directories/chunks")

def stream_lines():
    """Stream lines from all years without loading all into memory."""
    years = set()
    for f in RAW_DIR.glob('*_formatted.txt'):
        try:
            name = f.stem
            if name.startswith('catholic_dir_'):
                name = name.replace('catholic_dir_', '')
            years.add(int(name.split('_')[0]))
        except:
            pass
    return sorted(years)

def get_year_lines(year):
    """Get lines for a single year."""
    fp = RAW_DIR / f"{year}_formatted.txt"
    if not fp.exists():
        fp = RAW_DIR / f"catholic_dir_{year}_formatted.txt"
    if not fp.exists():
        return []
    
    text = fp.read_text(encoding='utf-8', errors='replace')
    text = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', text)  # Join hyphens
    
    lines = []
    for line in text.splitlines():
        line = re.sub(r'\s+', ' ', line.strip())
        if len(line) > 3:
            lines.append((year, line))
    return lines

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, help='Process single year')
    ap.add_argument('--lines', type=int, default=25000, help='Lines per chunk')
    args = ap.parse_args()
    
    CHUNK_DIR.mkdir(exist_ok=True)
    
    if args.year:
        lines = get_year_lines(args.year)
        out = CHUNK_DIR / f"year_{args.year}.json"
        out.write_text(json.dumps(lines, ensure_ascii=False), encoding='utf-8')
        print(f"{args.year}: {len(lines)} lines saved to {out.name}")

if __name__ == '__main__':
    main()
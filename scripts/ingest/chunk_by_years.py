#!/usr/bin/env python3
"""
Break years into manageable chunks.
Process 5 years at a time, save as separate files.

Usage:
    python scripts/ingest/chunk_by_years.py --chunk 1   # Years 1-5 (1833-1834, 1836-1839)
    python scripts/ingest/chunk_by_years.py --chunk 2   # Years 6-10
"""

import re
import json
from pathlib import Path
from collections import defaultdict

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def fix_hyphens(text):
    """Fix line-break word splits."""
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
    return text

def fix_odd_chars(text):
    """Fix odd characters from OCR."""
    text = text.replace('�', '')
    text = re.sub(r'[—–]+', '-', text)
    text = re.sub(r'[�]+', '', text)
    return text

def process_years(year_list):
    """Process a list of years into a chunk."""
    all_entries = []
    
    for year in year_list:
        fp = RAW_DIR / f"{year}_formatted.txt"
        if not fp.exists():
            fp = RAW_DIR / f"catholic_dir_{year}_formatted.txt"
        if not fp.exists():
            continue
        
        text = fp.read_text(encoding='utf-8', errors='replace')
        text = fix_hyphens(text)
        text = fix_odd_chars(text)
        
        # Normalize lines
        lines = [' '.join(line.split()) for line in text.splitlines() if len(line.strip()) > 3]
        
        # Save chunk
        chunk_name = f"chunk_{min(year_list)}_{max(year_list)}.txt"
        all_entries.extend([(year, line) for line in lines])
    
    return all_entries

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--chunk', type=int, required=True, help='Chunk number (1-based)')
    p.add_argument('--size', type=int, default=5, help='Years per chunk')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Get all years
    years = []
    for f in RAW_DIR.glob('*_formatted.txt'):
        try:
            name = f.stem
            if name.startswith('catholic_dir_'):
                name = name.replace('catholic_dir_', '')
            years.append(int(name.split('_')[0]))
        except:
            pass
    
    years = sorted(set(years))
    
    # Get chunk
    start = (args.chunk - 1) * args.size
    end = start + args.size
    chunk_years = years[start:end]
    
    if not chunk_years:
        print(f"No years in chunk {args.chunk}")
        return
    
    print(f"Chunk {args.chunk}: Years {chunk_years}")
    entries = process_years(chunk_years)
    
    # Save as JSON lines (year, line)
    out = OUTPUT_DIR / f"chunk_{args.chunk}_{args.size}.json"
    
    # Group by year
    by_year = defaultdict(list)
    for year, line in entries:
        by_year[year].append(line)
    
    out.write_text(json.dumps(dict(by_year), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved {len(entries)} lines from {len(chunk_years)} years to {out}")

if __name__ == '__main__':
    main()
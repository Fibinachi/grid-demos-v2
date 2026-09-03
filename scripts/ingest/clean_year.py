#!/usr/bin/env python3
"""
Process individual years into clean JSON files.
Each year gets its own cleaned file.

Creates:
- YYYY_cleaned.json - All lines with OCR fixes applied
- YYYY_churches.json - Extracted church entries only

Usage:
    python scripts/ingest/clean_year.py --year 1833
    python scripts/ingest/clean_year.py --range 1833-1837
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def fix_hyphens(line):
    """Fix hyphenated word breaks."""
    return re.sub(r'(\w)-\s*(\w)', r'\1\2', line)

def fix_ocr_artifacts(line):
    """Clean OCR artifacts."""
    line = re.sub(r'[—–]+', '-', line)
    line = line.replace('�', "'")
    line = re.sub(r'\s+', ' ', line)
    return line.strip()

def extract_churches(lines, year):
    """Extract church entries."""
    churches = []
    for line in lines:
        if re.search(r'(?:St\.|Cathedral|Chapel|Church|Immaculate|Assumption|Holy Trinity)\s+', line, re.I):
            churches.append(line.strip())
    return churches

def process_year(year):
    fp = RAW_DIR / f"{year}_formatted.txt"
    if not fp.exists():
        fp = RAW_DIR / f"catholic_dir_{year}_formatted.txt"
    if not fp.exists():
        return None, None
    
    text = fp.read_text(encoding='utf-8', errors='replace')
    
    # Fix and clean
    lines = []
    for line in text.splitlines():
        line = fix_hyphens(line)
        line = fix_ocr_artifacts(line)
        if len(line) > 5:
            lines.append(line)
    
    churches = extract_churches(lines, year)
    
    return lines, churches

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int, help='Single year')
    p.add_argument('--range', help='Range like 1833-1837')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        years = [args.year]
    elif args.range:
        start, end = map(int, args.range.split('-'))
        years = list(range(start, end + 1))
    else:
        print("Use --year YYYY or --range YYYY-YYYY")
        return
    
    for y in years:
        lines, churches = process_year(y)
        if lines:
            # Save cleaned lines
            out = OUTPUT_DIR / f"{y}_lines.json"
            out.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding='utf-8')
            
            # Save churches
            ch_out = OUTPUT_DIR / f"{y}_churches.json"
            ch_out.write_text(json.dumps(churches, ensure_ascii=False, indent=2), encoding='utf-8')
            
            print(f"{y}: {len(lines)} lines, {len(churches)} churches")

if __name__ == '__main__':
    main()
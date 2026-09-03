#!/usr/bin/env python3
"""
Final cleanup: Fix all OCR spacing and word-break issues in formatted files.
Processes all 140 formatted files.
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def fix_spacing(text):
    """Fix OCR spacing issues - normalize all whitespace."""
    # Replace multiple spaces with single space
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text

def fix_word_breaks(text):
    """Fix hyphenated and broken words from OCR."""
    # Common OCR word splits
    fixes = [
        (r'\bcon\-?\s*crat', 'consecrated'),
        (r'\btrans\-?\s*lat', 'translated'),
        (r'\ben\-?\s*com', 'encamped'),
        (r'\barch\-?\s*dioce', 'archdiocese'),
        (r'\bdi\-?\s*oces', 'diocese'),
        (r'\bpro\-?\s*vin', 'province'),
        (r'\bvery\s+rev\.', 'very rev.'),
        (r'\brt\.\s*rev\.', 'rt. rev.'),
    ]
    for pattern, replacement in fixes:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def clean_text(text):
    """Clean OCR issues."""
    # Fix spacing
    lines = []
    for line in text.splitlines():
        line = ' '.join(line.split())  # Normalize whitespace
        lines.append(line)
    
    text = '\n'.join(lines)
    
    # Fix word breaks
    text = fix_word_breaks(text)
    
    # Remove trailing artifacts
    text = re.sub(r'\s*[\|\-—–=_]{2,}$', '', text, flags=re.MULTILINE)
    
    return text

def extract_entries(text, year):
    """Extract clean church entries."""
    entries = []
    
    # Split by double newlines (paragraphs)
    blocks = re.split(r'\n\s*\n', text)
    
    for block in blocks:
        block = block.strip()
        if len(block) < 20:
            continue
        
        # Look for St./Church/Cathedral patterns
        if re.search(r'(?:St\.|Sts\.|Cathedral|Church|Chapel)\s+[\w\'\s\.\-]+', block, re.I):
            entries.append({
                'year': year,
                'entry': block
            })
    
    return entries

def process_file(fp, year):
    """Process one formatted file."""
    text = fp.read_text(encoding='utf-8', errors='replace')
    clean = clean_text(text)
    entries = extract_entries(clean, year)
    
    out = OUTPUT_DIR / f"{year}_clean.json"
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
    
    return len(entries)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--all', action='store_true')
    p.add_argument('--year', type=int)
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.all:
        years = set()
        for f in RAW_DIR.glob('*_formatted.txt'):
            try:
                name = f.stem
                if name.startswith('catholic_dir_'):
                    name = name.replace('catholic_dir_', '')
                years.add(int(name.split('_')[0]))
            except:
                pass
        
        total = 0
        for y in sorted(years):
            for pattern in [f"{y}_formatted.txt", f"catholic_dir_{y}_formatted.txt"]:
                fp = RAW_DIR / pattern
                if fp.exists():
                    break
            else:
                continue
            
            try:
                n = process_file(fp, y)
                total += n
                print(f"{y}: {n} entries")
            except Exception as e:
                print(f"{y}: ERROR - {e}")
        
        print(f"\nTotal: {total} entries")

if __name__ == '__main__':
    main()
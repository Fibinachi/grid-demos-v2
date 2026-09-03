#!/usr/bin/env python3
"""
Fix OCR word breaks in formatted Catholic Directory files.
Processes years in batches.

Usage:
    python scripts/ingest/fix_word_breaks.py --batch 1   # Years 1833-1850  
    python scripts/ingest/fix_word_breaks.py --batch 2  # Years 1851-1870
    python scripts/ingest/fix_word_breaks.py --batch 3  # Years 1871-1900
    python scripts/ingest/fix_word_breaks.py --all       # All years
"""

import re
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

# Word break fixes (word-continuation hyphens)
WORD_BREAK_FIXES = [
    ('consecrated', r'consec-'),
    ('translated', r'translat-'),
    ('consecrated', r'con-'),
    ('consecrated', r'consec-'),
    ('exclusive', r'exclu-'),
    ('attended', r'attend-'),
    ('Govans', r'Govans-'),
    ('Gaitley', r'Gait-'),
    ('West', r'West-'),
    ('Frederick', r'Frede-'),
    ('church', r'church-'),
]

def fix_hyphens(text):
    """Fix line-break word splits (hyphen at end of line)."""
    # Join hyphenated words that span lines
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
    return text

def fix_common_breaks(text):
    """Fix common OCR word breaks within lines."""
    fixes = [
        (r'consec-[\s\-]*', 'consecrated '),
        (r'translat-[\s\-]*', 'translated '),
        (r'attend-[\s\-]*', 'attended '),
        (r'exclu-[\s\-]*', 'exclusive '),
        (r'consec-[\s\-]*', 'consecrated '),
        (r'con-[\s\-]*', 'consecrated '),
        (r'Gait-[\s\-]*', 'Gaitley'),
        (r'West-[\s\-]*', 'West '),
        (r'Frede-[\s\-]*', 'Frederick '),
    ]
    for pattern, replacement in fixes:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def fix_odd_chars(text):
    """Fix odd characters from OCR."""
    # Replace odd characters
    text = text.replace('�', '')  # Malformed apostrophe
    text = re.sub(r'['�–—_]+', '-', text)  # Various dash types
    return text

def process_year(year):
    fp = RAW_DIR / f"{year}_formatted.txt"
    if not fp.exists():
        fp = RAW_DIR / f"catholic_dir_{year}_formatted.txt"
    if not fp.exists():
        return None
    
    text = fp.read_text(encoding='utf-8', errors='replace')
    
    # Apply fixes
    text = fix_hyphens(text)
    text = fix_common_breaks(text)
    text = fix_odd_chars(text)
    
    # Normalize whitespace within lines
    lines = [' '.join(line.split()) for line in text.splitlines()]
    clean = '\n'.join(lines)
    
    out = OUTPUT_DIR / f"{year}_clean.txt"
    out.write_text(clean, encoding='utf-8')
    
    return len(clean.splitlines())

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--batch', type=int, choices=[1,2,3,4])
    p.add_argument('--all', action='store_true')
    p.add_argument('--year', type=int)
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Get all years
    years = set()
    for f in RAW_DIR.glob('*_formatted.txt'):
        try:
            name = f.stem
            if name.startswith('catholic_dir_'):
                name = name.replace('catholic_dir_', '')
            years.add(int(name.split('_')[0]))
        except:
            pass
    
    if args.batch == 1:
        batch_years = [y for y in years if y <= 1850]
    elif args.batch == 2:
        batch_years = [y for y in years if 1851 <= y <= 1870]
    elif args.batch == 3:
        batch_years = [y for y in years if 1871 <= y <= 1900]
    elif args.batch == 4:
        batch_years = [y for y in years if y > 1900]
    elif args.all:
        batch_years = sorted(years)
    elif args.year:
        batch_years = [args.year]
    else:
        print("Specify --batch, --all, or --year")
        return
    
    print(f"Processing {len(batch_years)} years...")
    total = 0
    for y in batch_years:
        n = process_year(y)
        if n:
            total += n
            print(f"  {y}: {n} lines")
    
    print(f"\nTotal: {total} lines from {len(batch_years)} years")

if __name__ == '__main__':
    main()
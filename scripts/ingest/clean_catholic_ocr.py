#!/usr/bin/env python3
"""
Systematic OCR cleanup for Catholic Directory raw text files.
Removes HTML artifacts, fixes common OCR errors, and outputs clean text.

Usage:
    python scripts/ingest/clean_catholic_ocr.py --year 1865
    python scripts/ingest/clean_catholic_ocr.py --all
    python scripts/ingest/clean_catholic_ocr.py --stats
"""

import re
import os
import json
from pathlib import Path
from collections import defaultdict

RAW_DIR = Path("E:/grid/data/directories")
CLEAN_DIR = Path("E:/grid/data/directories")

# Common OCR character mappings
OCR_CHAR_MAP = {
    # Common OCR misreads
    'ſ': 's',  # Long s
    'ﬁ': 'fi', 'ﬂ': 'fl',  # Ligatures
    '—': '-',   # Em dash to hyphen
    '–': '-',   # En dash to hyphen
    '"': '"', '"': '"',  # Smart quotes
    ''': "'", ''': "'",  # Smart single quotes
    '…': '...', # Ellipsis
    # OCR noise characters
    '□': '',    # Box
    '■': '',    # Block
    '¤': '',    # Currency
    '¶': '',    # Pilcrow
    '§': '',    # Section
    '£': '',    # Pound
    '®': '',    # Registered
    '™': '',    # Trademark
    '©': '',    # Copyright
    '°': '',    # Degree
    '±': '',    # Plus-minus
}

# Specific name/city corrections
NAME_CORRECTIONS = {
    'McCLOSKEY': 'McCloskey',
    'McClosk': 'McCloskey',
    'McCarony': 'McCarron',
    'McCOY': 'McCoy',
}

# Common OCR error corrections (pattern -> replacement)
OCR_CORRECTIONS = [
    # OCR misreads of common words
    (r'\bSadli?er?[’\']?s?\b', "Sadlier"),
    (r'\bSADLIER["\']?S\b', "Sadlier"),
    (r'\bARCHDIOCESE\b', "Archdiocese"),
    (r'\bARCHDIOCESAN\b', "Archdiocesan"),
    (r'\bDIOCESAN\b', "Diocesan"),
    (r'\bPREFACE[.\-]?\s*$', "PREFACE."),
    (r'\bCONTENTS[.\-]?\s*$', "CONTENTS."),
    # Fix broken dashes (emdash, endash artifacts)
    (r'[—–]', '-'),
    # Fix broken single quotes
    (r"[`'ʼ]", "'"),
    # Fix broken double quotes
    (r'"', '"'),
    # Fix common OCR name mangling
    (r'\bMcCloskey\b', 'McCloskey'),
    (r'\bMcClosk\b', 'McCloskey'),
    # Fix OCR'd garbage patterns
    (r'^[|\s\-+~=`]*$', ''),  # Lines that are only ornamental chars
]

# Patterns to strip entire lines (advertisements, noise)
NOISE_PATTERNS = [
    r'^Digitized by.*$',
    r'^Google$',
    r'^Archive.*$',
    r'^https?://.*$',
    r'.*\.com\b.*$',
    r'.*\.org\b.*$',
    r'.*\.net\b.*$',
    r'^\s*[0-9]+\s*[0-9,]+\s*[0-9]+\s*$',  # Just numbers
    r'^[A-Z]{2,}\s*[0-9]+.*$',  # Ad codes like "KA 123"
    r'^\s*\|\s*.*$',  # Lines starting with pipe (navigation chars)
    r'^[+\-~=*]{3,}$',  # Separator lines
    r'^\s*Page\s+\d+.*$', 
    r'^\s*Directory\s+for.*$',
    r'^Published\s+by.*$',
    r'^Printed\s+and.*$',
    r'^Address.*$',
    r'^Price.*$',
    r'^Manufac?t?ur?er?s?.*$',
    r'^Warranted.*$',
    r'^Sole\s+patentees.*$',
    r'^Manufacturers?\s+of.*$',
]

def clean_html_artifacts(text):
    """Remove HTML tags and artifacts."""
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove HTML entities
    text = re.sub(r'&[a-z]+;', '', text)
    # Remove script blocks and styles
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
    return text

def apply_corrections(text):
    """Apply OCR corrections."""
    for pattern, replacement in OCR_CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def strip_noise_lines(text):
    """Remove lines that are just noise."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            cleaned.append('')
            continue
        is_noise = False
        for pat in NOISE_PATTERNS:
            if re.search(pat, line, re.IGNORECASE):
                is_noise = True
                break
        if not is_noise:
            cleaned.append(line)
    return '\n'.join(cleaned)

def join_hyphenated_words(text):
    """Fix words broken across lines by hyphens."""
    # Join hyphenated words: "Ober-\nmyer" -> "Obermyer"
    text = re.sub(r'([a-z])-\s*\n\s*([a-z])', r'\1\2', text)
    return text

def normalize_whitespace(text):
    """Normalize whitespace within lines."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        # Collapse multiple spaces but preserve paragraph breaks
        line = re.sub(r'[ \t]+', ' ', line)
        cleaned.append(line.strip())
    return '\n'.join(cleaned)

def clean_file(input_path, output_path):
    """Clean a single file."""
    with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    
    original_lines = len(raw.splitlines())
    
    # Apply cleaning pipeline
    cleaned = clean_html_artifacts(raw)
    cleaned = join_hyphenated_words(cleaned)
    cleaned = apply_corrections(cleaned)
    cleaned = strip_noise_lines(cleaned)
    cleaned = normalize_whitespace(cleaned)
    
    final_lines = len(cleaned.splitlines())
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    
    return original_lines, final_lines

def main():
    import argparse
    p = argparse.ArgumentParser(description="Clean OCR'd Catholic Directory files")
    p.add_argument('--year', type=int, help='Clean specific year')
    p.add_argument('--all', action='store_true', help='Clean all raw files')
    p.add_argument('--stats', action='store_true', help='Show file stats')
    args = p.parse_args()
    
    if args.stats:
        files = sorted(RAW_DIR.glob('catholic_dir_????.txt'))
        print(f"{'Year':<8} {'Raw lines':>12} {'Clean lines':>12} {'Status':>15}")
        print("-" * 50)
        for fp in files[:20]:
            year = fp.stem.split('_')[1]
            raw_lines = len(fp.read_text(encoding='utf-8', errors='replace').splitlines())
            clean_path = RAW_DIR / f"catholic_dir_{year}_formatted.txt"
            status = "formatted" if clean_path.exists() else "raw only"
            clean_lines = 0
            if clean_path.exists():
                clean_lines = len(clean_path.read_text(encoding='utf-8', errors='replace').splitlines())
            print(f"{year:<8} {raw_lines:>12,} {clean_lines:>12,} {status:>15}")
        print(f"\n... and {max(0, len(files)-20)} more files")
        return
    
    if args.year:
        input_file = RAW_DIR / f"catholic_dir_{args.year}.txt"
        output_file = RAW_DIR / f"catholic_dir_{args.year}_formatted.txt"
        
        if not input_file.exists():
            print(f"Not found: {input_file}")
            return
        
        print(f"Cleaning {input_file.name}...")
        orig, final = clean_file(input_file, output_file)
        print(f"  {orig:,} lines -> {final:,} lines")
        print(f"  Saved to: {output_file}")
    
    elif args.all:
        files = sorted(RAW_DIR.glob('catholic_dir_????.txt'))
        # Skip if _formatted already exists
        files = [f for f in files if not f.name.endswith('_formatted.txt')]
        print(f"Cleaning {len(files)} raw files...")
        
        total_orig = 0
        total_final = 0
        for i, fp in enumerate(files, 1):
            year = fp.stem.split('_')[1]
            formatted = RAW_DIR / f"catholic_dir_{year}_formatted.txt"
            if formatted.exists():
                print(f"  [{i}/{len(files)}] {fp.name} - skipped (exists)")
                continue
            
            print(f"  [{i}/{len(files)}] {fp.name}...", end=" ", flush=True)
            orig, final = clean_file(fp, formatted)
            total_orig += orig
            total_final += final
            print(f"{orig:,} -> {final:,}")
        
        print(f"\nTotal: {total_orig:,} -> {total_final:,} lines")

if __name__ == '__main__':
    main()
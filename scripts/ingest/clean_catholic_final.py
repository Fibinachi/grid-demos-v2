#!/usr/bin/env python3
"""
Final OCR cleanup pipeline for Catholic Directory files.
Outputs clean JSON by diocese with proper entry parsing.

Usage:
    python scripts/ingest/clean_catholic_final.py --year 1865
    python scripts/ingest/clean_catholic_final.py --all
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def clean_text(text):
    """Remove HTML and normalize."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'[—–]', '-', text)
    text = re.sub(r'[ſﬁﬂ]', lambda m: {'ſ': 's', 'ﬁ': 'fi', 'ﬂ': 'fl'}.get(m.group(), m.group()), text)
    return text

def parse_entries(text, year):
    """Parse all entries from cleaned text."""
    # Find diocese sections
    diocese_starts = []
    for m in re.finditer(r'^(?:ARCH)?DIOCESE\s+OF\s+([A-Z][A-Z\s\-\']+)\.?$', text, re.MULTILINE|re.IGNORECASE):
        diocese_starts.append((m.group(1).strip(), m.start()))
    for m in re.finditer(r'^(?:VICARIATE\s+APOSTOLIC\s+OF\s+)([A-Z][A-Z\s\-\']+)\.?$', text, re.MULTILINE|re.IGNORECASE):
        diocese_starts.append((m.group(1).strip(), m.start()))
    
    diocese_starts.sort(key=lambda x: x[1])
    if not diocese_starts:
        return []
    
    entries = []
    for i, (dname, start) in enumerate(diocese_starts):
        end = diocese_starts[i+1][1] if i+1 < len(diocese_starts) else len(text)
        section = text[start:end]
        
        # Extract church/clergy entries - look for patterns like:
        # "St. Name, Address. Rev. Name, Role"
        # "City — St. Name. Rev. Name"
        
        # Pattern: St. Name with clergy
        for m in re.finditer(r'((?:St\.|Sts\.|St\.?\s*Mary|Catedral|Church|Immaculate|Assumption|Holy Trinity)[^\n]{10,200}?)(?:Rev\.|Rey\.|Very|Revd|\.\s+[A-Z][a-z])', section, re.IGNORECASE):
            entry_text = m.group(1).strip()
            # Clean up
            entry_text = re.sub(r'\s{2,}', ' ', entry_text)
            
            if len(entry_text) > 5:
                entries.append({
                    'year': year,
                    'diocese': dname,
                    'entry': entry_text
                })
    
    return entries

def process_year(year, dry_run=False):
    fp = RAW_DIR / f"catholic_dir_{year}.txt"
    if not fp.exists():
        print(f"Missing: {fp}")
        return
    
    raw_text = fp.read_text(encoding='utf-8', errors='replace')
    cleaned = clean_text(raw_text)
    
    # Remove noise lines
    lines = []
    for line in cleaned.splitlines():
        line = ' '.join(line.split())
        if re.match(r'^(?:Digitized|Google|Archive|Page|Directory|Published|Manufactur|Warranted)', line, re.I):
            continue
        if re.match(r'^[\|\-—–~=`]+$', line):
            continue
        if len(line) > 3:
            lines.append(line)
    
    clean_text_joined = '\n'.join(lines)
    entries = parse_entries(clean_text_joined, year)
    
    print(f"{year}: {len(raw_text):,} raw -> {len(lines):,} lines -> {len(entries):,} entries")
    
    if not dry_run:
        out = OUTPUT_DIR / f"{year}_entries.json"
        out.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
        print(f"  Saved to {out}")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        process_year(args.year, dry_run=args.dry_run)
    elif args.all:
        # Get all years that need processing
        years = set()
        for f in RAW_DIR.glob('catholic_dir_????.txt'):
            try:
                year = int(f.stem.split('_')[1])
                # Check if formatted version exists
                formatted = RAW_DIR / f"{year}_formatted.txt"
                if not formatted.exists():
                    years.add(year)
            except (ValueError, IndexError):
                continue
        
        print(f"Found {len(years)} years needing cleaning")
        for y in sorted(years)[:5]:
            process_year(y, dry_run=args.dry_run)

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Convert all formatted Catholic Directory files to clean JSON.
Handles both old format (state-based, 1833-1864) and new format (diocese-based, 1865+).

Usage:
    python scripts/ingest/convert_all_formatted.py --all
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def parse_old_format(text, year):
    """Parse pre-1865 format (state-based listings)."""
    entries = []
    lines = text.splitlines()
    
    current_state = None
    
    for line in lines:
        line = re.sub(r'\s+', ' ', line.strip())
        if not line:
            continue
        
        # State header
        if re.match(r'^[A-Z][A-Z\s\.]+$', line) and len(line.split()) <= 3:
            if line.upper() in ['ALABAMA.', 'ARKANSAS.', 'CONNECTICUT.', 'DELAWARE.', 'DISTRICT', 'FLORIDA', 'GEORGIA', 'ILLINOIS', 'INDIANA', 'KENTUCKY', 'LOUISIANA', 'MAINE', 'MARYLAND', 'MASSACHUSETTS', 'MICHIGAN', 'MISSISSIPPI', 'MISSOURI', 'NEW ENGLAND', 'NEW JERSEY', 'NEW YORK', 'NORTH CAROLINA', 'OHIO', 'PENNSYLVANIA', 'RHODE ISLAND', 'SOUTH CAROLINA', 'TENNESSEE', 'VIRGINIA', 'WISCONSIN']:
                current_state = line.rstrip('.')
                continue
        
        # Entry line - look for St./Church/Mass followed by Rev./Revd
        if re.search(r'(?:St\.|Church|Cathedral|Mass|Holy|Trinity|Divine Service)', line, re.I) and re.search(r'(?:Rev\.|Revd|Rev\.)', line, re.I):
            entries.append({
                'year': year,
                'state': current_state,
                'raw_entry': line
            })
    
    return entries

def parse_new_format(text, year):
    """Parse 1865+ format (diocese-based)."""
    entries = []
    
    # Find dioceses - use raw string to avoid escape issues
    diocese_pattern = r'^(?:ARCH)?DIOCESE\s+OF\s+([A-Z][A-Z\s\-\']+)[\.\s]'
    dioceses = []
    for m in re.finditer(diocese_pattern, text, re.MULTILINE):
        dioceses.append((m.group(1).strip(), m.start()))
    
    for i, (dname, start) in enumerate(dioceses):
        end = dioceses[i+1][1] if i+1 < len(dioceses) else len(text)
        section = text[start:end]
        
        # Parse entries in this section - look for church names followed by clergy
        church_pattern = r'((?:St\.|Sts\.|Cathedral|Chapel|Immaculate|Assumption|Church|Mission|Hospital|Seminary|Convent|School|Academy)[^\.]{10,}(?:\.|\.\s*Rev\.)'
        for m in re.finditer(church_pattern, section, re.I):
            entry_text = m.group(1).strip()
            entries.append({
                'year': year,
                'diocese': dname,
                'raw_entry': entry_text
            })
    
    return entries

def convert_file(fp, year):
    """Convert a formatted file to entries."""
    try:
        text = fp.read_text(encoding='utf-8', errors='replace')
    except:
        text = fp.read_text(encoding='latin-1', errors='replace')
    
    if year < 1865:
        return parse_old_format(text, year)
    else:
        return parse_new_format(text, year)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--all', action='store_true')
    p.add_argument('--dry-run', action='store_true')
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
                entries = convert_file(fp, y)
                if not args.dry_run:
                    out = OUTPUT_DIR / f"{y}_parsed.json"
                    out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
                total += len(entries)
                print(f"{y}: {len(entries)} entries {'saved' if not args.dry_run else ''}")
            except Exception as e:
                print(f"{y}: ERROR - {e}")
        
        print(f"\nTotal: {total} entries from {len(years)} years")

if __name__ == '__main__':
    main()
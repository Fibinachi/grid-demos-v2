#!/usr/bin/env python3
"""
Parse formatted Catholic Directory files into clean JSON entries.
Handles multiple formats:
- 1833-1864: State-based entries
- 1865-1900: City/county format (no "DIOCESE OF" header)
- 1900+: Diocese-based format
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def parse_entries_any_format(text, year):
    """Parse entries regardless of format."""
    entries = []
    lines = text.splitlines()
    
    # Pattern for entries - starts with St./Church/Cathedral followed by location/clergy
    entry_pattern = r'((?:St\.|Sts\.|Cathedral|Chapel|Immaculate|Assumption|Church|Mission|Hospital|Seminary|Convent|School|Academy)[^\n]{10,}?)\s*(?:Rev\.|Rey\.|Very)'
    
    for line in lines:
        line = re.sub(r'\s+', ' ', line.strip())
        if len(line) < 10:
            continue
        
        # Look for entry pattern
        m = re.search(entry_pattern, line, re.I)
        if m:
            entries.append({
                'year': year,
                'raw_entry': m.group(1).strip()
            })
    
    return entries

def convert_file(fp, year):
    try:
        text = fp.read_text(encoding='utf-8', errors='replace')
    except:
        text = fp.read_text(encoding='latin-1', errors='replace')
    
    return parse_entries_any_format(text, year)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
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
        for y in sorted(years):  # Process all years
            for pattern in [f"{y}_formatted.txt", f"catholic_dir_{y}_formatted.txt"]:
                fp = RAW_DIR / pattern
                if fp.exists():
                    break
            else:
                continue
            
            try:
                entries = convert_file(fp, y)
                out = OUTPUT_DIR / f"{y}_parsed.json"
                out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
                total += len(entries)
                print(f"{y}: {len(entries)} entries")
            except Exception as e:
                print(f"{y}: ERROR - {e}")
        
        print(f"\nTotal: {total} entries")

if __name__ == '__main__':
    main()
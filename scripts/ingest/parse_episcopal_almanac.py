#!/usr/bin/env python3
"""Parse Episcopal Church Annual almanac files."""
import re, csv
from pathlib import Path

DATA_DIR = Path('e:/grid/data/episcopal_annual')
OUTPUT_CSV = Path('e:/grid/data/denom/episcopal_almanac_parsed.csv')

def parse_almanac(text, year):
    entries = []
    lines = text.splitlines()
    
    # Pattern: "City, St._____’s, number. Initials" 
    pat = re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+(St\.[^\d]+)\s*(\d+)\s*\.\s*([A-Z].)')
    
    for line in lines:
        m = pat.search(line)
        if m:
            entries.append({
                'year': year,
                'church_name': m.group(2).strip().replace("'", "'"),
                'city': m.group(1).strip(),
                'state': '',  # Will need to infer from diocese context
                'rector': m.group(4).strip()
            })
    
    return entries

def main():
    files = sorted(DATA_DIR.glob('*_episcopal_almanac.txt'))
    print(f"Found {len(files)} almanac files")
    
    all_entries = []
    for f in files:
        year = int(f.stem.split('_')[0])
        print(f"  Parsing {year}...")
        text = f.read_text(encoding='utf-8', errors='replace')
        entries = parse_almanac(text, year)
        all_entries.extend(entries)
    
    # Deduplicate
    seen = set()
    unique = []
    for e in all_entries:
        key = (e['year'], e['church_name'], e['city'])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    
    print(f"Total entries: {len(unique)}")
    
    if unique:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['year', 'church_name', 'city', 'state', 'rector'])
            w.writeheader()
            w.writerows(unique)
        print(f"Saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Parse formatted Catholic Directory files into clean JSON entries.
Handles multi-line entries and extracts church name, city, clergy.

Output format:
{
  "year": 1872,
  "diocese": "BALTIMORE",
  "church_name": "St. Patrick's",
  "location": "Fell's Point, corner of Broadway and Bank street",
  "clergy": ["Rev. John Gaitley, P.P.", "Rev. James Duncan, of New Carolina"]
}
"""

import re
import json
from pathlib import Path

RAW_DIR = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/directories/cleaned")

def parse_diocese_file(fp, year):
    """Parse formatted directory into structured entries."""
    text = fp.read_text(encoding='utf-8', errors='replace')
    
    # Find diocese sections
    dioceses = []
    for m in re.finditer(r'^(?:ARCH)?DIOCESE\s+OF\s+([A-Z][A-Z\s\-\']+?)\s*$', text, re.MULTILINE):
        dioceses.append((m.group(1).strip(), m.start()))
    
    all_entries = []
    
    for i, (dname, start) in enumerate(dioceses):
        end = dioceses[i+1][1] if i+1 < len(dioceses) else len(text)
        section = text[start:end]
        
        entries = parse_section(section, dname, year)
        all_entries.extend(entries)
    
    return all_entries

def parse_section(section, diocese, year):
    """Parse a diocese section."""
    entries = []
    
    # Split into paragraphs (double newlines)
    paragraphs = re.split(r'\n\s*\n', section)
    
    current_entry = None
    
    for para in paragraphs:
        para = re.sub(r'\s+', ' ', para.strip())
        if not para:
            continue
        
        # Skip structural headers
        if re.match(r'^(CHURCHES\s+AND\s+CLERGY|INSTITUTIONS?|ECCLESIASTICAL|PAROCHIAL|COUNTRY|CITY\s+OF|COUNTY|DECEASED|Present|Archbishop|Bishop|Vicar|PREFACE|CONTENTS)', para, re.I):
            continue
        
        # Skip pure clergy lists (just names/titles)
        if re.match(r'^Rev\.\s+\w+', para) and not re.search(r'(?:St\.|Cathedral|Church|Chapel)\s+', para):
            continue
        
        # Entry starts with St./Cathedral/Chapel
        m = re.match(r'^((?:St\.|Sts\.|Cathedral|Chapel|Church|Immaculate|Assumption|Mission)\s+[\w\s\.\-\']+?)(?:,\s*|\s+)([\w\s\.\-\',]+?)(?:\.\s+Rev\.|$)', para, re.I)
        if m:
            name = m.group(1).strip()
            rest = m.group(2).strip() if m.group(2) else ""
            
            # Extract clergy info
            clergy = re.findall(r'Rev\.\s+[\w\s\.\-\']+?(?:,[\s\w\.]+)?', para, re.I)
            
            entries.append({
                'year': year,
                'diocese': diocese,
                'church_name': name,
                'location': rest,
                'clergy': clergy,
                'raw': para[:200]
            })
    
    return entries

def process_year(year, dry=False):
    """Process one year's formatted file."""
    for pattern in [f"{year}_formatted.txt", f"catholic_dir_{year}_formatted.txt"]:
        fp = RAW_DIR / pattern
        if fp.exists():
            break
    else:
        return None
    
    entries = parse_diocese_file(fp, year)
    print(f"{year}: {len(entries)} entries")
    
    if not dry:
        out = OUTPUT_DIR / f"{year}_parsed.json"
        out.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
        print(f"  Saved to {out}")
    
    return entries

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int)
    p.add_argument('--all', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    if args.year:
        process_year(args.year, dry=args.dry_run)
    elif args.all:
        # Get all years with formatted files
        years = set()
        for f in RAW_DIR.glob('*_formatted.txt'):
            try:
                name = f.stem
                if name.startswith('catholic_dir_'):
                    name = name.replace('catholic_dir_', '')
                years.add(int(name.split('_')[0]))
            except:
                pass
        
        for y in sorted(years)[:3]:  # Test first 3
            process_year(y, dry=args.dry_run)

if __name__ == '__main__':
    main()
"""
Parse The Official Catholic Directory format (years 1948+)
Pattern: Church name, location, Rev. ClergyName, Role
"""
import re
import csv
import os
from pathlib import Path
from gw_db import connect

DIRECTORIES = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/denom")

# Pattern for church entries: "Church Name, City, State — Rev. Name, Role"
RE_CHURCH_ENTRY = re.compile(
    r'^((?:St\.|Sts\.|St\.|Cathedral|Church|Mission|Shrine|Basilica)\s+[A-Z][^\n]{10,100}?)\s*[—\-]?\s*'
    r'((?:Rev\.|Very\s+Rev\.|Most\s+Rev\.|Rt\.?\s+Rev\.|Msgr\.|Fr\.)\s+[A-Z][a-z][^\n]{0,50})',
    re.IGNORECASE
)

RE_CHURCH_LINE = re.compile(
    r'^(.{10,150}?)\s*[—\-]\s*(Rev\.|Very\s+Rev\.|Most\s+Rev\.|Rt\.\s*Rev\.)\s+([A-Z][a-z][^\n]{0,100})',
    re.IGNORECASE
)

RE_NAME = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z]\.)?\s+(?:Mc|Mac)?[A-Z][a-z]+)'
)

ORDERS = ['O.S.B.', 'O.S.F.', 'C.SS.R.', 'O.F.M.', 'S.J.', 'O.S.B', 'O.S.F', 'C.SS.R', 'O.F.M', 'S.J']


def parse_official_directory(filepath, year):
    """Parse The Official Catholic Directory format."""
    records = []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    
    # Split into diocese sections
    diocese_sections = re.split(r'(ARCH?)DIOCESE\s+OF\s+([A-Z][^\n.]+)\.', text, flags=re.IGNORECASE)
    
    current_diocese = None
    current_country = 'US'
    
    lines = text.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Check for diocese header
        dio_match = re.match(r'(ARCHDIOCESE|DIOCESE)\s+OF\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', line, re.IGNORECASE)
        if dio_match:
            current_diocese = dio_match.group(2)
            i += 1
            continue
        
        # Check for "in the United States" or country markers
        if 'United States' in line or 'Canada' in line:
            current_country = 'US' if 'United States' in line else 'CA'
        
        # Skip structural lines
        if any(x in line for x in ['Digitized by', 'Google', '=====', 'CONTENTS', 'PREFACE', 'Page', 'PAGE']):
            i += 1
            continue
        
        # Try to match church pattern
        # Look for: Church name — Rev. Name, Role OR
        # Church name, City — Rev. Name
        m = RE_CHURCH_LINE.match(line)
        if m:
            church_part = m.group(1).strip()
            clergy_part = m.group(2) + ' ' + m.group(3) if m.group(3) else m.group(2)
            
            # Extract city from church_part
            city = None
            city_m = re.search(r'(?:,\s*)([A-Z][a-z]+(?:\s+[A-Z]\.)?(?:,\s+[A-Z]{2})?)$', church_part)
            if city_m:
                city = city_m.group(1).strip().rstrip(',')
            
            # Parse clergy names
            priests = []
            name_matches = RE_NAME.findall(clergy_part)
            for nm in name_matches:
                # Extract order/religious community
                order = None
                for o in ORDERS:
                    if o in clergy_part:
                        order = o
                        break
                
                priests.append({
                    'name': nm.strip(),
                    'title': 'Rev.' if not any(x in clergy_part for x in ['Very', 'Most', 'Rt.']) else 'Very Rev.',
                    'order': order,
                    'role': 'Pastor'
                })
            
            for p in priests:
                records.append({
                    'year': year,
                    'diocese': current_diocese or '',
                    'city': city or '',
                    'parish': church_part[:80],
                    'priest_name': p['name'],
                    'title': p['title'],
                    'order': p['order'],
                    'role': p['role'],
                    'source_file': os.path.basename(filepath),
                    'source_line': i + 1,
                })
        
        i += 1
    
    return records[:1000]  # Limit for testing


def main():
    db = connect()
    
    for year in [1948, 1949, 1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958]:
        fp = DIRECTORIES / f"catholic_dir_{year}_formatted.txt"
        if not fp.exists():
            print(f"Skipping {year} - file not found")
            continue
        
        print(f"\n{year} - parsing...")
        recs = parse_official_directory(fp, year)
        print(f"  {len(recs)} entries")
        
        if recs:
            csv_path = OUTPUT_DIR / f"catholic_directory_{year}.csv"
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['year', 'diocese', 'city', 'parish', 'priest_name', 'title', 'order', 'role', 'source_file', 'source_line'])
                w.writeheader()
                w.writerows(recs)
            print(f"  Saved to {csv_path}")
    
    db.close()


if __name__ == '__main__':
    main()
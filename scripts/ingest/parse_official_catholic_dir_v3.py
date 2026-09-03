"""
Parse The Official Catholic Directory format (years 1948+).
Format: "DIOCESE OF X, STATE" or "DIOCESE OF X STATE" followed by church entries.
Extracts state from diocese header, not from individual lines.
"""
import re
import csv
import os
from pathlib import Path

DIRECTORIES = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/denom/catholic_official_parsed_v3")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# State name to code mapping
STATE_CODES = {
    'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
    'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
    'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID', 'ILLINOIS': 'IL',
    'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS', 'KENTUCKY': 'KY', 'LOUISIANA': 'LA',
    'MAINE': 'ME', 'MARYLAND': 'MD', 'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI',
    'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS', 'MISSOURI': 'MO', 'MONTANA': 'MT',
    'NEBRASKA': 'NE', 'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ',
    'NEW MEXICO': 'NM', 'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND',
    'OHIO': 'OH', 'OKLAHOMA': 'OK', 'OREGON': 'OR', 'PENNSYLVANIA': 'PA',
    'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN',
    'TEXAS': 'TX', 'UTAH': 'UT', 'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA',
    'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC',
    # Also handle 2-letter codes
    'AL': 'AL', 'AK': 'AK', 'AZ': 'AZ', 'AR': 'AR', 'CA': 'CA', 'CO': 'CO', 'CT': 'CT',
    'DE': 'DE', 'FL': 'FL', 'GA': 'GA', 'HI': 'HI', 'ID': 'ID', 'IL': 'IL', 'IN': 'IN',
    'IA': 'IA', 'KS': 'KS', 'KY': 'KY', 'LA': 'LA', 'ME': 'ME', 'MD': 'MD', 'MA': 'MA',
    'MI': 'MI', 'MN': 'MN', 'MS': 'MS', 'MO': 'MO', 'MT': 'MT', 'NE': 'NE', 'NV': 'NV',
    'NH': 'NH', 'NJ': 'NJ', 'NM': 'NM', 'NY': 'NY', 'NC': 'NC', 'ND': 'ND', 'OH': 'OH',
    'OK': 'OK', 'OR': 'OR', 'PA': 'PA', 'RI': 'RI', 'SC': 'SC', 'SD': 'SD', 'TN': 'TN',
    'TX': 'TX', 'UT': 'UT', 'VT': 'VT', 'VA': 'VA', 'WA': 'WA', 'WV': 'WV', 'WI': 'WI',
    'WY': 'WY', 'DC': 'DC',
}

def parse_official_directory(filepath, year):
    """Parse The Official Catholic Directory format."""
    records = []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    
    lines = [l.rstrip() for l in text.split('\n')]
    
    # Find diocese sections
    diocese_pattern = re.compile(r'(?:ARCHDIOCESE|DIOCESE)\s+OF\s+(.+)', re.IGNORECASE)
    
    current_diocese = None
    current_state = None
    
    for i, line in enumerate(lines):
        # Check diocese header
        m = diocese_pattern.search(line)
        if m:
            header = m.group(1).strip()
            # Parse "Pueblo, Colorado" or "PUEBLO COLORADO"
            parts = header.split(',')
            if len(parts) >= 2:
                current_diocese = parts[0].strip().rstrip('.')
                state_part = parts[1].strip()
                current_state = STATE_CODES.get(state_part.upper(), state_part[:2].upper())
            else:
                # Try space-separated: "PUEBLO COLORADO" 
                parts = header.split()
                state_idx = None
                for idx, p in enumerate(parts):
                    if p.upper() in STATE_CODES:
                        state_idx = idx
                        break
                if state_idx:
                    current_diocese = ' '.join(parts[:state_idx])
                    current_state = STATE_CODES.get(parts[state_idx].upper(), parts[state_idx][:2].upper())
                else:
                    current_diocese = header
                    current_state = None
            continue
        
        # Skip garbage lines
        if len(line) < 10:
            continue
        if any(x in line.lower() for x in ['page ', 'copyright', 'advertis', 'kenedy', 'telephone', 'index of', 'classified']):
            continue
        
        # Check for church entry
        if current_diocese and line.startswith(('St.', 'Sts.', 'Cathedral', 'Mission', 'Shrine')):
            # Clean the name
            name = line.split(',')[0].strip()
            records.append({
                'year': year,
                'diocese': current_diocese,
                'state': current_state or '',
                'name': name,
                'source_line': i + 1,
                'source_file': os.path.basename(filepath),
            })
    
    return records

def main():
    for year in [1948, 1949, 1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958, 1960, 1961, 1962, 1963, 1964, 1965, 1966, 1967, 1968, 1971, 1972, 1974, 1975, 1976, 1978, 1979, 1980, 1981, 1982, 1983, 1984, 1985, 1986, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2005, 2006, 2007, 2008, 2009, 2010, 2012, 2013, 2014, 2015, 2016, 2018, 2019, 2020, 2021]:
        fp = DIRECTORIES / f"catholic_dir_{year}_formatted.txt"
        if not fp.exists():
            continue
        
        print(f"\n{year} - parsing...", end=' ', flush=True)
        recs = parse_official_directory(fp, year)
        
        # Deduplicate
        seen = set()
        clean_recs = []
        for r in recs:
            if r['name'] and (r['name'], r['diocese']) not in seen:
                seen.add((r['name'], r['diocese']))
                clean_recs.append(r)
        
        print(f"{len(clean_recs)} entries")
        
        csv_path = OUTPUT_DIR / f"catholic_{year}.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['year', 'diocese', 'state', 'city', 'name', 'source_file', 'source_line'])
            w.writeheader()
            w.writerows(clean_recs)
        print(f"  Saved to {csv_path}")
    
    print("\nDone.")

if __name__ == '__main__':
    main()
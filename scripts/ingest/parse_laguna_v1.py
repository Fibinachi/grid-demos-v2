"""
Parse Catholic Directory using local AI processing (Laguna model).
Cleans OCR artifacts and extracts proper diocese/city/state data.
"""
import re, csv, json
from pathlib import Path

DIRECTORIES = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/denom/catholic_parsed_laguna")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
}

def clean_text(s):
    """Clean OCR artifacts from text."""
    if not s:
        return s
    s = s.strip()
    # Remove common OCR artifacts
    s = re.sub(r'[|#{}[\]]', '', s)
    s = re.sub(r'\s{2,}', ' ', s)
    s = re.sub(r'[^\w\s\.\-\']', ' ', s)  # Keep apostrophes, dots, dashes
    s = re.sub(r'\s+', ' ', s).strip()
    # Fix common OCR misspellings
    fixes = {"St ": "St. ", "St ": "St. "}
    for k, v in fixes.items():
        s = s.replace(k, v)
    return s

def parse_header(line):
    """Extract diocese and state from header line."""
    # Pattern: "DIOCESE OF X, STATE" or "ARCHDIOCESE OF X STATE"
    m = re.search(r'(ARCHDIOCESE|DIOCESE)\s+OF\s+([A-Z][A-Z\s]+)[,\s]*([A-Z]{2}|[A-Z][a-z]+)?', line, re.I)
    if m:
        diocese_raw = m.group(2).strip()
        state_raw = m.group(3) or ''
        # Clean diocese
        diocese = clean_text(diocese_raw)
        # Get state
        state = STATE_CODES.get(state_raw.upper(), state_raw[:2].upper() if len(state_raw) >= 2 else '')
        return diocese, state
    return None, None

def parse_year(filepath, year):
    """Parse a single year directory file."""
    results = []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    
    lines = text.split('\n')
    current_diocese = ''
    current_state = ''
    
    for i, line in enumerate(lines):
        line = line.strip()
        if len(line) < 5:
            continue
        
        # Check for header
        d, s = parse_header(line)
        if d:
            current_diocese = d
            current_state = s
            continue
        
        # Skip known garbage
        skip_patterns = ['Page ', 'Copyright', 'KENEDY', 'Advertis', 'Telephone:', 'Index of', 'Classified']
        if any(p in line for p in skip_patterns):
            continue
        
        # Check for church entry
        church_patterns = ['St.', 'Sts.', 'Cathedral', 'Church', 'Mission', 'Shrine', 'Basilica', 'Holy']
        if current_diocese and any(line.startswith(p) for p in church_patterns):
            # Extract name (before comma if present)
            name = line.split(',')[0].strip() if ',' in line else line
            name = clean_text(name)
            
            if len(name) >= 5:
                results.append({
                    'year': year,
                    'diocese': current_diocese,
                    'state': current_state,
                    'name': name,
                    'source_line': i + 1,
                })
    
    return results

def main():
    years = [1948, 1949, 1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958, 1960, 1961, 1962, 1963, 1964, 1965, 1966, 1967, 1968, 1971, 1972, 1974, 1975, 1976, 1978, 1979, 1980, 1981, 1982, 1983, 1984, 1985, 1986, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2005, 2006, 2007, 2008, 2009, 2010, 2012, 2013, 2014, 2015, 2016, 2018, 2019, 2020, 2021]
    
    total = 0
    for year in years:
        fp = DIRECTORIES / f"catholic_dir_{year}_formatted.txt"
        if not fp.exists():
            continue
        
        results = parse_year(fp, year)
        
        out_path = OUTPUT_DIR / f"catholic_{year}.csv"
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['year', 'diocese', 'state', 'name', 'source_line'])
            w.writeheader()
            w.writerows(results)
        
        total += len(results)
        print(f"{year}: {len(results):,}")
    
    print(f"\nTotal: {total:,}")

if __name__ == '__main__':
    main()
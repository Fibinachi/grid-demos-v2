"""
Parse The Official Catholic Directory format (years 1948+).
Format: Diocese header followed by institution/church name + location lines.
Pattern: "Archdiocese of X, State" followed by "St. Something, City" lines
"""
import re
import csv
import os
from pathlib import Path

DIRECTORIES = Path("E:/grid/data/directories")
OUTPUT_DIR = Path("E:/grid/data/denom/catholic_official_parsed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RE_DIOCESE = re.compile(r'^Archdiocese of ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s+([A-Z]{2})', re.IGNORECASE)
RE_DIOCESE2 = re.compile(r'^Diocese of ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s+([A-Z]{2})', re.IGNORECASE)
RE_CHURCH = re.compile(r'^(St\.|Sts\.|Cathedral|Church|Mission|Shrine|Basilica|Holy)\s+[A-Z][^\n,]{5,100}', re.IGNORECASE)
RE_CITY = re.compile(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s+([A-Z]{2})$')


def parse_official_directory(filepath, year):
    """Parse The Official Catholic Directory format."""
    records = []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    
    lines = [l.strip() for l in text.split('\n')]
    
    current_diocese = None
    current_state = None
    
    for i, line in enumerate(lines):
        if not line or len(line) < 10:
            continue
        
        # Check for diocese header
        dio_match = RE_DIOCESE.match(line) or RE_DIOCESE2.match(line)
        if dio_match:
            current_diocese = dio_match.group(1)
            current_state = dio_match.group(2)
            continue
        
        # Skip ad sections, page refs, etc.
        if any(x in line for x in ['Page ', 'Copyright', 'All rights', 'KENEDY', 'Advertis', 
                                     'Telephone:', 'Index of', 'Classified', '—', '====']):
            continue
        
        # Check for church entry
        church_match = RE_CHURCH.match(line)
        if church_match and current_diocese:
            # Extract city if present
            city = ''
            if ',' in line:
                parts = line.split(',')
                if len(parts) >= 2:
                    city = parts[-1].strip().rstrip(').').strip()
                    # Clean up - remove state if attached to church name
                    if re.match(r'^[A-Z]{2}$', city):
                        city = parts[-2].strip() if len(parts) >= 3 else ''
            
            records.append({
                'year': year,
                'diocese': current_diocese,
                'state': current_state,
                'name': line.split(',')[0].strip() if ',' in line else line,
                'city': city,
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
        
        # Filter duplicates and garbage
        seen = set()
        clean_recs = []
        for r in recs:
            key = (r['year'], r['diocese'], r['name'])
            if key not in seen and r['name']:
                seen.add(key)
                clean_recs.append(r)
        
        # Group by diocese and count
        from collections import defaultdict
        by_diocese = defaultdict(int)
        for r in clean_recs:
            by_diocese[r['diocese']] += 1
        
        print(f"{len(clean_recs)} entries in {len(by_diocese)} dioceses")
        
        if clean_recs:
            csv_path = OUTPUT_DIR / f"catholic_{year}.csv"
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=['year', 'diocese', 'state', 'city', 'name', 'source_file', 'source_line'])
                w.writeheader()
                w.writerows(clean_recs)
            print(f"  Saved to {csv_path}")
    
    print("\nDone.")


if __name__ == '__main__':
    main()
"""
Clean the parsed CSVs using diocese-state mapping from catholic_hierarchy.
"""
import csv, sqlite3, re
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"
PARSED_DIR = Path("E:/grid/data/denom/catholic_official_parsed")
GRID_DB = "E:/grid/churches.db"

# Build diocese->state mapping from catholic_hierarchy
def build_mapping():
    grid = sqlite3.connect(GRID_DB)
    mapping = {}
    for row in grid.execute('SELECT diocese, state FROM catholic_hierarchy').fetchall():
        d, s = row
        if d and s:
            d_clean = re.sub(r'^(?:ARCH|ARCHDIOCESE|DIOCESE)\s+OF\s+', '', d, flags=re.I).strip()
            mapping[d_clean.lower()] = s.upper()
            mapping[d.lower()] = s.upper()
    grid.close()
    return mapping

def clean_diocese(d):
    """Extract diocese name from corrupted string."""
    if not d:
        return d
    # Remove trailing garbage like "Leavenworth to the Diocese of, KS"
    d = d.strip()
    # Match patterns like "DIOCESE OF XXX" or "ARCHDIOCESE OF XXX"
    m = re.search(r'(?:DIOCESE|ARCHDIOCESE)\s+OF\s+([A-Z][A-Z\s]+)', d, re.I)
    if m:
        d = m.group(1).strip()
    # Remove common OCR artifacts
    d = re.sub(r'[.,;]+$', '', d)
    return d

def main():
    mapping = build_mapping()
    print(f"Loaded {len(mapping)} diocese-state mappings")
    
    cath = sqlite3.connect(CATH_DB)
    
    # Process all CSVs, update with correct states
    csvs = sorted(PARSED_DIR.glob('catholic_*.csv'))
    print(f"Processing {len(csvs)} CSV files...")
    
    for cp in csvs:
        year = int(cp.stem.split('_')[1])
        
        with open(cp, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        updated = 0
        for r in rows:
            diocese = r.get('diocese', '')
            if not diocese:
                continue
            
            clean_d = clean_diocese(diocese)
            state = mapping.get(clean_d.lower())
            
            if state and r.get('state'):
                # Update the DB entry
                cath.execute('''
                    UPDATE dir_entries 
                    SET state=? 
                    WHERE directory_year=? AND diocese=?
                ''', (state, year, diocese))
        
        if updated > 0:
            cath.commit()
            print(f"  {year}: updated")
    
    cath.close()
    print("Done.")

if __name__ == '__main__':
    main()
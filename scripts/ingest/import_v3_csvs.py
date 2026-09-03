"""
Re-import v3 parsed CSVs with proper diocese extraction and match to GRID.
"""
import csv, sqlite3
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"
PARSED_DIR = Path("E:/grid/data/denom/catholic_official_parsed_v3")

def build_diocese_states():
    """Build diocese->state mapping from catholic_hierarchy."""
    grid = sqlite3.connect(GRID_DB)
    mapping = {}
    for r in grid.execute('SELECT diocese, state FROM catholic_hierarchy').fetchall():
        if r[0] and r[1]:
            mapping[r[0].lower().strip()] = r[1].upper().strip()
    grid.close()
    return mapping

def main():
    cath = sqlite3.connect(CATH_DB)
    
    # Build mapping
    dia_map = build_diocese_states()
    print(f"Diocese mapping: {len(dia_map)} entries")
    
    # Get existing years
    existing = set(r[0] for r in cath.execute('SELECT DISTINCT directory_year FROM dir_entries').fetchall())
    
    total_added = 0
    
    csvs = sorted(PARSED_DIR.glob('catholic_*.csv'))
    print(f"Importing {len(csvs)} years...")
    
    for cp in csvs:
        year = int(cp.stem.split('_')[1])
        
        if year in existing:
            print(f"  {year}: already exists, skipping")
            continue
        
        with open(cp, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(f)
        
        added = 0
        for line in rows[1:]:  # Skip header
            parts = line.strip().split(',')
            if len(parts) < 4:
                continue
            diocese = parts[1].strip() if len(parts) > 1 else ''
            state = parts[2].strip() if len(parts) > 2 else ''
            
            # Fix state using mapping
            if not state or state not in 'AL,AK,AZ,AR,CA,CO,CT,DE,FL,GA,HI,ID,IL,IN,IA,KS,KY,LA,ME,MD,MA,MI,MN,MS,MO,MT,NE,NV,NH,NJ,NM,NY,NC,ND,OH,OK,OR,PA,RI,SC,SD,TN,TX,UT,VT,VA,WA,WV,WI,WY,DC'.split(',') + ['PR', 'QC', 'AB', 'ON', 'BC']:
                state = dia_map.get(diocese.lower(), '')
            
            name = parts[3].strip() if len(parts) > 3 else ''
            
            if name and diocese:
                cath.execute('''
                    INSERT INTO dir_entries (directory_year, source_entry_id, name, state, diocese, entity_type, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (year, f"v3_{diocese}_{name[:30]}", name, state, diocese, 'parish', f"[Official CD {year}]"))
                added += 1
        
        if added > 0:
            cath.commit()
            print(f"  {year}: {added:,}")
            total_added += added
    
    print(f"\nTotal added: {total_added:,}")
    cath.close()

if __name__ == '__main__':
    main()
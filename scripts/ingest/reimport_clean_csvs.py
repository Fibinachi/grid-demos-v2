"""
Re-import cleaned CSVs into catholic_directory.db with proper diocese names.
"""
import csv, sqlite3, re
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"
PARSED_DIR = Path("E:/grid/data/denom/catholic_official_parsed_clean")
GRID_DB = "E:/grid/churches.db"

def build_diocese_states():
    db = sqlite3.connect(GRID_DB)
    mapping = {}
    for r in db.execute('SELECT diocese, state FROM catholic_hierarchy').fetchall():
        if r[0] and r[1]:
            d = re.sub(r'^(?:arch|archdiocese|diocese)\s+of\s+', '', r[0], flags=re.I).strip().lower()
            mapping[d] = r[1].strip().upper()
    db.close()
    return mapping

def clean_diocese(d):
    d = re.sub(r'^.*(diocese|archdiocese)\s+of\s+', '', d, flags=re.I)
    d = d.strip('.,;').strip()
    return d

def main():
    cath = sqlite3.connect(CATH_DB)
    mapping = build_diocese_states()
    print(f"Diocese mapping: {len(mapping)}")
    
    # Clear existing parsed entries (keep DeepSeek-parsed ones)
    cath.execute("DELETE FROM dir_entries WHERE notes LIKE '%[Official CD%'")
    cath.commit()
    print("Cleared old parsed entries")
    
    csvs = sorted(PARSED_DIR.glob("catholic_*.csv"))
    total_added = 0
    
    for cp in csvs:
        year = int(cp.stem.split('_')[1])
        
        with open(cp, 'r', encoding='utf-8') as f:
            lines = f.read().split('\n')
        
        added = 0
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split(',')
            if len(parts) >= 6:
                diocese = clean_diocese(parts[1])
                state = parts[2].strip() if len(parts) > 2 else ''
                
                # Infer state from diocese if missing
                if not state or state not in 'AL,AK,AZ,AR,CA,CO,CT,DE,FL,GA,HI,ID,IL,IN,IA,KS,KY,LA,ME,MD,MA,MI,MN,MS,MO,MT,NE,NV,NH,NJ,NM,NY,NC,ND,OH,OK,OR,PA,RI,SC,SD,TN,TX,UT,VT,VA,WA,WV,WI,WY,DC'.split(',') + ['PR', 'QC', 'AB', 'ON', 'BC']:
                    state = mapping.get(diocese.lower(), '')
                
                name = parts[4].strip() if len(parts) > 4 else ''
                
                if name and diocese:
                    cath.execute('''
                        INSERT INTO dir_entries (directory_year, source_entry_id, name, city, state, diocese, entity_type, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (year, f"clean_{diocese}_{name[:30]}", name, 
                          parts[3].strip() if len(parts) > 3 else None, state, diocese, 'parish',
                          f"[Official CD {year}]"))
                    added += 1
        
        if added > 0:
            cath.commit()
            total_added += added
            print(f"  {year}: {added:,}")
    
    print(f"\nTotal added: {total_added:,}")
    cath.close()

if __name__ == '__main__':
    main()
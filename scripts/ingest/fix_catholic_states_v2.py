"""
Re-import all Catholic directory years with proper state inference from diocese names.
"""
import sqlite3, csv, time
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"
PARSED_DIR = Path("E:/grid/data/denom/catholic_official_parsed")

# Build diocese-to-state mapping from catholic_hierarchy
def build_diocese_states():
    db = sqlite3.connect(GRID_DB)
    db.row_factory = sqlite3.Row
    
    mapping = {}
    rows = db.execute('''
        SELECT DISTINCT diocese, state FROM catholic_hierarchy 
        WHERE diocese IS NOT NULL AND diocese != '' AND state IS NOT NULL AND state != ''
    ''').fetchall()
    for r in rows:
        d = r['diocese'].lower().strip()
        s = r['state'].strip()
        # Normalize diocese name
        if 'archdiocese' in d:
            d = d.replace('archdiocese of ', '').replace('archdiocese ', '').strip()
        elif 'diocese' in d:
            d = d.replace('diocese of ', '').replace('diocese ', '').strip()
        mapping[d] = s.upper()
        # Also store full name
        mapping[r['diocese'].lower().strip()] = s.upper()
    
    db.close()
    return mapping

def infer_state(diocese, mapping):
    """Infer state from diocese name."""
    if not diocese:
        return None
    d = diocese.lower().strip()
    if 'archdiocese' in d:
        d = d.replace('archdiocese of ', '').replace('archdiocese ', '').strip()
    elif 'diocese' in d:
        d = d.replace('diocese of ', '').replace('diocese ', '').strip()
    
    if d in mapping:
        return mapping[d]
    
    # Try partial match
    for k, v in mapping.items():
        if k in d or d in k:
            return v
    
    return None

def main():
    cath = sqlite3.connect(CATH_DB)
    cath.row_factory = sqlite3.Row
    
    # Build mapping
    print("Building diocese->state mapping...")
    mapping = build_diocese_states()
    print(f"Found {len(mapping)} diocese-state pairs")
    
    # Get entries with invalid states
    cath.row_factory = sqlite3.Row
    bad = cath.execute('''
        SELECT id, state, diocese FROM dir_entries 
        WHERE state NOT IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','QC','NULL')
    ''').fetchall()
    
    print(f"Fixing {len(bad):,} entries with invalid states...")
    
    fixed = 0
    for r in bad:
        real_state = infer_state(r['diocese'], mapping)
        if real_state:
            cath.execute('UPDATE dir_entries SET state=? WHERE id=?', (real_state, r['id']))
            fixed += 1
            if fixed % 10000 == 0:
                cath.commit()
                print(f"  Fixed {fixed:,}")
    
    cath.commit()
    
    # Check remaining
    remaining = cath.execute('''
        SELECT COUNT(*) FROM dir_entries 
        WHERE state NOT IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','QC')
    ''').fetchone()[0]
    print(f"Remaining invalid: {remaining}")
    
    cath.close()

if __name__ == '__main__':
    main()
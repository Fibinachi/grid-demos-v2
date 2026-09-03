"""
Fix all state data in catholic_directory.db using catholic_hierarchy mapping.
"""
import sqlite3, re
from collections import defaultdict

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"

def build_state_map():
    db = sqlite3.connect(GRID_DB)
    # Map diocese name to state
    diocese_to_state = {}
    for r in db.execute('SELECT diocese, state FROM catholic_hierarchy').fetchall():
        if r[0] and r[1]:
            d = r[0].lower().strip()
            s = r[1].strip().upper()
            # Normalize
            d = re.sub(r'^(?:arch|archdiocese|diocese)\s+of\s+', '', d, flags=re.I)
            diocese_to_state[d] = s
            diocese_to_state[r[0].lower().strip()] = s
    
    # Also build from churches table via hierarchy
    for r in db.execute('SELECT diocese_canonical, state FROM churches WHERE diocese_canonical IS NOT NULL AND state IS NOT NULL').fetchall():
        d = r[0].lower().strip() if r[0] else ''
        s = r[1].strip().upper() if r[1] else ''
        if d and s:
            diocese_to_state[d] = s
    
    db.close()
    return diocese_to_state

def main():
    diocese_to_state = build_state_map()
    print(f"Diocese-state mapping: {len(diocese_to_state)} entries")
    
    cath = sqlite3.connect(CATH_DB)
    cath.row_factory = sqlite3.Row
    
    # Get entries with missing/invalid states
    bad = cath.execute('''
        SELECT id, diocese, state, name FROM dir_entries 
        WHERE state IS NULL OR state = '' OR 
              state NOT IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC','PR','QC','AB','ON','BC','MB')
    ''').fetchall()
    
    print(f"Fixing {len(bad):,} entries...")
    
    fixed = 0
    for row in bad:
        diocese = row['diocese']
        if not diocese:
            continue
        
        # Try to find state
        state = None
        d_low = diocese.lower()
        if d_low in diocese_to_state:
            state = diocese_to_state[d_low]
        else:
            # Try partial match
            for k, v in diocese_to_state.items():
                if k in d_low or d_low in k:
                    state = v
                    break
        
        if state:
            cath.execute('UPDATE dir_entries SET state=? WHERE id=?', (state, row['id']))
            fixed += 1
    
    cath.commit()
    print(f"Fixed {fixed:,} entries")
    
    # Check remaining
    remaining = cath.execute('SELECT COUNT(*) FROM dir_entries WHERE state IS NULL OR state = ""').fetchone()[0]
    print(f"Still missing state: {remaining}")
    
    cath.close()

if __name__ == '__main__':
    main()
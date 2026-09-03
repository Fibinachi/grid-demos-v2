"""
Match all Catholic directory entries to GRID churches by name proximity.
Uses fuzzy matching since city/state fields are partially corrupted.
"""
import sqlite3, re
from collections import defaultdict

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"

def norm_name(s):
    """Normalize church name for matching."""
    if not s:
        return ''
    s = s.upper()
    s = re.sub(r"[^\w\s']", ' ', s)  # Remove punctuation but keep apostrophes
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r"'\s*S\s*", "'S ", s)  # St -> St
    s = re.sub(r'\bST\b', 'ST', s)
    return s

def main():
    cath = sqlite3.connect(CATH_DB)
    cath.row_factory = sqlite3.Row
    
    grid = sqlite3.connect(GRID_DB)
    grid.row_factory = sqlite3.Row
    
    # Build name index from GRID
    print("Building GRID name index...")
    grid_names = {}
    for r in grid.execute('SELECT id, name, city, state FROM churches WHERE name IS NOT NULL AND name != ""').fetchall():
        key = norm_name(r[1])
        if key:
            grid_names[key] = (r[0], (r[2] or '').upper(), (r[3] or '').upper())
    
    print(f"GRID index: {len(grid_names):,} names")
    
    # Get unmatched entries
    entries = cath.execute('''
        SELECT id, name, city, state, directory_year, diocese 
        FROM dir_entries 
        WHERE grid_church_id IS NULL AND name IS NOT NULL
    ''').fetchall()
    
    print(f"Matching {len(entries):,} entries...")
    
    matched = 0
    updates = []
    
    for e in entries:
        eid, name, city, state, year, diocese = e
        
        # Try exact normalized name match
        norm = norm_name(name)
        best_grid_id = None
        best_conf = None
        
        for gk, gv in grid_names.items():
            # Check if names overlap
            if norm in gk or gk in norm or len(set(norm.split()) & set(gk.split())) >= 2:
                best_grid_id = gv[0]
                # Same city check
                if city and gv[1] and city.upper() in gv[1]:
                    best_conf = 'high'
                else:
                    best_conf = 'medium'
                break
        
        if best_grid_id:
            matched += 1
            updates.append((best_grid_id, f'name_{best_conf}', eid))
        
        if len(updates) >= 5000:
            cath.executemany('UPDATE dir_entries SET grid_church_id=?, geocode_confidence=? WHERE id=?', updates)
            cath.commit()
            updates = []
    
    if updates:
        cath.executemany('UPDATE dir_entries SET grid_church_id=?, geocode_confidence=? WHERE id=?', updates)
        cath.commit()
    
    print(f"Matched {matched:,}")
    
    cath.close()
    grid.close()

if __name__ == '__main__':
    main()
"""
Match all Catholic directory entries to GRID by name (no GPS required).
"""
import sqlite3, re
from collections import defaultdict

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"

def norm_name(s):
    if not s:
        return ''
    s = s.upper()
    s = re.sub(r"[^\w\s']", ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def main():
    cath = sqlite3.connect(CATH_DB)
    cath.row_factory = sqlite3.Row
    
    grid = sqlite3.connect(GRID_DB)
    
    # Get entries without matches
    entries = cath.execute('SELECT id, name, state FROM dir_entries WHERE grid_church_id IS NULL').fetchall()
    print(f"Matching {len(entries):,} entries to GRID...")
    
    # Build name index
    name_to_ids = defaultdict(list)
    for r in grid.execute('SELECT id, name FROM churches WHERE name IS NOT NULL AND name != ""').fetchall():
        key = norm_name(r[1])[:40]
        if key:
            name_to_ids[key].append(r[0])
    
    matched = 0
    updates = []
    
    for row in entries:
        eid, name, state = row['id'], row['name'], row['state']
        if not name:
            continue
        
        norm = norm_name(name)
        
        # Try partial matches
        for gk in name_to_ids.keys():
            if norm in gk or gk in norm or len(set(norm.split()) & set(gk.split())) >= 2:
                gid = name_to_ids[gk][0]
                updates.append((gid, 'name_medium', eid))
                matched += 1
                break
        
        if len(updates) >= 5000:
            cath.executemany('UPDATE dir_entries SET grid_church_id=?, geocode_confidence=? WHERE id=?', updates)
            cath.commit()
            updates = []
            print(f"  Progress: {matched:,}")
    
    if updates:
        cath.executemany('UPDATE dir_entries SET grid_church_id=?, geocode_confidence=? WHERE id=?', updates)
        cath.commit()
    
    print(f"\nMatched {matched:,}")
    
    # Update stats
    total = cath.execute('SELECT COUNT(*) FROM dir_entries').fetchone()[0]
    mat = cath.execute('SELECT COUNT(*) FROM dir_entries WHERE grid_church_id IS NOT NULL').fetchone()[0]
    print(f"Total matched: {mat:,}/{total:,} ({100*mat/total:.1f}%)")
    
    cath.close()
    grid.close()

if __name__ == '__main__':
    main()
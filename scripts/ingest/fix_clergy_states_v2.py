"""
Build diocese-state mapping from catholic_hierarchy and fix imported clergy entries.
"""
import sqlite3

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"

def main():
    grid = sqlite3.connect(GRID_DB)
    cath = sqlite3.connect(CATH_DB)
    
    # Build diocese->state mapping from catholic_hierarchy
    mapping = {}
    for row in grid.execute('SELECT diocese, state FROM catholic_hierarchy WHERE diocese IS NOT NULL AND state IS NOT NULL').fetchall():
        d = row[0].upper().strip()
        s = row[1].strip().upper() if row[1] else None
        if s:
            mapping[d] = s
            # Also store normalized forms
            if 'ARCHDIOCESE' in d:
                norm = d.replace('ARCHDIOCESE OF ', '').replace('ARCHDIOCESE ', '').strip()
            elif 'DIOCESE' in d:
                norm = d.replace('DIOCESE OF ', '').replace('DIOCESE ', '').strip()
            else:
                norm = d
            mapping[norm] = s
    
    print(f"Built mapping for {len(mapping)} dioceses")
    
    # Fix entries
    entries = cath.execute('''
        SELECT id, diocese FROM dir_entries 
        WHERE state IS NULL AND diocese IS NOT NULL AND diocese != ''
    ''').fetchall()
    
    print(f"Fixing {len(entries):,} entries...")
    
    fixed = 0
    for eid, diocese in entries:
        d_upper = diocese.upper().strip()
        if d_upper in mapping:
            state = mapping[d_upper]
            cath.execute('UPDATE dir_entries SET state=? WHERE id=?', (state, eid))
            fixed += 1
        else:
            # Try partial match
            for k, v in mapping.items():
                if k in d_upper or d_upper in k:
                    cath.execute('UPDATE dir_entries SET state=? WHERE id=?', (v, eid))
                    fixed += 1
                    break
    
    cath.commit()
    print(f"Fixed {fixed:,} entries")
    
    # Check remaining
    remaining = cath.execute('SELECT COUNT(*) FROM dir_entries WHERE state IS NULL').fetchone()[0]
    print(f"Still missing state: {remaining}")
    
    cath.close()
    grid.close()

if __name__ == '__main__':
    main()
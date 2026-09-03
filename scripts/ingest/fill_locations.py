"""
Use later years (1938-2021) with GPS to infer city/state for earlier years.
"""
import sqlite3, csv, re
from collections import defaultdict

CATH_DB = "E:/grid/data/catholic_directory.db"
OUTPUT = "E:/grid/data/denom/catholic_directories_with_locations.csv"

def main():
    db = sqlite3.connect(CATH_DB)
    db.row_factory = sqlite3.Row
    
    # Build diocese->state,city mapping from entries with GPS/match
    diocese_info = defaultdict(lambda: {'states': set(), 'cities': set()})
    
    good_years = db.execute('''
        SELECT diocese, state, city FROM dir_entries 
        WHERE directory_year >= 1938 AND state IS NOT NULL AND state != ''
        AND grid_church_id IS NOT NULL
    ''').fetchall()
    
    for r in good_years:
        d = (r['diocese'] or '').lower().strip()
        s = (r['state'] or '').strip().upper()
        c = (r['city'] or '').lower().strip()
        if d and s:
            diocese_info[d]['states'].add(s)
            if c:
                diocese_info[d]['cities'].add(c)
    
    print(f"Dioceses with location data: {len(diocese_info)}")
    
    # Update entries without state/city
    updated = 0
    for r in db.execute('SELECT id, diocese, state, city FROM dir_entries WHERE state IS NULL OR state = ""').fetchall():
        d = (r['diocese'] or '').lower().strip()
        if d in diocese_info:
            info = diocese_info[d]
            state = list(info['states'])[0] if info['states'] else None
            city = list(info['cities'])[0] if info['cities'] else None
            
            if state:
                db.execute('UPDATE dir_entries SET state=? WHERE id=?', (state, r['id']))
            if city:
                db.execute('UPDATE dir_entries SET city=? WHERE id=?', (city, r['id']))
            updated += 1
    
    db.commit()
    print(f"Updated {updated:,} entries")
    
    # Export clean
    rows = db.execute('SELECT directory_year, name, diocese, state, city, grid_church_id FROM dir_entries ORDER BY directory_year').fetchall()
    
    with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['year', 'name', 'diocese', 'state', 'city', 'grid_church_id'])
        for r in rows:
            w.writerow([r['directory_year'], r['name'], r['diocese'], r['state'], r['city'], r['grid_church_id']])
    
    print(f"Exported {len(rows):,} to {OUTPUT}")
    
    db.close()

if __name__ == '__main__':
    main()
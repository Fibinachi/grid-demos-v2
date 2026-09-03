"""
Clean OCR errors in imported Catholic directory data and match to GRID churches.
"""
import sqlite3, math, time, re
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"
PROXIMITY_M = 500

US_STATES = {c.upper() for c in 'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split()}

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def load_grid_index():
    """Load GRID churches by state for proximity matching."""
    grid = sqlite3.connect(GRID_DB)
    grid.row_factory = sqlite3.Row
    
    rows = grid.execute('''
        SELECT id, name, city, state, latitude, longitude
        FROM churches
        WHERE latitude IS NOT NULL AND latitude != 0
          AND longitude IS NOT NULL AND longitude != 0
    ''').fetchall()
    
    # Build lookup by (state, city_upper, name_pattern)
    city_idx = {}
    for r in rows:
        st = (r['state'] or '').strip().upper()
        city = (r['city'] or '').strip().upper()
        if st and city:
            key = (st, city)
            if key not in city_idx:
                city_idx[key] = []
            city_idx[key].append(r)
    
    grid.close()
    return rows, city_idx

def find_best_match(name, city, state, grid_rows, city_idx):
    """Find best GRID match by name similarity in same city/state."""
    name_upper = name.upper().replace("'", '').replace('"', '').strip()
    
    candidates = city_idx.get((state.upper(), city.upper()), [])
    if not candidates:
        # Try without city filter
        for k, v in city_idx.items():
            if k[0] == state.upper() and city.upper() in k[1]:
                candidates.extend(v)
    
    if not candidates:
        return None, None
    
    # Find best match
    best = None
    best_dist = float('inf')
    
    for g in candidates:
        gname = g['name'].upper().replace("'", '').replace('"', '').strip()
        # Check if names overlap
        if name_upper in gname or gname in name_upper:
            return g['id'], 'high'
    
    return None, None

def main():
    cath = sqlite3.connect(CATH_DB)
    
    # Fix invalid states
    print("\n=== Fixing OCR state errors ===")
    fixes = cath.execute('''
        SELECT DISTINCT state, diocese 
        FROM dir_entries 
        WHERE state NOT IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC')
    ''').fetchall()
    
    # Map corrupted states to actual states based on diocese name
    state_map = {
        'Erie': 'PA', 'Buffalo': 'NY', 'Rochester': 'NY', 'Albany': 'NY',
        'Milwaukee': 'WI', 'San Juan': 'PR', 'Arecibo': 'PR', 'Boise': 'ID',
        'Chicago': 'IL', 'San Francisco': 'CA', 'Monrovia': 'CA', 'Durban': 'IN',
        'Quebec': 'QC', 'Santiago': 'PR', 'Jalapa': 'PR', 'Newark': 'NJ',
    }
    
    for old_state, diocese in fixes:
        # Look for the "real" state in the diocese name or nearby
        real_state = state_map.get(diocese, None)
        if real_state:
            print(f"  Fixing state '{old_state}' -> '{real_state}' for diocese '{diocese}'")
            cath.execute('UPDATE dir_entries SET state=? WHERE state=? AND diocese=?', (real_state, old_state, diocese))
            cath.commit()
    
    print("\n=== Matching to GRID ===")
    
    # Load GRID data
    grid_rows, city_idx = load_grid_index()
    print(f"Loaded {len(grid_rows):,} GRID churches")
    
    # Get entries to match
    cath.row_factory = sqlite3.Row
    entries = cath.execute('''
        SELECT id, name, city, state, directory_year 
        FROM dir_entries 
        WHERE grid_church_id IS NULL 
          AND name IS NOT NULL 
          AND name NOT LIKE '%Page %'
          AND state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC')
    ''').fetchall()
    
    print(f"Entries to match: {len(entries):,}")
    
    matched = 0
    multi = 0
    
    for e in entries:
        grid_id, conf = find_best_match(e['name'], e['city'], e['state'], grid_rows, city_idx)
        if grid_id:
            matched += 1
            cath.execute('UPDATE dir_entries SET grid_church_id=?, geocode_confidence=? WHERE id=?', 
                        (grid_id, conf or 'low', e['id']))
    
    cath.commit()
    print(f"Matched: {matched}")
    
    cath.close()

if __name__ == '__main__':
    main()
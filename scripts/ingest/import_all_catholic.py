"""
Import all Catholic directory years into catholic_directory.db.
1. Imports catholic_clergy assignments (1839-1946) as entries
2. Cleans OCR errors from parsed CSVs (1948-2020)
3. Matches all to GRID churches
"""
import csv, sqlite3, math, time
from pathlib import Path
from collections import defaultdict

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"
PARSED_DIR = Path("E:/grid/data/denom/catholic_official_parsed")

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def load_grid_index():
    """Build GRID index keyed by (state, city) for fast lookup."""
    grid = sqlite3.connect(GRID_DB)
    grid.row_factory = sqlite3.Row
    
    rows = grid.execute('''
        SELECT id, name, city, state, latitude, longitude
        FROM churches
        WHERE latitude IS NOT NULL AND latitude != 0
          AND longitude IS NOT NULL AND longitude != 0
    ''').fetchall()
    
    # Build (state, city) -> list of churches lookup
    city_idx = defaultdict(list)
    for r in rows:
        st = (r['state'] or '').strip().upper()
        city = (r['city'] or '').strip().upper()
        if st and city:
            city_idx[(st, city)].append(r)
    
    # Also build name index for fuzzy matching
    name_idx = defaultdict(list)
    for r in rows:
        name = r['name'].upper().strip()[:30] if r['name'] else ''
        if name:
            name_idx[name].append(r)
    
    grid.close()
    return city_idx, name_idx

def fix_state(diocese):
    """Map diocese to correct US state (handling OCR states)."""
    diocese_map = {
        'Erie': 'PA', 'Buffalo': 'NY', 'Rochester': 'NY', 'Albany': 'NY',
        'Milwaukee': 'WI', 'San Juan': 'PR', 'Arecibo': 'PR', 'Boise': 'ID',
        'Chicago': 'IL', 'San Francisco': 'CA', 'Monrovia': 'CA', 
        'Quebec': 'QC', 'Santiago': 'PR', 'Jalapa': 'PR', 'Newark': 'NJ',
    }
    return diocese_map.get(diocese, None)

def import_clergy_assignments():
    """Import catholic_clergy assignments as entries with clergy info."""
    db = sqlite3.connect('E:/grid/churches.db')
    db.row_factory = sqlite3.Row
    
    cath = sqlite3.connect(CATH_DB)
    
    # Find unique parish entries from catholic_clergy
    clergy_rows = db.execute('''
        SELECT DISTINCT year, diocese, city, parish FROM catholic_clergy
        ORDER BY year, diocese, city, parish
    ''').fetchall()
    
    print(f"\nImporting {len(clergy_rows):,} clergy parish entries...")
    
    # Get existing years in catholic_directory.db
    existing = set(r[0] for r in cath.execute(
        'SELECT DISTINCT directory_year FROM dir_entries'
    ).fetchall())
    
    added = 0
    for r in clergy_rows:
        year = r['year']
        # Skip if already imported
        if year in existing:
            continue
        
        city = r['city']
        state = ''
        if ',' in city:
            # City format "City, State" 
            parts = city.rsplit(',', 1)
            city = parts[0].strip()
            state = parts[1].strip()[:2].upper() if len(parts) > 1 else ''
        
        cath.execute('''
            INSERT INTO dir_entries (directory_year, source_entry_id, name, city, state, diocese, entity_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (year, f"clergy_{r['diocese']}_{r['parish'][:50]}", r['parish'],
              city, state, r['diocese'], 'parish',
              f"[Catholic Clergy {year}]"))
        added += 1
    
    cath.commit()
    cath.close()
    db.close()
    return added

def import_parsed_csvs():
    """Import and clean parsed CSVs (1948-2020)."""
    cath = sqlite3.connect(CATH_DB)
    
    # Get existing years
    existing = set(r[0] for r in cath.execute(
        'SELECT DISTINCT directory_year FROM dir_entries'
    ).fetchall())
    
    csvs = sorted(PARSED_DIR.glob('catholic_*.csv'))
    print(f"\nFound {len(csvs)} CSV files to import")
    
    total_added = 0
    for csv_path in csvs:
        year = int(csv_path.stem.split('_')[1])
        
        if year in existing:
            continue
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        
        # Fix state OCR issues
        for r in rows:
            bad_state = r.get('state', '')
            fixed_state = fix_state(r.get('diocese', ''))
            if fixed_state:
                r['state'] = fixed_state
        
        # Deduplicate
        seen = set()
        clean = []
        for r in rows:
            key = (year, r['diocese'], r['name'])
            if key not in seen:
                seen.add(key)
                clean.append(r)
        
        for r in clean:
            cath.execute('''
                INSERT INTO dir_entries (directory_year, source_entry_id, name, city, state, diocese, entity_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (year, f"parsed_{r['diocese']}_{r['name'][:50]}", r['name'],
                  r.get('city') or None, r.get('state') or None, r['diocese'], 'parish',
                  f"[Official Catholic Directory {year}]"))
        
        cath.commit()
        total_added += len(clean)
        print(f"  {year}: {len(clean):,}")
    
    cath.close()
    return total_added

def match_to_grid():
    """Match all dir_entries to GRID churches."""
    cath = sqlite3.connect(CATH_DB)
    cath.row_factory = sqlite3.Row
    
    city_idx, name_idx = load_grid_index()
    print(f"\nLoaded GRID index ({len(city_idx)} state/city pairs)")
    
    # Get unmatched entries with valid US states
    us_states = 'AL,AK,AZ,AR,CA,CO,CT,DE,FL,GA,HI,ID,IL,IN,IA,KS,KY,LA,ME,MD,MA,MI,MN,MS,MO,MT,NE,NV,NH,NJ,NM,NY,NC,ND,OH,OK,OR,PA,RI,SC,SD,TN,TX,UT,VT,VA,WA,WV,WI,WY,DC'
    entries = cath.execute(f'''
        SELECT id, name, city, state, directory_year 
        FROM dir_entries 
        WHERE grid_church_id IS NULL 
          AND name IS NOT NULL
          AND state IN ({','.join(['?' for _ in us_states.split(',')])})
    ''', us_states.split(',')).fetchall()
    
    print(f"Entries to match: {len(entries):,}")
    
    matched = 0
    updates = []
    
    for e in entries:
        name = e['name'].upper().strip()
        city = (e['city'] or '').upper().strip()
        state = (e['state'] or '').upper().strip()
        
        grid_id = None
        conf = None
        
        # Try (state, city) lookup first
        candidates = city_idx.get((state, city), [])
        if not candidates:
            # Try name prefix
            for i in range(20, min(50, len(name)) + 1):
                candidates = name_idx.get(name[:i], [])
                if candidates:
                    break
        
        if candidates:
            for c in candidates:
                gname = c['name'].upper()
                if name in gname or gname in name or c['city'].upper() == city:
                    grid_id = c['id']
                    conf = 'high' if c['city'].upper() == city else 'medium'
                    break
        
        if grid_id:
            matched += 1
            updates.append((grid_id, conf, e['id']))
        
        if len(updates) >= 5000:
            cath.executemany('UPDATE dir_entries SET grid_church_id=?, geocode_confidence=? WHERE id=?', updates)
            cath.commit()
            updates = []
    
    if updates:
        cath.executemany('UPDATE dir_entries SET grid_church_id=?, geocode_confidence=? WHERE id=?', updates)
        cath.commit()
    
    print(f"Matched: {matched:,}")
    cath.close()

if __name__ == '__main__':
    t0 = time.time()
    
    # import_clergy_assignments()
    # import_parsed_csvs()
    match_to_grid()
    
    print(f"\nDone in {time.time()-t0:.1f}s")
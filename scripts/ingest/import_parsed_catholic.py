"""
Import parsed Catholic directory CSVs into catholic_directory.db.
Cleans OCR issues, deduplicates, and matches to GRID churches.
"""
import csv, sqlite3, time, math
from pathlib import Path
from collections import defaultdict

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"
PARSED_DIR = Path("E:/grid/data/denom/catholic_official_parsed")
PROXIMITY_M = 500

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def clean_diocese(d, s):
    """Fix OCR diocese/state mixups."""
    d = d.strip()
    s = s.strip().upper()
    s = s.rstrip(',')
    if len(s) > 2:
        s = s[:2]
    # Common OCR fixes
    fixes = {
        'Tr': 'TX', 'El': 'TX', 'Md': 'MD', 'Pa': 'PA', 'Ny': 'NY',
        'Il': 'IL', 'Oh': 'OH', 'In': 'IN', 'Mi': 'MI', 'Wi': 'WI',
    }
    s = fixes.get(s.upper(), s.upper())
    return d, s

def clean_city(city):
    """Clean city field - remove OCR artifacts."""
    if not city:
        return ''
    city = city.strip()
    # Remove numbers mistakenly in city field
    if city.isdigit():
        return ''
    if ',' in city:
        city = city.split(',')[0].strip()
    return city

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
    
    state_idx = defaultdict(list)
    for r in rows:
        st = (r['state'] or '').strip().upper()
        state_idx[st].append({
            'id': r['id'],
            'name': r['name'],
            'city': (r['city'] or '').strip().upper(),
            'lat': r['latitude'],
            'lon': r['longitude'],
        })
    
    grid.close()
    return state_idx

def find_grid_match(name, city, state, state_idx):
    """Find closest GRID church by proximity."""
    candidates = state_idx.get(state, [])
    if not candidates:
        return None, None
    
    # Try fuzzy name match first
    name_upper = name.upper().replace("'", '').replace(',', '').strip()
    
    # Extract city from name if embedded (e.g., "St. X, Y" -> city=Y)
    if ',' in name_upper:
        parts = name_upper.split(',')
        potential_city = parts[-1].strip()
        if potential_city not in ['NJ', 'NY', 'CA', 'TX', 'PA'] and len(potential_city) > 2:
            city = potential_city
    
    best_dist = float('inf')
    best_match = None
    
    for cand in candidates:
        if city and cand['city'] and city.upper() == cand['city'].upper():
            # Same city - close match
            return cand['id'], 'high'
        
        # Check if name contains church name or vice versa
        cand_upper = cand['name'].upper().replace("'", '').replace(',', '').strip()
        if name_upper in cand_upper or cand_upper in name_upper:
            return cand['id'], 'medium'
        
        # No GPS in parsed data, so just check if city matches
        if cand['city'] and city and cand['city'].upper() == city.upper():
            return cand['id'], 'medium'
    
    return None, None

def main():
    cath = sqlite3.connect(CATH_DB)
    cath.row_factory = sqlite3.Row
    
    # Get years already in DB
    existing = set(r[0] for r in cath.execute(
        'SELECT DISTINCT directory_year FROM dir_entries'
    ).fetchall())
    print(f"Years already in DB: {sorted(existing)}")
    
    # Load GRID index
    print("Loading GRID index...", end=' ', flush=True)
    state_idx = load_grid_index()
    print(f"done ({len(state_idx)} states)")
    
    # Process each CSV
    csvs = sorted(PARSED_DIR.glob('catholic_*.csv'))
    print(f"Found {len(csvs)} CSV files to import\n")
    
    total_added = 0
    total_matched = 0
    
    for csv_path in csvs:
        year = int(csv_path.stem.split('_')[1])
        
        if year in existing:
            print(f"  {year}: already exists in DB, skipping")
            continue
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        
        print(f"  {year}: {len(rows)} records", end=' ', flush=True)
        
        # Clean and deduplicate
        seen = set()
        clean_rows = []
        for r in rows:
            name = r['name'].strip()
            if not name or any(x in name for x in ['Page ', 'Copyright', 'Advertis']):
                continue
            
            diocese = r['diocese']
            state = r['state']
            
            # Skip obvious garbage
            if diocese and state and len(state) > 2 and ',' not in state:
                # Likely OCR error - "Md," or "Pa," in wrong place
                continue
            
            diocese_clean, state_clean = clean_diocese(diocese, state)
            city_clean = clean_city(r.get('city', ''))
            
            key = (year, diocese_clean, name)
            if key in seen:
                continue
            seen.add(key)
            
            clean_rows.append({
                'year': year,
                'diocese': diocese_clean,
                'state': state_clean,
                'city': city_clean,
                'name': name,
            })
        
        print(f"-> {len(clean_rows)} after dedup/clean")
        
        # Insert into DB
        for r in clean_rows:
            cath.execute('''
                INSERT INTO dir_entries (directory_year, source_entry_id, name, city, state, diocese, entity_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (r['year'], f"{r['diocese']}_{r['name'][:50]}", r['name'], 
                  r['city'] or None, r['state'] or None, r['diocese'], 'parish',
                  f"[Official Catholic Directory {year}]"))
        
        cath.commit()
        total_added += len(clean_rows)
    
    print(f"\nTotal added: {total_added}")
    cath.close()

if __name__ == '__main__':
    main()
"""
Geocode Catholic directory entries using geonames_places city coordinates.
Matches by (city_upper, state) → lat/lon from geonames_places.
Falls back to Nominatim for unmatched places (non-US, small towns).
"""
import sqlite3, time, requests, json
from collections import defaultdict

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

def progress_bar(current, total, width=40):
    if total == 0: return f"[{'█'*width}] {current}/{current} (100%)"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

# ── Step 1: Load geonames index ────────────────────────────────────
print("Loading geonames_places into memory...")
grid = sqlite3.connect(GRID_DB)
grid.row_factory = sqlite3.Row

geo_rows = grid.execute('''
    SELECT name, admin1, country_code, latitude, longitude, population
    FROM geonames_places
    WHERE country_code IN ('US', 'CA', 'PR', 'GU', 'VI', 'AS', 'MP', 'FM', 'MH', 'PW')
      AND admin1 IS NOT NULL
''').fetchall()
grid.close()

# Build index: (name_upper, admin1) → best coordinate (highest population)
geo_idx = {}  # (name_upper, admin1) → (lat, lon, population)
for r in geo_rows:
    key = (r['name'].strip().upper(), r['admin1'].strip().upper())
    pop = r['population'] or 0
    if key not in geo_idx or pop > geo_idx[key][2]:
        geo_idx[key] = (r['latitude'], r['longitude'], pop)

print(f"  Indexed {len(geo_idx):,} unique city+state combos")
print(f"  (from {len(geo_rows):,} geonames records)")

# ── Step 2: Match dir_entries ──────────────────────────────────────
cath = sqlite3.connect(CATH_DB)
cath.row_factory = sqlite3.Row

rows = cath.execute('''
    SELECT id, city, state, directory_year
    FROM dir_entries
    WHERE latitude IS NULL
      AND city IS NOT NULL AND city != ''
      AND state IS NOT NULL AND state != ''
      AND LENGTH(city) > 2
    ORDER BY directory_year, id
''').fetchall()

print(f"\nMatching {len(rows):,} ungeocoded entries against geonames...")

matched_geo = 0
unmatched = []
updates = []

t0 = time.time()
for r in rows:
    eid, city, state, year = r['id'], r['city'], r['state'], r['directory_year']
    key = (city.strip().upper(), state.strip().upper())
    
    coords = geo_idx.get(key)
    if coords:
        lat, lon, pop = coords
        source = f'geonames_pop{pop}'
        updates.append((lat, lon, source, eid))
        matched_geo += 1
    else:
        unmatched.append(r)
    
    if len(updates) >= 1000:
        cath.executemany('UPDATE dir_entries SET latitude = ?, longitude = ?, geocode_source = ? WHERE id = ?', updates)
        cath.commit()
        updates.clear()
        print(f"  {progress_bar(matched_geo + len(unmatched), len(rows))} "
              f"geonames: {matched_geo}, todo: {len(unmatched)}", flush=True)

if updates:
    cath.executemany('UPDATE dir_entries SET latitude = ?, longitude = ?, geocode_source = ? WHERE id = ?', updates)
    cath.commit()
    updates.clear()

elapsed = time.time() - t0
print(f"\n  Step 1 done in {elapsed:.1f}s")
print(f"  Matched via geonames: {matched_geo}/{len(rows)} ({100*matched_geo/len(rows):.1f}%)")
print(f"  Unmatched: {len(unmatched)}")

# ── Step 3: Nominatim fallback for unmatched ───────────────────────
if unmatched:
    print(f"\n  Nominatim fallback for {len(unmatched)} unmatched entries...")
    
    # Deduplicate to unique city+state queries
    unique_queries = {}
    for r in unmatched:
        key = (r['city'].strip().upper(), r['state'].strip().upper())
        if key not in unique_queries:
            unique_queries[key] = []
        unique_queries[key].append(r['id'])
    
    print(f"    {len(unique_queries)} unique city+state queries")
    
    nom_matched = 0
    nom_total = len(unique_queries)
    updates = []
    
    for i, ((city_up, state_up), ids) in enumerate(unique_queries.items()):
        query = f"{city_up.title()}, {state_up}"
        
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={'q': query, 'format': 'json', 'limit': 1, 'addressdetails': 0},
                headers={'User-Agent': 'GRID/1.0 (grid-project)'},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    lat = float(data[0].get('lat', 0))
                    lon = float(data[0].get('lon', 0))
                    if lat and lon:
                        for eid in ids:
                            updates.append((lat, lon, 'nominatim_fallback', eid))
                        nom_matched += 1
        except Exception:
            pass
        
        if (i+1) % 200 == 0:
            print(f"      {progress_bar(i+1, nom_total)} matched: {nom_matched}", flush=True)
        
        if len(updates) >= 500:
            cath.executemany('UPDATE dir_entries SET latitude = ?, longitude = ?, geocode_source = ? WHERE id = ?', updates)
            cath.commit()
            updates.clear()
        
        time.sleep(0.3)  # Nominatim rate limit
    
    if updates:
        cath.executemany('UPDATE dir_entries SET latitude = ?, longitude = ?, geocode_source = ? WHERE id = ?', updates)
        cath.commit()
        updates.clear()
    
    print(f"\n    Nominatim matched {nom_matched}/{nom_total} unique cities")
    print(f"    Remaining unmatched entries: {len(rows) - matched_geo - sum(len(ids) for _, ids in unique_queries.items() if all(False for _ in ids))}")

# ── Final summary ──────────────────────────────────────────────────
total_with_gps = cath.execute('SELECT COUNT(*) FROM dir_entries WHERE latitude IS NOT NULL').fetchone()[0]
total_all = cath.execute('SELECT COUNT(*) FROM dir_entries').fetchone()[0]
print(f"\n{'='*60}")
print(f"Final: {total_with_gps:,}/{total_all:,} entries now have GPS")
print(f"       ({100*total_with_gps/total_all:.1f}%)")

# By geocode source
print(f"\n  Geocode source breakdown:")
for r in cath.execute('SELECT geocode_source, COUNT(*) as cnt FROM dir_entries WHERE geocode_source IS NOT NULL GROUP BY geocode_source ORDER BY cnt DESC').fetchall():
    print(f"    {r['geocode_source']}: {r['cnt']}")

cath.close()
print(f"\nDone.")

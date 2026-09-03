"""
Geocode Catholic directory parishes via Census batch API, then proximity-match to GRID.
Two passes:
  1. Forward-geocode ~1,900 records with address+city but no GPS
  2. Proximity-match ALL ~35K records with GPS (city centroids + newly geocoded) against churches.db

Saves grid_church_id on dir_entries for matched records.
"""
import sqlite3, time, requests, math, sys
from pathlib import Path

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BATCH_SIZE = 500
PROXIMITY_THRESHOLD_M = 300
CENSUS_TIMEOUT = 180
MAX_RETRIES = 3

def progress_bar(current, total, width=40):
    if total == 0:
        return f"[{'█'*width}] {current}/{current} (100%)"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ── Phase 1: Geocode ───────────────────────────────────────────────
def geocode_catholic():
    conn = sqlite3.connect(CATH_DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute('''
        SELECT id, name, address, city, state
        FROM dir_entries
        WHERE latitude IS NULL
          AND address IS NOT NULL AND address != ''
          AND city IS NOT NULL AND city != ''
          AND state IS NOT NULL AND state != ''
        ORDER BY state, id
    ''').fetchall()

    print(f"\n{'='*60}")
    print(f"Phase 1: Geocoding {len(rows)} Catholic directory records via Census API")
    print(f"{'='*60}")

    if not rows:
        print("  Nothing to geocode.")
        conn.close()
        return

    geocoded = 0
    failed = 0

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]

        lines = []
        for r in batch:
            street = (r['address'] or '').strip()
            city = (r['city'] or '').strip()
            state = (r['state'] or '').strip()
            lines.append(f'{r["id"]},"{street}","{city}","{state}",""')

        body = '\n'.join(lines)

        print(f"\n  Batch {batch_start//BATCH_SIZE + 1}/{(len(rows)-1)//BATCH_SIZE + 1} "
              f"({len(batch)} records)...", end=' ', flush=True)

        ok = False
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    CENSUS_URL,
                    data={'benchmark': 'Public_AR_Current', 'vintage': 'Current_Current'},
                    files={'addressFile': ('addresses.csv', body.encode('utf-8'))},
                    timeout=CENSUS_TIMEOUT
                )
                if resp.status_code == 200 and resp.text and not resp.text.startswith('<'):
                    ok = True
                    break
                else:
                    print(f"\n    Attempt {attempt+1}: HTTP {resp.status_code}/{len(resp.text)}b, retrying...")
                    time.sleep(5)
            except Exception as e:
                print(f"\n    Attempt {attempt+1}: {type(e).__name__}, retrying...")
                time.sleep(5)

        if not ok:
            print(f"FAILED after {MAX_RETRIES} attempts")
            failed += len(batch)
            continue

        text = resp.text

        updates = []
        for line in text.strip().split('\n'):
            parts = line.strip().split(',')
            if len(parts) < 6:
                continue
            try:
                rid = int(parts[0].strip('"'))
            except (ValueError, IndexError):
                continue
            match_type = parts[2].strip('"') if len(parts) > 2 else ''
            try:
                lat = float(parts[4].strip('"')) if parts[4].strip('"') else None
                lon = float(parts[5].strip('"')) if parts[5].strip('"') else None
            except (ValueError, IndexError):
                lat = lon = None

            if lat and lon:
                updates.append((lat, lon, 'census_forward', f'census_{match_type}', rid))

        conn.executemany('''
            UPDATE dir_entries
            SET latitude = ?, longitude = ?, geocode_source = ?, geocode_confidence = ?
            WHERE id = ?
        ''', updates)
        conn.commit()

        n_ok = len(updates)
        geocoded += n_ok
        n_fail = len(batch) - n_ok
        failed += n_fail
        print(f"{progress_bar(batch_start + len(batch), len(rows))} "
              f"ok {n_ok} fail {n_fail}")

        time.sleep(0.5)

    conn.close()
    print(f"\n  Phase 1 done: {geocoded} geocoded, {failed} failed")

# ── Phase 2: Proximity Match ───────────────────────────────────────
def match_catholic_to_grid():
    cath = sqlite3.connect(CATH_DB)
    cath.row_factory = sqlite3.Row
    grid = sqlite3.connect(GRID_DB)
    grid.row_factory = sqlite3.Row

    cath_rows = cath.execute('''
        SELECT id, name, city, state, latitude, longitude,
               entity_type, directory_year
        FROM dir_entries
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY id
    ''').fetchall()

    print(f"\n{'='*60}")
    print(f"Phase 2: Proximity-matching {len(cath_rows):,} Catholic directory records to GRID")
    print(f"{'='*60}")

    if not cath_rows:
        print("  No records with GPS to match.")
        cath.close()
        grid.close()
        return

    print("  Loading GRID churches with GPS into memory...", end=' ', flush=True)
    grid_rows = grid.execute('''
        SELECT id, name, city, state, latitude, longitude
        FROM churches
        WHERE latitude IS NOT NULL AND latitude != 0
          AND longitude IS NOT NULL AND longitude != 0
    ''').fetchall()
    print(f"{len(grid_rows):,} loaded")

    state_index = {}
    for g in grid_rows:
        st = (g['state'] or '').strip().upper()
        state_index.setdefault(st, []).append({
            'id': g['id'],
            'name': g['name'],
            'city': (g['city'] or '').strip().upper(),
            'lat': g['latitude'],
            'lon': g['longitude'],
        })

    matches_found = 0
    total_processed = 0
    no_gps_in_state = 0
    updates = []

    for cr in cath_rows:
        total_processed += 1
        cath_id = cr['id']
        lat = cr['latitude']
        lon = cr['longitude']
        state = (cr['state'] or '').strip().upper()
        city = (cr['city'] or '').strip().upper()

        if total_processed % 2000 == 0:
            print(f"  {progress_bar(total_processed, len(cath_rows))} "
                  f"matched: {matches_found}", flush=True)

        candidates = state_index.get(state, [])
        if not candidates:
            no_gps_in_state += 1
            continue

        best_dist = float('inf')
        best_match = None

        for c in candidates:
            dist = haversine_km(lat, lon, c['lat'], c['lon'])
            if dist < best_dist:
                best_dist = dist
                best_match = c

        best_dist_m = best_dist * 1000

        if best_dist_m <= PROXIMITY_THRESHOLD_M and best_match:
            matches_found += 1
            same_city = (best_match['city'] == city) if city else False
            confidence = 'high' if same_city else 'medium'
            updates.append((best_match['id'], f'proximity_{confidence}_{best_dist_m:.0f}m', cath_id))

    if updates:
        cath.executemany('''
            UPDATE dir_entries
            SET grid_church_id = ?, geocode_confidence = ?
            WHERE id = ?
        ''', updates)
        cath.commit()

    print(f"\n  {progress_bar(total_processed, len(cath_rows))} matched: {matches_found}")
    print(f"  No GRID churches in state: {no_gps_in_state}")

    print(f"\n  Match summary by year:")
    year_counts = cath.execute('''
        SELECT directory_year,
               COUNT(*) as total,
               SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as matched
        FROM dir_entries
        WHERE latitude IS NOT NULL
        GROUP BY directory_year
        ORDER BY directory_year
    ''').fetchall()
    for r in year_counts:
        pct = 100 * r['matched'] / r['total'] if r['total'] > 0 else 0
        print(f"    {r['directory_year']}: {r['matched']}/{r['total']} ({pct:.0f}%)")

    print(f"\n  Match summary by entity type:")
    type_counts = cath.execute('''
        SELECT entity_type,
               COUNT(*) as total,
               SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as matched
        FROM dir_entries
        WHERE latitude IS NOT NULL
        GROUP BY entity_type
        ORDER BY total DESC
        LIMIT 10
    ''').fetchall()
    for r in type_counts:
        pct = 100 * r['matched'] / r['total'] if r['total'] > 0 else 0
        print(f"    {r['entity_type']}: {r['matched']}/{r['total']} ({pct:.0f}%)")

    print(f"\n  Match rate by geocode source:")
    source_counts = cath.execute('''
        SELECT geocode_source,
               COUNT(*) as total,
               SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as matched
        FROM dir_entries
        WHERE latitude IS NOT NULL AND geocode_source IS NOT NULL
        GROUP BY geocode_source
        ORDER BY total DESC
    ''').fetchall()
    for r in source_counts:
        pct = 100 * r['matched'] / r['total'] if r['total'] > 0 else 0
        print(f"    {r['geocode_source']}: {r['matched']}/{r['total']} ({pct:.0f}%)")

    cath.close()
    grid.close()
    print(f"\n  Phase 2 done: {matches_found} proximity matches found")

# ── Main ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    t0 = time.time()
    geocode_catholic()
    match_catholic_to_grid()
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"Done in {elapsed/60:.1f} min")
    print(f"{'='*60}")

"""
Geocode WPA directory churches via Census batch API, then proximity-match to GRID.
Two passes:
  1. Forward-geocode addresses without GPS (~6K geocodable)
  2. Proximity-match ALL WPA records with GPS (existing + newly geocoded) against churches.db

Strategy:
  - Census batch API for US addresses (address + city + state)
  - Haversine proximity match (≤300m → high confidence, ≤500m → medium)
  - Saves matches to wpa_matches table
  - Reports match rate by state
"""
import sqlite3, time, requests, re, sys, math
from pathlib import Path

WPA_DB = "E:/grid/wpa.db"
GRID_DB = "E:/grid/churches.db"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BATCH_SIZE = 500
PROXIMITY_THRESHOLD_M = 300  # meters for high-confidence match

def progress_bar(current, total, width=40):
    if total == 0:
        return f"[{'█'*width}] {current}/{current} (100%)"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ── Phase 1: Geocode ───────────────────────────────────────────────
def geocode_wpa():
    """Forward-geocode ungeocoded WPA records via Census batch API."""
    conn = sqlite3.connect(WPA_DB)
    conn.row_factory = sqlite3.Row
    
    # Get ungeocoded records with address+city
    rows = conn.execute('''
        SELECT id, church_name, address, city, state
        FROM wpa_deepseek_parsed
        WHERE latitude IS NULL
          AND address IS NOT NULL AND address != ''
          AND city IS NOT NULL AND city != ''
          AND state IS NOT NULL AND state != ''
        ORDER BY state, id
    ''').fetchall()
    
    print(f"\n{'='*60}")
    print(f"Phase 1: Geocoding {len(rows)} WPA records via Census API")
    print(f"{'='*60}")
    
    if not rows:
        print("  Nothing to geocode.")
        conn.close()
        return
    
    geocoded = 0
    failed = 0
    
    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]
        
        # Build Census batch format: unique_id, street, city, state, zip
        lines = []
        for r in batch:
            street = (r['address'] or '').strip()
            city = (r['city'] or '').strip()
            state = (r['state'] or '').strip()
            lines.append(f'{r["id"]},"{street}","{city}","{state}",""')
        
        body = '\n'.join(lines)
        
        print(f"\n  Batch {batch_start//BATCH_SIZE + 1}/{(len(rows)-1)//BATCH_SIZE + 1} "
              f"({len(batch)} records)...", end=' ', flush=True)
        
        try:
            resp = requests.post(
                CENSUS_URL,
                data={'benchmark': 'Public_AR_Current', 'vintage': 'Current_Current'},
                files={'addressFile': ('addresses.csv', body.encode('utf-8'))},
                timeout=120
            )
        except Exception as e:
            print(f"REQ ERROR: {e}")
            time.sleep(5)
            failed += len(batch)
            continue
        
        text = resp.text
        if not text or text.startswith('<'):
            print(f"HTML response (likely error) — first 200 chars:")
            print(f"  {text[:200]}")
            time.sleep(3)
            failed += len(batch)
            continue
        
        # Parse Census response
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
                updates.append((lat, lon, 'census_forward', f'{match_type}', rid))
        
        # Apply updates
        conn.executemany('''
            UPDATE wpa_deepseek_parsed
            SET latitude = ?, longitude = ?, geocode_source = ?, geocode_match = ?
            WHERE id = ?
        ''', updates)
        conn.commit()
        
        n_ok = len(updates)
        geocoded += n_ok
        n_fail = len(batch) - n_ok
        failed += n_fail
        print(f"{progress_bar(batch_start + len(batch), len(rows))} "
              f" OK={n_ok} geocoded, Fail={n_fail}")
        
        time.sleep(0.3)  # Rate limit
    
    conn.close()
    print(f"\n  ✅ Phase 1 done: {geocoded} geocoded, {failed} failed")

# ── Phase 2: Proximity Match ───────────────────────────────────────
def match_wpa_to_grid():
    """Match all WPA records with GPS against churches.db by proximity."""
    wpa = sqlite3.connect(WPA_DB)
    wpa.row_factory = sqlite3.Row
    grid = sqlite3.connect(GRID_DB)
    grid.row_factory = sqlite3.Row
    
    # Get all WPA records with GPS
    wpa_rows = wpa.execute('''
        SELECT id, church_name, city, state, latitude, longitude
        FROM wpa_deepseek_parsed
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY id
    ''').fetchall()
    
    print(f"\n{'='*60}")
    print(f"Phase 2: Proximity-matching {len(wpa_rows)} GPS-able WPA records to GRID")
    print(f"{'='*60}")
    
    if not wpa_rows:
        print("  No WPA records with GPS to match.")
        wpa.close()
        grid.close()
        return
    
    # Load all GRID churches with GPS into memory for speed
    print("  Loading GRID churches with GPS into memory...", end=' ', flush=True)
    grid_rows = grid.execute('''
        SELECT id, name, city, state, latitude, longitude
        FROM churches
        WHERE latitude IS NOT NULL AND latitude != 0
          AND longitude IS NOT NULL AND longitude != 0
    ''').fetchall()
    print(f"{len(grid_rows):,} loaded")
    
    # Build spatial index: dict of state -> list of churches in that state
    state_index = {}
    for g in grid_rows:
        st = (g['state'] or '').strip().upper()
        state_index.setdefault(st, []).append({
            'id': g['id'],
            'name': g['name'],
            'city': (g['city'] or '').strip().upper(),
            'state': st,
            'lat': g['latitude'],
            'lon': g['longitude'],
        })
    
    matches_found = 0
    no_gps_in_state = 0
    total_processed = 0
    
    # Pre-clear old WPA matches (optional - we add new ones)
    # We'll just count, not overwrite existing matches
    
    for wr in wpa_rows:
        total_processed += 1
        wpa_id = wr['id']
        wpa_lat = wr['latitude']
        wpa_lon = wr['longitude']
        wpa_state = (wr['state'] or '').strip().upper()
        wpa_city = (wr['city'] or '').strip().upper()
        wpa_name = (wr['church_name'] or '').strip()
        
        if total_processed % 500 == 0:
            print(f"  {progress_bar(total_processed, len(wpa_rows))} "
                  f"matched: {matches_found}", flush=True)
        
        # Get candidate GRID churches in same state
        candidates = state_index.get(wpa_state, [])
        if not candidates:
            no_gps_in_state += 1
            continue
        
        # Find nearest using haversine
        best_dist = float('inf')
        best_match = None
        
        for c in candidates:
            dist = haversine_km(wpa_lat, wpa_lon, c['lat'], c['lon'])
            if dist < best_dist:
                best_dist = dist
                best_match = c
        
        best_dist_m = best_dist * 1000  # convert to meters
        
        if best_dist_m <= PROXIMITY_THRESHOLD_M and best_match:
            matches_found += 1
            # Check if match already exists
            existing = wpa.execute(
                'SELECT id FROM wpa_matches WHERE wpa_record_id = ?', (wpa_id,)
            ).fetchone()
            if not existing:
                # Check if name also has city overlap for extra confidence
                same_city = (best_match['city'] == wpa_city) if wpa_city else False
                name_overlap = False
                if wpa_name and best_match['name']:
                    wpa_words = set(wpa_name.lower().split()[:4])
                    grid_words = set(best_match['name'].lower().split()[:4])
                    name_overlap = len(wpa_words & grid_words) >= 2
                
                match_method = 'proximity_high' if (same_city or name_overlap) else 'proximity'
                match_score = round(1.0 - (best_dist_m / PROXIMITY_THRESHOLD_M), 2)
                
                wpa.execute('''
                    INSERT OR IGNORE INTO wpa_matches
                        (wpa_record_id, church_id, match_method, match_score, notes)
                    VALUES (?, ?, ?, ?, ?)
                ''', (wpa_id, best_match['id'], match_method, match_score,
                      f"GPS proximity {best_dist_m:.0f}m; state={wpa_state}"))
            
    wpa.commit()
    
    print(f"\n  {progress_bar(total_processed, len(wpa_rows))} "
          f"matched: {matches_found}")
    print(f"  No GRID churches in state: {no_gps_in_state}")
    
    # Summary by state
    print(f"\n  Match summary by state:")
    state_counts = wpa.execute('''
        SELECT d.state,
               COUNT(DISTINCT d.id) as total,
               COUNT(DISTINCT m.id) as matched
        FROM wpa_deepseek_parsed d
        LEFT JOIN wpa_matches m ON d.id = m.wpa_record_id
        WHERE d.latitude IS NOT NULL
        GROUP BY d.state
        ORDER BY total DESC
    ''').fetchall()
    for r in state_counts:
        pct = 100 * r['matched'] / r['total'] if r['total'] > 0 else 0
        print(f"    {r['state']}: {r['matched']}/{r['total']} ({pct:.0f}%)")
    
    wpa.close()
    grid.close()
    print(f"\n  ✅ Phase 2 done: {matches_found} proximity matches found")

# ── Main ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    t0 = time.time()
    
    geocode_wpa()
    match_wpa_to_grid()
    
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"✅ All done in {elapsed/60:.1f} min")
    print(f"{'='*60}")

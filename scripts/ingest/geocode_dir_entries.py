"""
Geocode Catholic directory entries with clean city+state but no GPS.
Uses Census single-address API (threaded) for US addresses,
Nominatim for non-US addresses.

Threaded for speed: 8 workers for Census, 4 for Nominatim.
"""
import sqlite3, time, requests, json, re, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

CATH_DB = "E:/grid/data/catholic_directory.db"
GRID_DB = "E:/grid/churches.db"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CENSUS_WORKERS = 8
NOMINATIM_WORKERS = 4
BATCH_COMMIT = 500

# US state abbreviations
US_STATES = {'AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN',
             'IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH',
             'NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT',
             'VT','VA','WA','WV','WI','WY','PR','VI','GU','AS','MP'}

# Canadian provinces
CA_PROVINCES = {'AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT'}

def progress_bar(current, total, width=40):
    if total == 0: return f"[{'█'*width}] {current}/{current} (100%)"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

def geocode_census(city, state):
    """Geocode US city+state via Census single-address API."""
    addr = f"{city}, {state}"
    try:
        resp = requests.get(
            CENSUS_URL,
            params={'benchmark': 'Public_AR_Current', 'format': 'json',
                    'address': addr},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('result') and data['result'].get('addressMatches'):
                match = data['result']['addressMatches'][0]
                coords = match.get('coordinates', {})
                lat = coords.get('y')
                lon = coords.get('x')
                if lat and lon:
                    return (lat, lon, 'census_city')
        return (None, None, None)
    except Exception:
        return (None, None, None)

def geocode_nominatim(city, state_code, country_hint=''):
    """Geocode via Nominatim."""
    q = f"{city}, {state_code}"
    if country_hint:
        q += f", {country_hint}"
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={'q': q, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'GRID/1.0 (grid-project)'},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                lat = float(data[0].get('lat', 0))
                lon = float(data[0].get('lon', 0))
                if lat and lon:
                    return (lat, lon, 'nominatim_city')
        return (None, None, None)
    except Exception:
        return (None, None, None)

def main():
    conn = sqlite3.connect(CATH_DB)
    conn.row_factory = sqlite3.Row
    
    # Get ungeocoded entries with clean city+state
    rows = conn.execute('''
        SELECT id, city, state, directory_year
        FROM dir_entries
        WHERE latitude IS NULL
          AND city IS NOT NULL AND city != ''
          AND state IS NOT NULL AND state != ''
          AND LENGTH(city) > 2
        ORDER BY directory_year, id
    ''').fetchall()
    
    print(f"Geocoding {len(rows)} entries...")
    
    # Separate US and non-US
    us_rows = [r for r in rows if r['state'] in US_STATES]
    ca_rows = [r for r in rows if r['state'] in CA_PROVINCES]
    other_rows = [r for r in rows if r['state'] not in US_STATES and r['state'] not in CA_PROVINCES]
    
    print(f"  US: {len(us_rows)}, Canada: {len(ca_rows)}, Other: {len(other_rows)}")
    
    total_geocoded = 0
    total_processed = 0
    t0 = time.time()
    
    # --- Geocode US via Census (threaded) ---
    if us_rows:
        print(f"\n  Geocoding US entries ({len(us_rows)}) via Census API...")
        us_done = 0
        with ThreadPoolExecutor(max_workers=CENSUS_WORKERS) as ex:
            fut_map = {}
            for r in us_rows:
                fut = ex.submit(geocode_census, r['city'], r['state'])
                fut_map[fut] = r['id']
            
            updates = []
            for fut in as_completed(fut_map):
                eid = fut_map[fut]
                us_done += 1
                lat, lon, source = fut.result()
                if lat and lon:
                    updates.append((lat, lon, source, eid))
                    total_geocoded += 1
                
                if us_done % 500 == 0:
                    print(f"    {progress_bar(us_done, len(us_rows))} geocoded: {total_geocoded}", flush=True)
                
                if len(updates) >= BATCH_COMMIT:
                    conn.executemany('''
                        UPDATE dir_entries
                        SET latitude = ?, longitude = ?, geocode_source = ?
                        WHERE id = ?
                    ''', updates)
                    conn.commit()
                    updates.clear()
            
            # Final batch
            if updates:
                conn.executemany('''
                    UPDATE dir_entries
                    SET latitude = ?, longitude = ?, geocode_source = ?
                    WHERE id = ?
                ''', updates)
                conn.commit()
                updates.clear()
    
    # --- Geocode Canada via Nominatim (threaded) ---
    if ca_rows:
        print(f"\n  Geocoding Canadian entries ({len(ca_rows)}) via Nominatim...")
        ca_done = 0
        with ThreadPoolExecutor(max_workers=NOMINATIM_WORKERS) as ex:
            fut_map = {}
            for r in ca_rows:
                fut = ex.submit(geocode_nominatim, r['city'], r['state'], 'Canada')
                fut_map[fut] = r['id']
            
            updates = []
            for fut in as_completed(fut_map):
                eid = fut_map[fut]
                ca_done += 1
                lat, lon, source = fut.result()
                if lat and lon:
                    updates.append((lat, lon, source, eid))
                    total_geocoded += 1
                
                if ca_done % 200 == 0:
                    print(f"    {progress_bar(ca_done, len(ca_rows))} geocoded: {total_geocoded}", flush=True)
                
                if len(updates) >= BATCH_COMMIT:
                    conn.executemany('UPDATE dir_entries SET latitude = ?, longitude = ?, geocode_source = ? WHERE id = ?', updates)
                    conn.commit()
                    updates.clear()
            
            if updates:
                conn.executemany('UPDATE dir_entries SET latitude = ?, longitude = ?, geocode_source = ? WHERE id = ?', updates)
                conn.commit()
                updates.clear()
    
    # --- Geocode other via Nominatim (threaded) ---
    if other_rows:
        print(f"\n  Geocoding other entries ({len(other_rows)}) via Nominatim...")
        other_done = 0
        with ThreadPoolExecutor(max_workers=NOMINATIM_WORKERS) as ex:
            fut_map = {}
            for r in other_rows:
                # Determine country from state code (approximate)
                country_hint = ''
                if r['state'] in ('FM', 'MH', 'PW', 'MP', 'GU', 'AS'):
                    country_hint = 'Micronesia' if r['state'] == 'FM' else \
                                  'Marshall Islands' if r['state'] == 'MH' else \
                                  'Palau' if r['state'] == 'PW' else 'US'
                elif r['state'] == 'PR':
                    country_hint = 'Puerto Rico'
                else:
                    country_hint = ''
                fut = ex.submit(geocode_nominatim, r['city'], r['state'], country_hint)
                fut_map[fut] = r['id']
            
            updates = []
            for fut in as_completed(fut_map):
                eid = fut_map[fut]
                other_done += 1
                lat, lon, source = fut.result()
                if lat and lon:
                    updates.append((lat, lon, source, eid))
                    total_geocoded += 1
                
                if other_done % 100 == 0:
                    print(f"    {progress_bar(other_done, len(other_rows))} geocoded: {total_geocoded}", flush=True)
                
                if len(updates) >= BATCH_COMMIT:
                    conn.executemany('UPDATE dir_entries SET latitude = ?, longitude = ?, geocode_source = ? WHERE id = ?', updates)
                    conn.commit()
                    updates.clear()
            
            if updates:
                conn.executemany('UPDATE dir_entries SET latitude = ?, longitude = ?, geocode_source = ? WHERE id = ?', updates)
                conn.commit()
                updates.clear()
    
    elapsed = time.time() - t0
    print(f"\n  Done in {elapsed:.1f}s")
    print(f"  Total geocoded: {total_geocoded}/{len(rows)} ({100*total_geocoded/max(1,len(rows)):.1f}%)")
    
    # Summary
    print(f"\n  Geocode source breakdown:")
    for r in conn.execute('SELECT geocode_source, COUNT(*) as cnt FROM dir_entries WHERE geocode_source IS NOT NULL AND geocode_source LIKE \"%census%\" OR geocode_source LIKE \"%nominatim%\" GROUP BY geocode_source ORDER BY cnt DESC').fetchall():
        print(f"    {r[0]}: {r[1]}")
    
    conn.close()

if __name__ == '__main__':
    main()

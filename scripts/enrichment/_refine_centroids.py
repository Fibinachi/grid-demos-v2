"""
Re-geocode city-only records from today's scrapes with church names.
These got city centroids in the first nameless Google run — fix them.
"""
import json, os, re, sys, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

try:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
        API_KEY = winreg.QueryValueEx(k, 'GOOGLE_GEOCODE_API_KEY')[0]
except:
    API_KEY = os.environ['GOOGLE_GEOCODE_API_KEY']

GEO_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
SOURCES = ['pb_directory_import','bma_directory','clc_directory','emc_scrape','smc_playwright']

def main():
    conn = connect()
    c = conn.cursor()
    ph = ','.join('?' * len(SOURCES))
    
    # Find city-only records WITH coordinates (got centroids, need fixing)
    c.execute(f"""
        SELECT id, name, address, city, state, latitude, longitude FROM churches
        WHERE source IN ({ph}) AND latitude IS NOT NULL
        AND (address IS NULL OR address = '' OR (
            address NOT GLOB '*[0-9]*' AND address NOT GLOB '*Road*' AND address NOT GLOB '*Rd*'
            AND address NOT GLOB '*Street*' AND address NOT GLOB '*St*'
            AND address NOT GLOB '*Avenue*' AND address NOT GLOB '*Ave*'
            AND address NOT GLOB '*Drive*' AND address NOT GLOB '*Dr*'
            AND address NOT GLOB '*Lane*' AND address NOT GLOB '*Ln*'
            AND address NOT GLOB '*Highway*' AND address NOT GLOB '*Hwy*'
            AND address NOT GLOB '*Route*' AND address NOT GLOB '*Rt*'
            AND address NOT GLOB '*County*' AND address NOT GLOB '*CR*'
            AND address NOT GLOB '*FM *' AND address NOT GLOB '*Blvd*'
            AND address NOT GLOB '*Circle*' AND address NOT GLOB '*Court*'
            AND address NOT GLOB '*Trail*' AND address NOT GLOB '*Pkwy*'
            AND address NOT GLOB '*Plaza*' AND address NOT GLOB '*Loop*'
        ))
    """, SOURCES)
    rows = c.fetchall()
    print(f"City-only records to re-geocode with names: {len(rows)}")
    print(f"{'─'*80}")

    if not rows:
        conn.close()
        return

    ok = skip = err = 0
    updates = []
    start = time.time()

    for i, (ch_id, name, addr, city, state, old_lat, old_lon) in enumerate(rows):
        # Build query with church name
        church_name = (name or '').strip()
        church_name = re.sub(r'^(The\s+|A\s+)', '', church_name)[:80]
        
        parts = [church_name] if church_name else []
        if addr and addr.strip() and addr.strip().lower() not in church_name.lower():
            parts.append(addr.strip())
        if city:
            parts.append(city.strip())
        if state:
            parts.append(state.strip())
        query = ', '.join(parts) + ', USA'
        
        try:
            params = urllib.parse.urlencode({'address': query, 'key': API_KEY})
            with urllib.request.urlopen(f'{GEO_URL}?{params}', timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            err += 1
            print(f"[{i+1:4d}/{len(rows)}] ✗ ERR: {query[:70]}")
            time.sleep(0.02)
            continue

        if data.get('status') == 'OK' and data.get('results'):
            loc = data['results'][0]['geometry']['location']
            new_lat, new_lon = loc['lat'], loc['lng']
            # Only update if different enough (>0.001° ~111m)
            dist = ((new_lat - old_lat)**2 + (new_lon - old_lon)**2)**0.5
            if dist > 0.001:
                updates.append((new_lat, new_lon, ch_id))
                ok += 1
                print(f"[{i+1:4d}/{len(rows)}] ✓ {new_lat:9.5f},{new_lon:9.5f} (was {old_lat:.5f},{old_lon:.5f}) ← {query[:55]}")
            else:
                skip += 1
                print(f"[{i+1:4d}/{len(rows)}] ≈ same spot: {query[:60]}")
        else:
            err += 1
            print(f"[{i+1:4d}/{len(rows)}] ✗ {data.get('status')}: {query[:60]}")

        if len(updates) >= 50:
            with Provenance(conn, "_refine_centroids.py", source="google_geocode_named",
                            action="refined", fields="latitude,longitude"):
                c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
                conn.commit()
            updates = []

        time.sleep(0.02)

    if updates:
        with Provenance(conn, "_refine_centroids.py", source="google_geocode_named",
                        action="refined", fields="latitude,longitude"):
            c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
            conn.commit()

    elapsed = time.time() - start
    print(f"{'─'*80}")
    print(f"Done in {elapsed:.0f}s | {ok} refined  {skip} same  {err} err")
    conn.close()

if __name__ == '__main__':
    main()

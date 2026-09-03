"""
Reverse geocode today's scrapes — turn coordinates into clean Google addresses.
Overwrites address/city/state/zip5 with standardized Google format.
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
DELAY = 0.02

def main():
    conn = connect()
    c = conn.cursor()
    ph = ','.join('?' * len(SOURCES))
    c.execute(f"SELECT id, name, latitude, longitude FROM churches WHERE source IN ({ph}) AND latitude IS NOT NULL", SOURCES)
    rows = c.fetchall()
    print(f"Reverse geocode: {len(rows):,} records | 50/sec | ~{len(rows)*0.02:.0f}s ETA")
    print(f"{'─'*80}")

    ok = err = 0
    updates = []
    start = time.time()

    for i, (ch_id, name, lat, lon) in enumerate(rows):
        params = urllib.parse.urlencode({'latlng': f'{lat},{lon}', 'key': API_KEY})
        url = f'{GEO_URL}?{params}'

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            err += 1
            time.sleep(DELAY)
            continue

        if data.get('status') == 'OK' and data.get('results'):
            comps = data['results'][0].get('address_components', [])
            # Extract fields
            street_num = ''
            route = ''
            city = ''
            state = ''
            zip5 = ''
            for comp in comps:
                types = comp.get('types', [])
                if 'street_number' in types:
                    street_num = comp['long_name']
                elif 'route' in types:
                    route = comp['long_name']
                elif 'locality' in types:
                    city = comp['long_name']
                elif 'administrative_area_level_1' in types:
                    state = comp['short_name']
                elif 'postal_code' in types:
                    zip5 = comp['long_name'][:5]

            street = f'{street_num} {route}'.strip() if street_num or route else ''
            formatted = data['results'][0].get('formatted_address', '')[:120]

            updates.append((street, city, state, zip5[:5], ch_id))
            ok += 1
            print(f"[{i+1:4d}/{len(rows)}] ✓ {formatted[:70]}")
        else:
            err += 1
            print(f"[{i+1:4d}/{len(rows)}] ✗ {data.get('status')}: {lat:.5f},{lon:.5f}")

        if len(updates) >= 100:
            with Provenance(conn, "_reverse_geocode.py", source="google_reverse",
                            action="enriched", fields="address,city,state,zip5"):
                c.executemany("UPDATE churches SET address=?, city=?, state=?, zip5=? WHERE id=?", updates)
                conn.commit()
            updates = []

        time.sleep(DELAY)

    if updates:
        with Provenance(conn, "_reverse_geocode.py", source="google_reverse",
                        action="enriched", fields="address,city,state,zip5"):
            c.executemany("UPDATE churches SET address=?, city=?, state=?, zip5=? WHERE id=?", updates)
            conn.commit()

    elapsed = time.time() - start
    print(f"{'─'*80}")
    print(f"Done in {elapsed:.0f}s | {ok} ok  {err} err")
    conn.close()

if __name__ == '__main__':
    main()

"""
Phase 3: Census single-address geocoder for remaining street addresses.
Faster + more reliable than Nominatim public server.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

SOURCES = [
    'pb_directory_import',
    'bma_directory',
    'clc_directory',
    'emc_scrape',
    'smc_playwright',
]

CENSUS_URL = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'
COMMIT_EVERY = 50
DELAY = 0.15  # Census allows ~500/min = 8/sec; 0.15s = 6.6/sec is safe


def build_query(addr, city, state):
    """Build clean address string."""
    if not addr:
        addr = ''
    addr = re.sub(r'[🟡🔴🟢🔵🟠🟣]\s*Fix\s*GPS', '', addr, flags=re.IGNORECASE)
    addr = addr.strip().strip(',').strip()
    
    # Don't duplicate city/state if already in address
    if city and city.lower() in addr.lower():
        city = ''
    if state and state.lower() in addr.lower():
        state = ''
    
    parts = []
    if addr:
        parts.append(addr)
    if city:
        parts.append(city.strip())
    if state:
        parts.append(state.strip())
    
    return ', '.join(parts) + ', USA' if parts else ''


def main():
    conn = connect()
    c = conn.cursor()

    placeholders = ','.join('?' * len(SOURCES))
    c.execute(f"""
        SELECT id, address, city, state FROM churches
        WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    rows = c.fetchall()
    
    print(f"Census single-address: {len(rows):,} remaining | ~{len(rows)*0.15:.0f}s ETA")
    print(f"{'─'*80}")

    if not rows:
        conn.close()
        return

    ok = miss = err = 0
    updates = []
    start = time.time()

    for i, (ch_id, addr, city, state) in enumerate(rows):
        query = build_query(addr, city, state)
        
        try:
            params = urllib.parse.urlencode({
                'address': query,
                'benchmark': 'Public_AR_Current',
                'format': 'json',
            })
            url = f'{CENSUS_URL}?{params}'
            req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            
            matches = data.get('result', {}).get('addressMatches', [])
            if matches:
                coords = matches[0].get('coordinates', {})
                lat = float(coords.get('y', 0))
                lon = float(coords.get('x', 0))
                if lat and lon:
                    updates.append((lat, lon, ch_id))
                    ok += 1
                    print(f"[{i+1:4d}/{len(rows)}] ✓ {lat:9.5f},{lon:9.5f}  ← {query[:60]}")
                else:
                    miss += 1
                    print(f"[{i+1:4d}/{len(rows)}] ✗ zero coords: {query[:60]}")
            else:
                miss += 1
                print(f"[{i+1:4d}/{len(rows)}] ✗ no match: {query[:60]}")
        except Exception as e:
            err += 1
            print(f"[{i+1:4d}/{len(rows)}] ✗ ERR: {query[:60]}")

        if len(updates) >= COMMIT_EVERY:
            with Provenance(conn, "_geocode_today_phase3.py", source="census_single",
                            action="enriched", fields="latitude,longitude"):
                c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
                conn.commit()
            updates = []

        time.sleep(DELAY)

    if updates:
        with Provenance(conn, "_geocode_today_phase3.py", source="census_single",
                        action="enriched", fields="latitude,longitude"):
            c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
            conn.commit()

    elapsed = time.time() - start
    print(f"{'─'*80}")
    print(f"Done in {elapsed:.0f}s | {ok} ok  {miss} miss  {err} err")

    c.execute(f"""
        SELECT COUNT(*) FROM churches WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    print(f"Still ungeocoded: {c.fetchone()[0]}")

    conn.close()


if __name__ == '__main__':
    main()

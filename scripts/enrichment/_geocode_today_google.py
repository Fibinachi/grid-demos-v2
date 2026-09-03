"""
Google Geocoding API — 929 remaining, 50/sec, done in ~20s.
Shows live input/output pairs.
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

def _get_key():
    """Get API key from env var or Windows registry (User scope)."""
    key = os.getenv('GOOGLE_GEOCODE_API_KEY')
    if key:
        return key
    # Try registry for persistent User variable
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
            return winreg.QueryValueEx(k, 'GOOGLE_GEOCODE_API_KEY')[0]
    except Exception:
        raise RuntimeError('GOOGLE_GEOCODE_API_KEY not found in env or registry')

API_KEY = _get_key()
GEO_URL = 'https://maps.googleapis.com/maps/api/geocode/json'

SOURCES = [
    'pb_directory_import', 'bma_directory', 'clc_directory',
    'emc_scrape', 'smc_playwright',
]
COMMIT_EVERY = 100
DELAY = 0.02  # 50 req/sec


def build_query(name, addr, city, state):
    """Build query — always includes church name for best match."""
    if not addr:
        addr = ''
    addr = re.sub(r'[🟡🔴🟢🔵🟠🟣]\s*Fix\s*GPS', '', addr, flags=re.IGNORECASE)
    addr = addr.strip().strip(',').strip()
    
    # Clean church name
    church_name = (name or '').strip()
    church_name = re.sub(r'^(The\s+|A\s+)', '', church_name)[:80]
    
    parts = [church_name] if church_name else []
    if addr and addr.lower() not in church_name.lower():
        parts.append(addr)
    if city:
        parts.append(city.strip())
    if state:
        parts.append(state.strip())
    
    return ', '.join(parts) + ', USA'


def main():
    conn = connect()
    c = conn.cursor()
    ph = ','.join('?' * len(SOURCES))
    c.execute(f"SELECT id, name, address, city, state FROM churches WHERE source IN ({ph}) AND (latitude IS NULL OR longitude IS NULL)", SOURCES)
    rows = c.fetchall()
    print(f"Google Geocode: {len(rows):,} remaining | 50/sec | ~{len(rows)*0.02:.0f}s ETA")
    print(f"{'─'*80}")

    if not rows:
        conn.close()
        return

    ok = miss = err = 0
    updates = []
    start = time.time()

    for i, (ch_id, name, addr, city, state) in enumerate(rows):
        query = build_query(name, addr, city, state)
        params = urllib.parse.urlencode({'address': query, 'key': API_KEY})
        url = f'{GEO_URL}?{params}'

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            err += 1
            print(f"[{i+1:4d}/{len(rows)}] ✗ ERR: {query[:60]}")
            time.sleep(DELAY)
            continue

        status = data.get('status', 'UNKNOWN')
        if status == 'OK' and data.get('results'):
            loc = data['results'][0]['geometry']['location']
            lat, lon = loc['lat'], loc['lng']
            updates.append((lat, lon, ch_id))
            ok += 1
            print(f"[{i+1:4d}/{len(rows)}] ✓ {lat:9.5f},{lon:9.5f}  ← {query[:60]}")
        elif status == 'ZERO_RESULTS':
            miss += 1
            print(f"[{i+1:4d}/{len(rows)}] ✗ no match: {query[:60]}")
        elif status == 'OVER_QUERY_LIMIT':
            print(f"[{i+1:4d}/{len(rows)}] ⚠ QUOTA — sleeping 10s...", flush=True)
            time.sleep(10)
            err += 1
        else:
            err += 1
            print(f"[{i+1:4d}/{len(rows)}] ✗ {status}: {query[:60]}")

        if len(updates) >= COMMIT_EVERY:
            with Provenance(conn, "_geocode_today_google.py", source="google_geocode",
                            action="enriched", fields="latitude,longitude"):
                c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
                conn.commit()
            updates = []

        time.sleep(DELAY)

    if updates:
        with Provenance(conn, "_geocode_today_google.py", source="google_geocode",
                        action="enriched", fields="latitude,longitude"):
            c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
            conn.commit()

    elapsed = time.time() - start
    print(f"{'─'*80}")
    print(f"Done in {elapsed:.0f}s | {ok} ok  {miss} miss  {err} err")
    c.execute(f"SELECT COUNT(*) FROM churches WHERE source IN ({ph}) AND latitude IS NULL", SOURCES)
    print(f"Still ungeocoded: {c.fetchone()[0]}")
    conn.close()


if __name__ == '__main__':
    main()

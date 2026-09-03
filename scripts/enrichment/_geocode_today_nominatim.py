"""
Nominatim fallback — shows every query + result live, one per line.
Resumes automatically (only geocodes records still missing coordinates).
"""
import os
import re
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

SOURCES = [
    'pb_directory_import',
    'bma_directory',
    'clc_directory',
    'emc_scrape',
    'smc_playwright',
]

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) GRID-Geocoder/1.0'}
DELAY = 2.5  # Extra conservative to avoid 429 bans
COMMIT_EVERY = 50


def clean_query(addr, city, state):
    if not addr:
        addr = ''
    addr = re.sub(r'[🟡🔴🟢🔵🟠🟣]\s*Fix\s*GPS', '', addr, flags=re.IGNORECASE)
    addr = addr.strip().strip(',').strip()

    parts = []
    if addr and addr.lower() not in (city.lower() if city else '', state.lower() if state else ''):
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

    print(f"Nominatim: {len(rows):,} remaining | ~{len(rows)}s ETA")
    print(f"{'─'*80}")

    if not rows:
        conn.close()
        return

    ok = miss = err = 0
    updates = []
    start = time.time()
    backoff = 1.0  # starts at 1s, grows on 429

    for i, (ch_id, addr, city, state) in enumerate(rows):
        query = clean_query(addr, city, state)

        # --- Request (with retry on 429) ---
        for attempt in range(3):
            try:
                r = requests.get(NOMINATIM_URL,
                               params={'q': query, 'format': 'json', 'limit': 1},
                               headers=HEADERS, timeout=10)
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                err += 1
                print(f"[{i+1:4d}/{len(rows)}] ✗ ERR: {query[:75]}")
                r = None
                break

            if r is None:
                break

            if r.status_code == 429:
                backoff = min(backoff * 2, 30)
                print(f"[{i+1:4d}/{len(rows)}] ⚠ 429 backoff {backoff:.0f}s", flush=True)
                time.sleep(backoff)
                continue

            if r.status_code == 200:
                data = r.json()
                if data:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    updates.append((lat, lon, ch_id))
                    ok += 1
                    backoff = max(backoff * 0.9, 1.0)  # decay backoff
                    print(f"[{i+1:4d}/{len(rows)}] ✓ {lat:9.5f},{lon:9.5f}  ← {query[:60]}")
                else:
                    miss += 1
                    print(f"[{i+1:4d}/{len(rows)}] ✗ no match: {query[:60]}")
            else:
                err += 1
                print(f"[{i+1:4d}/{len(rows)}] ✗ HTTP {r.status_code}: {query[:60]}")
            break  # success or non-429 error

        # Commit periodically
        if len(updates) >= COMMIT_EVERY:
            with Provenance(conn, "_geocode_today_nominatim.py", source="nominatim",
                            action="enriched", fields="latitude,longitude"):
                c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
                conn.commit()
            updates = []

        time.sleep(DELAY)

    # Final commit
    if updates:
        with Provenance(conn, "_geocode_today_nominatim.py", source="nominatim",
                        action="enriched", fields="latitude,longitude"):
            c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
            conn.commit()

    elapsed = time.time() - start
    print(f"{'─'*80}")
    print(f"Done in {elapsed/60:.1f}m | {ok} ok  {miss} miss  {err} err")

    c.execute(f"""
        SELECT COUNT(*) FROM churches WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    print(f"Still ungeocoded: {c.fetchone()[0]}")

    conn.close()


if __name__ == '__main__':
    main()

"""
Geocode remaining ungeocoded records from today's scrapes using Nominatim.
Census batch already handled 1,389; this tackles the 929 Census can't match
(rural routes, city-only, cross-streets, vague addresses).

Nominatim rate limit: 1 req/s. ETA: ~16 min for 929 records.
"""
import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GRID/1.0 (global religious infrastructure; contact@gridproject.org)"
DELAY = 1.05  # seconds between requests (Nominatim limit: 1/s)
COMMIT_EVERY = 200
TIMEOUT = 15

SOURCES = [
    'pb_directory_import',
    'bma_directory',
    'clc_directory',
    'emc_scrape',
    'smc_playwright',
]


def build_query(address, city, state):
    """Build a clean Nominatim query from available fields."""
    parts = []
    if address and address.strip():
        addr = address.strip().rstrip(',').strip()
        if addr and addr.lower() not in ('school', 'tbd', 'n/a', 'church'):
            parts.append(addr)
    if city and city.strip():
        parts.append(city.strip())
    if state and state.strip():
        parts.append(state.strip())
    parts.append("USA")
    return ", ".join(parts)


def main():
    conn = connect()
    c = conn.cursor()

    placeholders = ','.join('?' * len(SOURCES))

    # Get remaining ungeocoded
    c.execute(f"""
        SELECT id, address, city, state
        FROM churches
        WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    rows = c.fetchall()
    total = len(rows)

    if total == 0:
        print("Nothing to geocode!")
        conn.close()
        return

    print(f"Remaining to geocode: {total:,}")
    eta_min = total * DELAY / 60
    print(f"Estimated time: {eta_min:.0f} min (Nominatim 1 req/s)")

    geocoded = 0
    failed = 0
    updates = []

    t0 = time.time()

    for i, (ch_id, address, city, state) in enumerate(rows):
        query = build_query(address, city, state)

        try:
            r = requests.get(
                NOMINATIM_URL,
                params={'q': query, 'format': 'json', 'limit': 1},
                headers={'User-Agent': USER_AGENT},
                timeout=TIMEOUT,
            )

            if r.status_code == 200:
                data = r.json()
                if data:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        updates.append((lat, lon, ch_id))
                        geocoded += 1
                    else:
                        failed += 1
                else:
                    failed += 1
            elif r.status_code == 429:
                # Rate limited — back off
                print(f"\n  Rate limited! Backing off 30s...")
                time.sleep(30)
                failed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        # Progress
        if (i + 1) % 50 == 0 or i == total - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta_remaining = (total - i - 1) * DELAY / 60
            pct = 100 * (i + 1) / total
            print(f"\r  [{i+1:,}/{total:,} {pct:.0f}%] "
                  f"geocoded={geocoded:,} failed={failed:,} "
                  f"rate={rate:.1f}/s ETA={eta_remaining:.0f}m", end="", flush=True)

        # Commit periodically
        if len(updates) >= COMMIT_EVERY:
            with Provenance(conn, "geocode_today_nominatim.py", source="nominatim",
                            action="enriched", fields="latitude,longitude"):
                c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
                conn.commit()
            print(f"\n  [Committed {len(updates):,}]")
            updates = []

        time.sleep(DELAY)

    # Final commit
    if updates:
        with Provenance(conn, "geocode_today_nominatim.py", source="nominatim",
                        action="enriched", fields="latitude,longitude"):
            c.executemany("UPDATE churches SET latitude=?, longitude=? WHERE id=?", updates)
            conn.commit()
        print(f"\n  [Final commit: {len(updates):,}]")

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"RESULTS (Nominatim)")
    print(f"  Geocoded:  {geocoded:,}")
    print(f"  Failed:    {failed:,}")
    print(f"  Duration:  {elapsed/60:.1f} min")

    # Remaining
    c.execute(f"""
        SELECT COUNT(*) FROM churches
        WHERE source IN ({placeholders})
          AND (latitude IS NULL OR longitude IS NULL)
    """, SOURCES)
    remaining = c.fetchone()[0]
    print(f"  Remaining: {remaining:,} / {total:,}")

    conn.close()


if __name__ == '__main__':
    main()

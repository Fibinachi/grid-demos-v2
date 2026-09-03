"""
Geocode US churches using Census Bureau Geocoding API (sequential, reliable).
Uses requests library with 10s timeouts. Writes every 100 records.
Shows every input/output.

Usage:
  python scripts/enrichment/geocode_census.py              # all US missing GPS
  python scripts/enrichment/geocode_census.py --dry-run    # 5 samples only
"""
import sqlite3, sys, os, time
import requests
from tqdm import tqdm

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/address"
BENCHMARK = "Public_AR_Current"
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
WRITE_EVERY = 100
DRY_RUN = '--dry-run' in sys.argv


def safe(v):
    return (v or '').strip()


def main():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()

    sql = """
        SELECT id, name, address, city, state, zip FROM churches
        WHERE country='US' AND (latitude IS NULL OR latitude=0)
        AND address IS NOT NULL AND address != ''
        AND city IS NOT NULL AND city != ''
        AND state IS NOT NULL AND state != ''
        ORDER BY id
    """
    c.execute(sql)
    rows = c.fetchall()
    total = len(rows)
    print(f"US churches needing forward geocode: {total:,}")

    if DRY_RUN:
        rows = rows[:5]
        total = len(rows)
        print("DRY RUN - 5 samples only")

    if total == 0:
        print("Nothing to do!")
        db.close()
        return

    session = requests.Session()
    ok = nom = err = 0
    batch = []
    start = time.time()

    pbar = tqdm(total=total, desc="Census geocode", unit='rec')

    for row in rows:
        chid, name, addr, city, state, zip_code = row
        dis_in = f"{safe(addr)}, {safe(city)}, {safe(state)} {safe(zip_code)}"

        params = {
            'street': safe(addr),
            'city': safe(city),
            'state': safe(state),
            'benchmark': BENCHMARK,
            'format': 'json'
        }
        if safe(zip_code):
            params['zip'] = safe(zip_code)[:5]

        try:
            r = session.get(CENSUS_URL, params=params, timeout=10)
            if r.status_code != 200:
                err += 1
                tqdm.write(f"  ERR [{chid}] HTTP {r.status_code} | {dis_in[:70]}")
                pbar.update(1)
                continue

            data = r.json()
            matches = data.get('result', {}).get('addressMatches', [])

            if matches:
                m = matches[0]
                coords = m.get('coordinates', {})
                lat, lon = coords.get('y'), coords.get('x')
                matched = m.get('matchedAddress', '')
                if lat and lon:
                    batch.append((lat, lon, 'census', chid))
                    ok += 1
                    tqdm.write(f"  OK  [{chid}] '{safe(name)[:45]}'")
                    tqdm.write(f"       in='{dis_in[:80]}'")
                    tqdm.write(f"       -> {lat:.6f},{lon:.6f} | out='{matched[:60]}'")
                else:
                    nom += 1
            else:
                nom += 1
        except requests.Timeout:
            err += 1
            tqdm.write(f"  TIM [{chid}] timeout | {dis_in[:70]}")
        except Exception as e:
            err += 1
            tqdm.write(f"  ERR [{chid}] {str(e)[:60]} | {dis_in[:60]}")

        pbar.update(1)

        if len(batch) >= WRITE_EVERY:
            c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source=? WHERE id=?", batch)
            db.commit()
            tqdm.write(f"  --- committed {len(batch)} ---")
            batch = []

        if not DRY_RUN:
            time.sleep(0.08)

    pbar.close()

    if batch:
        c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source=? WHERE id=?", batch)
        db.commit()

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"COMPLETE: {total:,} in {elapsed:.0f}s ({total/elapsed:.1f} rec/s)")
    print(f"  Geocoded: {ok:,} | No match: {nom:,} | Errors: {err:,}")

    remaining = c.execute("""SELECT COUNT(*) FROM churches
        WHERE country='US' AND (latitude IS NULL OR latitude=0)
        AND address IS NOT NULL AND address != ''
        AND city IS NOT NULL AND city != ''
        AND state IS NOT NULL AND state != ''""").fetchone()[0]
    print(f"  Remaining: {remaining:,}")
    db.close()


if __name__ == '__main__':
    main()

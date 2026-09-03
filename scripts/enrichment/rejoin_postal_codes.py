#!/usr/bin/env python3
"""
Optimized postal code re-join using in-memory spatial grid.
Loads postal codes into memory per country, grid-matches churches in batches.
"""
import sqlite3, time
from collections import defaultdict

DB = 'e:/grid/churches.db'

def main():
    t0 = time.time()
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA cache_size=-128000")
    c = db.cursor()

    print("OPTIMIZED POSTAL RE-JOIN")
    print("=" * 60)

    c.execute("SELECT DISTINCT country_code, COUNT(*) FROM geonames_postal GROUP BY country_code HAVING COUNT(*) > 100 ORDER BY COUNT(*) DESC")
    postal_countries = {r[0]: r[1] for r in c.fetchall()}
    
    total_updated = 0
    for country, pc_count in postal_countries.items():
        c.execute("SELECT COUNT(*) FROM churches WHERE country=? AND (zip IS NULL OR zip='') AND latitude IS NOT NULL", (country,))
        needed = c.fetchone()[0]
        if needed == 0:
            continue

        print(f"  {country}: {needed:,} need zip...", end='', flush=True)
        t1 = time.time()

        # Load postal codes into spatial grid (0.05 degree cells = ~5km)
        c.execute("""SELECT CAST(latitude*20 AS INT) as gx, CAST(longitude*20 AS INT) as gy,
                     postal_code, latitude, longitude FROM geonames_postal
                     WHERE country_code=? AND latitude IS NOT NULL""", (country,))
        grid = defaultdict(list)
        for gx, gy, pc, lat, lon in c.fetchall():
            grid[(gx, gy)].append((pc, lat, lon))

        # Process churches
        c.execute("SELECT id, latitude, longitude FROM churches WHERE country=? AND (zip IS NULL OR zip='') AND latitude IS NOT NULL", (country,))
        churches = c.fetchall()

        updates = []
        for ch_id, ch_lat, ch_lon in churches:
            gx, gy = int(ch_lat * 20), int(ch_lon * 20)
            best_pc, best_d = None, 99.0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for pc, lat, lon in grid.get((gx + dx, gy + dy), []):
                        d = abs(lat - ch_lat) + abs(lon - ch_lon)
                        if d < best_d:
                            best_d, best_pc = d, pc
            if best_pc and best_d < 0.1:
                updates.append((best_pc, ch_id))

        if updates:
            c.executemany("UPDATE churches SET zip=? WHERE id=?", updates)
            db.commit()
            total_updated += len(updates)
            dt = time.time() - t1
            print(f" -> {len(updates):,} in {dt:.1f}s")
        else:
            print(f" -> 0")

    elapsed = time.time() - t0
    print(f"\nTotal: {total_updated:,} zips in {elapsed:.0f}s")
    db.close()

if __name__ == '__main__':
    main()

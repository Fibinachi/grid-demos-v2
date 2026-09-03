"""
Import GeoNames populated places & fill missing city/state for churches with GPS.
"""
import sqlite3, time

DB = 'E:/grid/churches.db'
GEONAMES = 'E:/grid/data/geonames/allCountries.txt'
BATCH = 20000

def main():
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=OFF')
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()

    c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='geonames'")
    if not c.fetchone()[0]:
        print("Creating geonames table (populated places only)...")
        c.execute("""
            CREATE TABLE geonames (
                geonameid INTEGER PRIMARY KEY,
                name TEXT,
                latitude REAL, longitude REAL,
                feature_class TEXT,
                country_code TEXT,
                admin1_code TEXT,
                population INTEGER
            )
        """)
        
        print("Importing...")
        count = 0
        batch = []
        start = time.time()
        with open(GEONAMES, 'r', encoding='utf-8') as f:
            for line in f:
                fields = line.strip().split('\t')
                if len(fields) >= 15 and fields[6] == 'P':
                    batch.append((
                        int(fields[0]), fields[1],
                        float(fields[4]), float(fields[5]),
                        fields[6], fields[8], fields[10],
                        int(fields[14]) if fields[14] else 0
                    ))
                    if len(batch) >= BATCH:
                        c.executemany("INSERT OR IGNORE INTO geonames VALUES (?,?,?,?,?,?,?,?)", batch)
                        batch = []
                        count += BATCH
                        if count % 100000 == 0:
                            print(f"  {count:,} rows...")
        
        if batch:
            c.executemany("INSERT OR IGNORE INTO geonames VALUES (?,?,?,?,?,?,?,?)", batch)
            count += len(batch)
        
        c.execute("CREATE INDEX idx_gn_latlon ON geonames(latitude, longitude)")
        c.execute("CREATE INDEX idx_gn_country ON geonames(country_code)")
        db.commit()
        print(f"  Imported {count:,} populated places in {time.time()-start:.0f}s")
    else:
        c.execute("SELECT COUNT(*) FROM geonames")
        print(f"GeoNames: {c.fetchone()[0]:,} populated places (already imported)")

    # Fill missing city
    c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND latitude IS NOT NULL AND (city IS NULL OR city = '')")
    missing = c.fetchone()[0]
    print(f"\nUS churches with GPS but no city: {missing:,}")

    if missing > 0:
        print("Matching against GeoNames...")
        c.execute("""
            UPDATE churches SET city = (
                SELECT g.name FROM geonames g
                WHERE g.feature_class = 'P' AND g.country_code = 'US'
                  AND ABS(g.latitude - latitude) < 0.3
                  AND ABS(g.longitude - longitude) < 0.3
                ORDER BY (g.latitude-latitude)*(g.latitude-latitude) 
                       + (g.longitude-longitude)*(g.longitude-longitude)
                LIMIT 1
            )
            WHERE country='US' AND latitude IS NOT NULL AND (city IS NULL OR city = '')
        """)
        db.commit()
        print(f"  Updated {c.rowcount:,} cities")

    # Fill missing state
    c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND latitude IS NOT NULL AND (state IS NULL OR state = '')")
    ms = c.fetchone()[0]
    print(f"US churches with GPS but no state: {ms:,}")

    if ms > 0:
        print("Filling states from GeoNames admin1...")
        c.execute("""
            UPDATE churches SET state = (
                SELECT g.admin1_code FROM geonames g
                WHERE g.feature_class = 'P' AND g.country_code = 'US'
                  AND ABS(g.latitude - latitude) < 0.3
                  AND ABS(g.longitude - longitude) < 0.3
                ORDER BY (g.latitude-latitude)*(g.latitude-latitude) 
                       + (g.longitude-longitude)*(g.longitude-longitude)
                LIMIT 1
            )
            WHERE country='US' AND latitude IS NOT NULL AND (state IS NULL OR state = '')
        """)
        db.commit()
        print(f"  Updated {c.rowcount:,} states")

    # Final stats
    c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND latitude IS NOT NULL")
    ug = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND latitude IS NOT NULL AND city IS NOT NULL AND city != ''")
    uc = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND latitude IS NOT NULL AND state IS NOT NULL AND state != ''")
    us = c.fetchone()[0]
    print(f"\nUS churches with GPS: {ug:,}")
    print(f"  With city:  {uc:,} ({100*uc/ug:.0f}%)")
    print(f"  With state: {us:,} ({100*us/ug:.0f}%)")
    db.close()

if __name__ == '__main__':
    main()

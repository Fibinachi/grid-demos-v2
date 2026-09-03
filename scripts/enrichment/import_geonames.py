"""
Import GeoNames allCountries.txt into churches.db for reverse geocode fallback.
Creates geonames_places table with spatial index for fast nearest-neighbor lookups.

GeoNames format (tab-separated):
  0: geonameid      1: name           2: asciiname      3: alternatenames
  4: latitude       5: longitude      6: feature class  7: feature code
  8: country code   9: cc2           10: admin1 code   11: admin2 code
 12: admin3 code   13: admin4 code   14: population    15: elevation
 16: dem           17: timezone      18: modification date

We keep: geonameid, name, latitude, longitude, country_code, admin1, feature_class,
         feature_code, population
"""
import sqlite3, zipfile, os, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, 'churches.db')
ZIP = os.path.join(ROOT, 'data', 'geonames_allCountries.zip')

print(f"DB: {DB}")
print(f"ZIP: {ZIP} ({os.path.getsize(ZIP)/1024/1024:.0f} MB)")

con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode=WAL")
con.execute("PRAGMA synchronous=OFF")
con.execute("PRAGMA cache_size=-2000000")  # 2GB cache
cur = con.cursor()

# Drop old if exists
cur.execute("DROP TABLE IF EXISTS geonames_places")
cur.execute("""
    CREATE TABLE geonames_places (
        geonameid INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        country_code TEXT NOT NULL,
        admin1 TEXT,
        feature_class TEXT,
        feature_code TEXT,
        population INTEGER DEFAULT 0
    )
""")

# Feature classes we want (populated places + admin divisions)
# P = city/town/village, A = admin division (state/province)
WANTED_CLASSES = {'P', 'A'}

with zipfile.ZipFile(ZIP) as zf:
    with zf.open('allCountries.txt') as f:
        batch = []
        total = 0
        kept = 0
        start = time.time()
        for line in f:
            total += 1
            line = line.decode('utf-8').strip()
            if not line:
                continue
            fields = line.split('\t')
            if len(fields) < 19:
                continue
            
            fclass = fields[6]
            if fclass not in WANTED_CLASSES:
                continue
            
            try:
                geonameid = int(fields[0])
                name = fields[1]
                lat = float(fields[4])
                lon = float(fields[5])
                cc = fields[8]
                admin1 = fields[10] if fields[10] else None
                fcode = fields[7] if fields[7] else None
                pop = int(fields[14]) if fields[14] else 0
            except (ValueError, IndexError):
                continue
            
            if not name or lat == 0:
                continue
            
            batch.append((geonameid, name, lat, lon, cc, admin1, fclass, fcode, pop))
            kept += 1
            
            if len(batch) >= 50000:
                cur.executemany(
                    "INSERT OR IGNORE INTO geonames_places VALUES (?,?,?,?,?,?,?,?,?)",
                    batch
                )
                con.commit()
                elapsed = time.time() - start
                rate = kept / elapsed
                print(f"  {kept:>10,} kept / {total:>10,} scanned  ({rate:,.0f} rec/s)")
                batch = []

        # Final flush
        if batch:
            cur.executemany(
                "INSERT OR IGNORE INTO geonames_places VALUES (?,?,?,?,?,?,?,?,?)",
                batch
            )
            con.commit()

elapsed = time.time() - start
print(f"\nImported {kept:,} places in {elapsed:.0f}s ({kept/elapsed:,.0f} rec/s)")

# Indexes for spatial queries
print("\nBuilding indexes...")
cur.execute("CREATE INDEX idx_geonames_country ON geonames_places(country_code)")
cur.execute("CREATE INDEX idx_geonames_fclass ON geonames_places(feature_class)")
cur.execute("CREATE INDEX idx_geonames_pop ON geonames_places(population)")
con.commit()

# Stats
cur.execute("SELECT COUNT(*) FROM geonames_places")
total_places = cur.fetchone()[0]
cur.execute("SELECT country_code, COUNT(*) FROM geonames_places GROUP BY country_code ORDER BY COUNT(*) DESC LIMIT 10")
print(f"\nTotal places: {total_places:,}")
print("Top 10 countries:")
for cc, cnt in cur.fetchall():
    print(f"  {cc}: {cnt:,}")

con.close()
print("\nDone.")

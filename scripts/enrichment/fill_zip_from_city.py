"""Fill missing ZIPs and coordinates from city/state lookup — no API needed."""
import sqlite3, time
from datetime import datetime
import pandas as pd

DB = "E:/grid/churches.db"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
t0 = time.time()

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

db = sqlite3.connect(DB)

# ── 1. Build city→ZIP/coord lookup from geocoded churches ──
log("Building city-state lookup from geocoded churches...")
lookup = pd.read_sql_query("""
    SELECT LOWER(city) as city_key, LOWER(state) as state_key,
           zip, latitude, longitude, COUNT(*) as n
    FROM churches 
    WHERE latitude IS NOT NULL AND latitude != 0
      AND city IS NOT NULL AND city != ''
      AND state IS NOT NULL AND state != ''
      AND zip IS NOT NULL AND zip != ''
    GROUP BY LOWER(city), LOWER(state)
    ORDER BY n DESC
""", db)
log(f"  {len(lookup):,} unique (city, state) pairs with coordinates")

# Keep the most common ZIP per city
lookup = lookup.drop_duplicates(subset=["city_key", "state_key"], keep="first")
log(f"  {len(lookup):,} after dedup")

# ── 2. Load ungeocoded rows ──
log("Loading ungeocoded rows...")
need = pd.read_sql_query("""
    SELECT id, address, city, state, zip
    FROM churches 
    WHERE (latitude IS NULL OR latitude = 0)
      AND city IS NOT NULL AND city != ''
      AND state IS NOT NULL AND state != ''
    ORDER BY id
""", db)
log(f"  {len(need):,} rows")

# ── 3. Match ──
need["city_key"] = need["city"].str.lower()
need["state_key"] = need["state"].str.lower()

merged = need.merge(lookup, on=["city_key", "state_key"], how="inner")
log(f"  {len(merged):,} matched to (city, state) lookup")

# Fill ALL matched rows with lat/lon from lookup (city centroid ≈ ZIP centroid)
merged = merged.dropna(subset=["latitude", "longitude"])
log(f"  {len(merged):,} rows get coords from city lookup")

# ── 4. Write back ──
if len(merged) > 0:
    changed = merged[["id", "zip_y", "latitude", "longitude"]].copy()
    changed.columns = ["id", "zip", "latitude", "longitude"]
    changed = changed.dropna(subset=["id"])
    changed["id"] = changed["id"].astype("Int64")
    changed = changed.dropna(subset=["id"])
    
    log(f"  Writing {len(changed):,} updates...")
    changed.to_sql("_city_zip_fix", db, if_exists="replace", index=False)
    db.execute("CREATE INDEX _czf_idx ON _city_zip_fix(id)")
    
    db.execute("""
        UPDATE churches SET 
            zip = COALESCE(t.zip, churches.zip),
            latitude = COALESCE(t.latitude, churches.latitude),
            longitude = COALESCE(t.longitude, churches.longitude),
            geocode_source = COALESCE(churches.geocode_source, 'zip_centroid'),
            tract_geocode_source = COALESCE(churches.tract_geocode_source, 'zip_centroid'),
            tract_geocode_date = COALESCE(churches.tract_geocode_date, ?)
        FROM _city_zip_fix AS t WHERE churches.id = t.id
    """, (TODAY,))
    db.execute("DROP TABLE _city_zip_fix")
    log(f"  Done")

# ── 5. Provenance ──
db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, 0, ?, 0, 0, 'completed', ?)
""", ("city_zip_lookup", "fill_zip_from_city.py", TODAY, TODAY, len(changed),
      "zip,latitude,longitude",
      f"Filled coordinates via city-state lookup. {len(merged):,} rows updated with ZIP centroid coords."))

db.commit()

# ── 6. Final stats ──
t = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
g = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NOT NULL AND latitude!=0").fetchone()[0]
n = db.execute("SELECT COUNT(1) FROM churches WHERE latitude IS NULL OR latitude=0").fetchone()[0]
db.close()

log(f"\nDONE: {t:,} total | {g:,} geocoded ({g*100/t:.0f}%) | {n:,} remain")

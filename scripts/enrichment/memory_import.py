"""Load churches + geocoding results into memory, merge, write back."""
import sqlite3, csv, time
import pandas as pd

DB = "E:/grid/churches.db"
CSV = "E:/grid/data/cu_geocoded_results.csv"

t0 = time.time()

# 1. Load churches into DataFrame
print("Loading churches from DB...", flush=True)
db = sqlite3.connect(DB)
df = pd.read_sql_query("SELECT id, latitude, longitude, tract_fips, geocode_source, tract_geocode_source, tract_geocode_date, geocode_attempts, geocode_last_attempt FROM churches", db)
db.close()
print(f"  {len(df):,} rows in {time.time()-t0:.1f}s, {df.memory_usage(deep=True).sum()/1e6:.0f}MB", flush=True)

# 2. Load geocoding results
print("Loading geocoding results...", flush=True)
matches = []
no_matches = []
with open(CSV, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        sid = int(row["id"])
        if row["status"] == "match" and row["latitude"] and row["longitude"]:
            matches.append({"id": sid, "latitude": float(row["latitude"]),
                          "longitude": float(row["longitude"]),
                          "tract_fips": row.get("tract_fips", ""),
                          "geocode_source": "census_batch",
                          "tract_geocode_source": "census_batch",
                          "tract_geocode_date": "2026-06-17"})
        elif row["status"] == "no_match":
            no_matches.append(sid)

geo_df = pd.DataFrame(matches).set_index("id")
print(f"  {len(matches):,} matches, {len(no_matches):,} no_matches ({time.time()-t0:.1f}s)", flush=True)

# 3. Update in memory
print("Updating in memory...", flush=True)
df = df.set_index("id")

# Update matched rows
for col in ["latitude", "longitude", "tract_fips", "geocode_source", "tract_geocode_source", "tract_geocode_date"]:
    df.loc[df.index.isin(geo_df.index), col] = geo_df[col]

# Mark no_match attempts
no_idx = [i for i in no_matches if i in df.index]
df.loc[no_idx, "geocode_attempts"] = df.loc[no_idx, "geocode_attempts"].fillna(0) + 1
df.loc[no_idx, "geocode_last_attempt"] = "2026-06-17"
print(f"  {len(geo_df):,} updated, {len(no_idx):,} marked ({time.time()-t0:.1f}s)", flush=True)

# 4. Write changed rows via temp table + single SQL UPDATE (avoids executemany)
print("Writing changed rows via temp table...", flush=True)
changed_ids = list(geo_df.index) + no_idx
changed_mask = df.index.isin(changed_ids)
changed = df[changed_mask][["latitude", "longitude", "tract_fips", "geocode_source",
    "tract_geocode_source", "tract_geocode_date", "geocode_attempts", "geocode_last_attempt"]].copy()
changed["id"] = changed.index
changed = changed.reset_index(drop=True)
print(f"  {len(changed):,} rows to update ({time.time()-t0:.1f}s)", flush=True)

db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")

changed.to_sql("_cu_geo_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX IF NOT EXISTS _cu_temp_idx ON _cu_geo_temp(id)")
print(f"  Temp table + index ready ({time.time()-t0:.1f}s)", flush=True)

# Fast UPDATE FROM (SQLite 3.33+)
db.execute("""
    UPDATE churches SET 
        latitude = COALESCE(t.latitude, churches.latitude),
        longitude = COALESCE(t.longitude, churches.longitude),
        tract_fips = COALESCE(t.tract_fips, churches.tract_fips),
        geocode_source = COALESCE(t.geocode_source, churches.geocode_source),
        tract_geocode_source = COALESCE(t.tract_geocode_source, churches.tract_geocode_source),
        tract_geocode_date = COALESCE(t.tract_geocode_date, churches.tract_geocode_date),
        geocode_attempts = COALESCE(t.geocode_attempts, churches.geocode_attempts),
        geocode_last_attempt = COALESCE(t.geocode_last_attempt, churches.geocode_last_attempt)
    FROM _cu_geo_temp AS t
    WHERE churches.id = t.id
""")
print(f"  UPDATE complete ({time.time()-t0:.1f}s)", flush=True)

db.execute("DROP TABLE _cu_geo_temp")
db.commit()
db.close()

# 5. Verify
db = sqlite3.connect(DB)
t = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
g = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND latitude IS NOT NULL AND latitude != 0").fetchone()[0]
n = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude = 0)").fetchone()[0]
db.close()

print(f"\nDONE in {time.time()-t0:.1f}s", flush=True)
print(f"Total: {t:,} | ChurchUnion geocoded: {g:,} | Need: {n:,}", flush=True)

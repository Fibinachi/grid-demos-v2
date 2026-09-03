"""Import geocoding results to DB. Run once, self-contained."""
import sqlite3, csv, time, sys

DB = "E:/grid/churches.db"
CSV_PATH = "E:/grid/data/cu_geocoded_results.csv"
LOG = "E:/grid/data/import_log.txt"

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    print(msg, flush=True)

log("Starting import...")

# Read CSV
matches = []
no_matches = []
with open(CSV_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        sid = int(row["id"])
        if row["status"] == "match" and row["latitude"] and row["longitude"]:
            matches.append((float(row["latitude"]), float(row["longitude"]),
                          row.get("tract_fips", ""), sid))
        elif row["status"] == "no_match":
            no_matches.append(sid)

log(f"Loaded {len(matches):,} matches, {len(no_matches):,} no_matches")

# Update in batches
BATCH = 1000
for label, data, sql in [
    ("match", matches,
     "UPDATE churches SET latitude=?, longitude=?, tract_fips=?, geocode_source='census_batch', tract_geocode_source='census_batch', tract_geocode_date='2026-06-17' WHERE id=?"),
    ("no_match", [(s,) for s in no_matches],
     "UPDATE churches SET geocode_attempts=COALESCE(geocode_attempts,0)+1, geocode_last_attempt='2026-06-17' WHERE id=?")
]:
    for i in range(0, len(data), BATCH):
        chunk = data[i:i+BATCH]
        db = sqlite3.connect(DB, timeout=60)
        db.execute("PRAGMA synchronous=OFF")
        db.execute("BEGIN")
        db.executemany(sql, chunk)
        db.execute("COMMIT")
        db.close()
        n = min(i+BATCH, len(data))
        log(f"  {label}: {n:,}/{len(data):,}")

# Verify
db = sqlite3.connect(DB)
t = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
g = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND latitude IS NOT NULL AND latitude != 0").fetchone()[0]
n = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude = 0)").fetchone()[0]
db.close()
log(f"DONE: {t:,} total | {g:,} geocoded | {n:,} remain")

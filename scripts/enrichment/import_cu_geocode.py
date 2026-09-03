"""Import geocoding results CSV back into churches.db."""
import csv, sqlite3
from datetime import datetime

DB = "E:/grid/churches.db"
CSV = "E:/grid/data/cu_geocoded_results.csv"

# Read all results first
print("Loading results CSV...", flush=True)
matches = []
no_matches = []
with open(CSV, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["status"] == "match" and row["latitude"] and row["longitude"]:
            matches.append(row)
        elif row["status"] == "no_match":
            no_matches.append(row["id"])
print(f"  {len(matches):,} matches, {len(no_matches):,} no_matches", flush=True)

# Update DB in batches
BATCH = 5000
now = datetime.utcnow()
tract_date = now.strftime("%Y-%m-%d")
now_iso = now.isoformat()

for start in range(0, len(matches), BATCH):
    chunk = matches[start:start+BATCH]
    db = sqlite3.connect(DB, timeout=60)
    for row in chunk:
        db.execute("""
            UPDATE churches SET latitude=?, longitude=?, tract_fips=?,
                geocode_source='census_batch', tract_geocode_source='census_batch',
                tract_geocode_date=?
            WHERE id=?
        """, (float(row["latitude"]), float(row["longitude"]),
              row.get("tract_fips", ""), tract_date, int(row["id"])))
    db.commit()
    db.close()
    print(f"  {start+len(chunk):,}/{len(matches):,} matched rows updated", flush=True)

# Mark no_matches
for start in range(0, len(no_matches), BATCH):
    chunk = no_matches[start:start+BATCH]
    db = sqlite3.connect(DB, timeout=60)
    for rid in chunk:
        db.execute("UPDATE churches SET geocode_attempts=COALESCE(geocode_attempts,0)+1, geocode_last_attempt=? WHERE id=?",
                  (now_iso, int(rid)))
    db.commit()
    db.close()
    print(f"  {start+len(chunk):,}/{len(no_matches):,} no_match rows marked", flush=True)

# Verify
db = sqlite3.connect(DB)
total = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper'").fetchone()[0]
geo = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND latitude IS NOT NULL AND latitude != 0").fetchone()[0]
need = db.execute("SELECT COUNT(1) FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude = 0)").fetchone()[0]
db.close()
print(f"\nChurchUnion: {total:,} total | {geo:,} geocoded ({geo/total*100:.0f}%) | {need:,} remain", flush=True)

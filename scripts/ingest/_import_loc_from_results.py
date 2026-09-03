"""Import LOC phone directory churches from results JSON into churches.db."""
import json, sys, time
from pathlib import Path
from collections import Counter

sys.path.insert(0, r"E:\grid")
from gw_db import connect

JSON_PATH = Path("E:/grid/data/loc_phone_dirs/results/loc_churches_matched_20260709_094416.json")
CHUNK = 500

print("Loading LOC results...")
with open(JSON_PATH, encoding="utf-8") as f:
    data = json.load(f)
print(f"  {len(data):,} records")

# Check keys
keys = list(data[0].keys())
print(f"  Keys: {keys}")

# Count already-matched
already_matched = sum(1 for r in data if r.get("grid_church_id"))
print(f"  Already matched to grid: {already_matched:,}")

# Count with GPS
has_gps = sum(1 for r in data if r.get("lat") and r.get("lon"))
print(f"  Have GPS: {has_gps:,}")

db = connect()

# Check existing LOC entries
existing = db.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%loc_phone%' OR source LIKE '%loc_directory%'").fetchone()[0]
print(f"  Existing LOC churches in DB: {existing:,}")

# Build import list — only unmatched records
to_import = [r for r in data if not r.get("grid_church_id")]
print(f"  To import (unmatched): {len(to_import):,}")

if not to_import:
    print("Nothing to import!")
    db.close()
    sys.exit(0)

# Get next id
max_id = db.execute("SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) FROM churches").fetchone()[0]
print(f"  Starting from id: {max_id+1:,}")

state_counts = Counter()
imported = 0
errors = 0

for i in range(0, len(to_import), CHUNK):
    batch = to_import[i:i+CHUNK]
    for r in batch:
        try:
            new_id = max_id + imported + 1
            
            city = (r.get("city") or "").strip()
            state = (r.get("state") or "").strip()
            name = (r.get("name") or "").strip()
            lat = r.get("lat")
            lon = r.get("lon")
            source_date = r.get("source_date", "")
            
            source = f"loc_phone_directory_{source_date}" if source_date else "loc_phone_directory"
            
            db.execute("""
                INSERT INTO churches (id, name, city, state, country, 
                    latitude, longitude, landmark_type, source)
                VALUES (?, ?, ?, ?, 'US', ?, ?, 'church', ?)
            """, (str(new_id), name, city, state, lat, lon, source))
            
            state_counts[state or "unknown"] += 1
            imported += 1
            
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR: {name[:40]} - {e}")
    
    db.commit()
    pct = (i + len(batch)) / len(to_import) * 100
    print(f"  {min(i+len(batch), len(to_import)):,}/{len(to_import):,} ({pct:.0f}%)", end="\r", flush=True)

print(f"\n\nDone: {imported:,} imported, {errors} errors")
print(f"\nTop states:")
for state, cnt in state_counts.most_common(10):
    print(f"  {state:20s} {cnt:>6,}")

db.close()

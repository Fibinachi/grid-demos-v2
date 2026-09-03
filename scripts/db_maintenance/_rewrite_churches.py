"""Rewrite churches table keeping only core columns — ONE pass instead of 50 DROP COLUMNs."""
import sqlite3, os, sys
from datetime import datetime, timezone

DB = r"E:\grid\churches.db"

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

conn = sqlite3.connect(DB, timeout=300)
conn.execute("PRAGMA busy_timeout = 300000")
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA synchronous = OFF")
conn.execute("PRAGMA cache_size = -2000000")
c = conn.cursor()

KEEP = {
    "id", "name", "name_original", "name_transliterated",
    "address", "city", "state", "zip", "zip5", "zip4",
    "county", "county_fips_5", "country",
    "latitude", "longitude",
    "continent", "region_un", "subregion",
    "landmark_type", "is_landmark", "confidence_score",
    "ntee_code",
    "taxonomy_id", "culture_id", "faith_id", "legacy_id", "tradition_id", "movement_id",
    "civilizational_family", "nearest_city_km", "last_updated",
    "faith", "denomination", "denomination_id", "tradition", "legacy",
    "normalized_name", "source", "fips",
}

all_cols = [r[1] for r in c.execute("PRAGMA table_info('churches')").fetchall()]
keep_cols = [c for c in all_cols if c in KEEP]
drop_cols = [c for c in all_cols if c not in KEEP]

log(f"Current: {len(all_cols)} cols, Keeping: {len(keep_cols)}, Dropping: {len(drop_cols)}")

# Drop views
log("Dropping views...")
for row in c.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall():
    c.execute(f'DROP VIEW IF EXISTS "{row[0]}"')

# Drop all indexes
log("Dropping indexes...")
for row in c.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='churches'").fetchall():
    try:
        c.execute(f'DROP INDEX IF EXISTS "{row[0]}"')
    except:
        pass

# Create new table
log("Creating churches_new...")
col_list = ', '.join(f'"{c}"' for c in keep_cols)
c.execute(f"CREATE TABLE churches_new AS SELECT {col_list} FROM churches")
new_count = c.execute("SELECT COUNT(*) FROM churches_new").fetchone()[0]
log(f"  {new_count:,} rows copied")

# Swap
log("Swapping...")
c.execute("DROP TABLE churches")
c.execute("ALTER TABLE churches_new RENAME TO churches")

# Recreate essential indexes
log("Recreating indexes...")
c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_churches_id ON churches(id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_churches_faith ON churches(faith_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_churches_country ON churches(country)")
c.execute("CREATE INDEX IF NOT EXISTS idx_churches_state ON churches(state)")
c.execute("CREATE INDEX IF NOT EXISTS idx_churches_culture ON churches(culture_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_churches_legacy ON churches(legacy_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_churches_tradition ON churches(tradition_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_churches_movement ON churches(movement_id)")

# Verify
log("Verifying...")
n = c.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
ncol = len(c.execute("PRAGMA table_info('churches')").fetchall())
log(f"  churches: {n:,} rows, {ncol} columns")
log(f"  Kept: {', '.join(sorted(keep_cols))}")

conn.commit()
log("Vacuuming...")
conn.execute("VACUUM")
log("Done!")
conn.close()

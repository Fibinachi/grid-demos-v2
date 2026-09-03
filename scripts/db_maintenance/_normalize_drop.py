"""Rebuild churches with only core columns (one pass, fast)."""
import sqlite3, time

db = sqlite3.connect('E:/grid/churches.db')

# Core columns to KEEP
keep = [
    'id', 'name', 'denomination', 'family', 'faith', 'faith_tradition', 'tradition',
    'subtradition', 'religion_type', 'normalized_name',
    'address', 'city', 'state', 'zip', 'zip5', 'zip4', 'ein', 'ntee_code',
    'latitude', 'longitude', 'geocode_source', 'fips', 'country', 'source',
    'denomination_affiliation', 'address_source',
    'holy_site_id', 'landmark_type', 'is_landmark', 'heritage_status',
    'height_m', 'width_m', 'length_m', 'area_m2', 'capacity',
    'building_year',
    'source_primary', 'source_secondary',
    'osm_id', 'osm_type', 'osm_version', 'osm_timestamp',
    'wikidata_qid', 'wikidata_last_modified', 'overture_id',
    'confidence_score',
    'cra_bn', 'cra_category', 'cra_sub_category', 'cra_designation',
]

existing = {r[1] for r in db.execute("PRAGMA table_info(churches)")}
missing = [c for c in keep if c not in existing]
if missing:
    print(f"ERROR - Missing columns: {missing}")
    db.close()
    exit(1)

print(f"Keep: {len(keep)} columns, dropping {len(existing) - len(keep)}")

# Save indexes to recreate
indexes = db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='churches' AND sql IS NOT NULL").fetchall()

# Rebuild
t0 = time.time()
db.execute("DROP TABLE IF EXISTS churches_new")
cols = ', '.join(keep)
db.execute(f"CREATE TABLE churches_new AS SELECT {cols} FROM churches")
print(f"Built new table in {time.time()-t0:.1f}s")

t0 = time.time()
db.execute("DROP TABLE churches")
db.execute("ALTER TABLE churches_new RENAME TO churches")
print(f"Swapped in {time.time()-t0:.1f}s")

# Recreate indexes
for (sql,) in indexes:
    try:
        db.execute(sql)
    except:
        pass

cnt = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
cols = len([r for r in db.execute("PRAGMA table_info(churches)")])
print(f"Verified: {cnt:,} rows, {cols} columns")

db.commit()
db.close()
print("Done.")

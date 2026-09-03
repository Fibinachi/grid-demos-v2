"""
Assess null GPS records — scope and fixability
"""
import sqlite3

db = sqlite3.connect('E:/grid/churches.db')

total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
both_null = db.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL AND longitude IS NULL").fetchone()[0]
one_null = db.execute("SELECT COUNT(*) FROM churches WHERE (latitude IS NULL AND longitude IS NOT NULL) OR (latitude IS NOT NULL AND longitude IS NULL)").fetchone()[0]

print(f"Total records: {total:,}")
print(f"Both null: {both_null:,} ({both_null/total*100:.1f}%)")
print(f"One null:  {one_null:,} ({one_null/total*100:.1f}%)")
print()

# By source (both null)
rows = db.execute("SELECT COALESCE(source,'?'), COUNT(*) FROM churches WHERE latitude IS NULL AND longitude IS NULL GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
print("By source (both null):")
for s, n in rows:
    print(f"  {s}: {n:,}")
print()

# By country (top 20)
rows = db.execute("SELECT COALESCE(country,'?'), COUNT(*) FROM churches WHERE latitude IS NULL AND longitude IS NULL GROUP BY country ORDER BY COUNT(*) DESC LIMIT 20").fetchall()
print("By country (top 20, both null):")
for c, n in rows:
    print(f"  {c}: {n:,}")
print()

# By faith
rows = db.execute("SELECT COALESCE(faith,'?'), COUNT(*) FROM churches WHERE latitude IS NULL AND longitude IS NULL GROUP BY faith ORDER BY COUNT(*) DESC").fetchall()
print("By faith (both null):")
for f, n in rows:
    print(f"  {f}: {n:,}")
print()

# Check church_addresses — how many null-GPS records have address data?
with_addr = db.execute("""
    SELECT COUNT(DISTINCT c.rowid) FROM churches c
    JOIN church_addresses ca ON ca.church_rowid = c.rowid
    WHERE c.latitude IS NULL AND c.longitude IS NULL
""").fetchone()[0]
print(f"Null-GPS records WITH addresses in church_addresses: {with_addr:,}")

# Check address_components (via church_addresses join)
with_addr_comp = db.execute("""
    SELECT COUNT(DISTINCT c.rowid) FROM churches c
    JOIN church_addresses ca ON ca.church_rowid = c.rowid
    JOIN address_components ac ON ac.address_id = ca.address_id
    WHERE c.latitude IS NULL AND c.longitude IS NULL
""").fetchone()[0]
print(f"Null-GPS records WITH address_components: {with_addr_comp:,}")

# How many null-GPS churches have lat/lon in church_addresses but not churches?
with_addr_gps = db.execute("""
    SELECT COUNT(DISTINCT c.rowid) FROM churches c
    JOIN church_addresses ca ON ca.church_rowid = c.rowid
    WHERE c.latitude IS NULL AND c.longitude IS NULL
    AND ca.latitude IS NOT NULL AND ca.longitude IS NOT NULL
""").fetchone()[0]
print(f"Null-GPS records WITH lat/lon IN church_addresses: {with_addr_gps:,}")

# Address component types available
print("\nAddress component types for null-GPS records (any):")
for t, n in db.execute("""
    SELECT ac.component_type, COUNT(DISTINCT c.rowid)
    FROM churches c
    JOIN church_addresses ca ON ca.church_rowid = c.rowid
    JOIN address_components ac ON ac.address_id = ca.address_id
    WHERE c.latitude IS NULL AND c.longitude IS NULL
    GROUP BY ac.component_type ORDER BY COUNT(*) DESC
""").fetchall():
    print(f"  {t}: {n:,}")

# Check church_contacts
with_contact = db.execute("""
    SELECT COUNT(DISTINCT c.rowid) FROM churches c
    JOIN church_contacts cc ON cc.church_id = c.rowid
    WHERE c.latitude IS NULL AND c.longitude IS NULL
""").fetchone()[0]
print(f"Null-GPS records WITH church_contacts: {with_contact:,}")

# Check church_enrichment
with_enrich = db.execute("""
    SELECT COUNT(DISTINCT c.rowid) FROM churches c
    JOIN church_enrichment ce ON ce.church_id = c.rowid
    WHERE c.latitude IS NULL AND c.longitude IS NULL
""").fetchone()[0]
print(f"Null-GPS records WITH church_enrichment: {with_enrich:,}")
print()

# ————— One-null records —————
print("=== ONE NULL COORDINATE ===")
lon_null = db.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NULL").fetchone()[0]
lat_null = db.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL AND longitude IS NOT NULL").fetchone()[0]
print(f"Null longitude only: {lon_null:,}")
print(f"Null latitude only:  {lat_null:,}")

if lon_null > 0:
    rows = db.execute("SELECT COALESCE(source,'?'), COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NULL GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
    print("\nNull longitude by source:")
    for s, n in rows:
        print(f"  {s}: {n:,}")
if lat_null > 0:
    rows = db.execute("SELECT COALESCE(source,'?'), COUNT(*) FROM churches WHERE latitude IS NULL AND longitude IS NOT NULL GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
    print("\nNull latitude by source:")
    for s, n in rows:
        print(f"  {s}: {n:,}")

# Sample null-GPS records with names + city/state
print("\n--- 10 sample null-GPS records with address data ---")
for r in db.execute("""
    SELECT c.name, c.source, c.country,
           MAX(CASE WHEN ac.component_type='city' THEN ac.component_value END),
           MAX(CASE WHEN ac.component_type='state' THEN ac.component_value END),
           MAX(CASE WHEN ac.component_type='postcode' THEN ac.component_value END)
    FROM churches c
    JOIN church_addresses ca ON ca.church_rowid = c.rowid
    JOIN address_components ac ON ac.address_id = ca.address_id
    WHERE c.latitude IS NULL AND c.longitude IS NULL
    AND c.name IS NOT NULL
    GROUP BY c.rowid
    LIMIT 10
""").fetchall():
    print(f"  {r[0] or '?':.50s} | {r[1]:.20s} | {r[2]} | {r[3] or '?'}, {r[4] or '?'} {r[5] or '?'}")

db.close()

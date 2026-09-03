"""
Create diocese nodes for countries with Catholic churches but no diocese in hierarchy.
Diocese lines rarely cross borders — create one archdiocese per uncovered country.
"""
import sqlite3

DB = "E:/grid/churches.db"
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Find countries with Catholic churches but NO diocese/archdiocese in hierarchy
print("Finding uncovered countries...")
uncovered = db.execute("""
    SELECT c.country, COUNT(DISTINCT c.id) as churches
    FROM churches c
    WHERE c.taxonomy_id IN (14,86,92,100)
      AND c.country IS NOT NULL AND c.country != ''
      AND c.country NOT IN (
          SELECT DISTINCT country FROM catholic_hierarchy 
          WHERE cath_type IN ('diocese','archdiocese') AND country IS NOT NULL
      )
    GROUP BY c.country
    ORDER BY churches DESC
""").fetchall()

print(f"Countries without diocese nodes: {len(uncovered)}")
print(f"Total churches affected: {sum(r['churches'] for r in uncovered):,}")

for r in uncovered[:20]:
    print(f"  {r['country']}: {r['churches']:,}")

# Also get countries that DO have diocese nodes (to know what we have)
covered = db.execute("""
    SELECT DISTINCT country FROM catholic_hierarchy 
    WHERE cath_type IN ('diocese','archdiocese') AND country IS NOT NULL
""").fetchall()
covered_countries = {r["country"] for r in covered}
print(f"\nCountries WITH diocese nodes: {len(covered_countries)}")

# ── Create archdiocese nodes for uncovered countries ──
# Use a virtual "Holy See" parent (id=1) since these are exempt/national dioceses
holy_see_id = db.execute("SELECT id FROM catholic_hierarchy WHERE cath_type='holy_see' LIMIT 1").fetchone()
parent_id = holy_see_id["id"] if holy_see_id else None
print(f"Holy See parent id: {parent_id}")

inserts = []
for r in uncovered:
    country = r["country"]
    name = f"Archdiocese of {country}"
    inserts.append((
        parent_id,
        name, name,
        "archdiocese",
        name, name,  # diocese, archdiocese
        country,
        None, None, None, None,  # city, state, lat, lon
        "holy_see", "administered_by",
        f"Auto-created: {r['churches']:,} Catholic churches in {country} with no diocese"
    ))

print(f"\nCreating {len(inserts)} archdiocese nodes...")
for i in range(0, len(inserts), CHUNK_SIZE):
    batch = inserts[i:i+CHUNK_SIZE]
    db.executemany("""
        INSERT INTO catholic_hierarchy 
        (parent_id, name, original_name, cath_type, diocese, archdiocese,
         country, city, state, lat, lon, parent_cath_type, relationship, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()

print(f"Created {len(inserts)} archdiocese nodes")

# Verify
new_covered = db.execute("""
    SELECT COUNT(DISTINCT country) FROM catholic_hierarchy 
    WHERE cath_type IN ('diocese','archdiocese') AND country IS NOT NULL
""").fetchone()[0]
print(f"Countries with diocese nodes now: {new_covered} (was {len(covered_countries)})")

db.close()

"""
Geographic diocese assignment: county→diocese propagation for US Catholic entries.
Uses church_enrichment.diocese. Logs provenance.
"""
import sqlite3, time
from datetime import datetime, timezone
from collections import defaultdict

DB = 'churches.db'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# Catholic filter: tradition/faith/denomination contains 'cath'
CATH = "(LOWER(COALESCE(c.tradition,'')) LIKE '%cath%' OR LOWER(COALESCE(c.faith,'')) LIKE '%cath%' OR LOWER(COALESCE(c.denomination,'')) LIKE '%cath%')"

# Create enrichment rows for Catholic entries missing them
c.execute(f"""
INSERT OR IGNORE INTO church_enrichment (church_id)
SELECT c.rowid FROM churches c
WHERE c.country='US' AND {CATH}
  AND c.rowid NOT IN (SELECT church_id FROM church_enrichment)
""")
db.commit()
new_rows = c.rowcount
print(f"Created {new_rows:,} enrichment rows for US Catholic entries")

# Count current state
c.execute(f"SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND {CATH} AND ce.diocese IS NOT NULL AND ce.diocese!=''")
with_diocese = c.fetchone()[0]
c.execute(f"SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND {CATH} AND (ce.diocese IS NULL OR ce.diocese='')")
without_diocese = c.fetchone()[0]
total_catholic = with_diocese + without_diocese
print(f"US Catholic entries: {total_catholic:,} total, {with_diocese:,} with diocese, {without_diocese:,} without")

# Build county→diocese map from existing assignments
c.execute(f"""
SELECT DISTINCT ce.county_fips, ce.diocese
FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id
WHERE c.country='US' AND {CATH}
  AND ce.diocese IS NOT NULL AND ce.diocese!=''
  AND ce.county_fips IS NOT NULL AND ce.county_fips!=''
""")
county_map = {}
for fips, diocese in c.fetchall():
    if fips not in county_map:
        county_map[fips] = diocese
print(f"County→Diocese map: {len(county_map)} counties")

# Assign diocese by county_fips
updated = 0
for fips, diocese in county_map.items():
    c.execute(f"""
        UPDATE church_enrichment SET diocese=?
        WHERE church_id IN (
            SELECT c.rowid FROM churches c
            JOIN church_enrichment ce ON c.rowid=ce.church_id
            WHERE c.country='US' AND {CATH}
              AND (ce.diocese IS NULL OR ce.diocese='')
              AND ce.county_fips=?
        ) AND (diocese IS NULL OR diocese='')
    """, (diocese, fips))
    updated += c.rowcount
db.commit()
print(f"County assignment: {updated:,} updated")

# Build city+state→diocese map
c.execute(f"""
SELECT DISTINCT LOWER(COALESCE(c.city,'')), COALESCE(c.state,''), ce.diocese
FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id
WHERE c.country='US' AND {CATH}
  AND ce.diocese IS NOT NULL AND ce.diocese!=''
  AND c.city IS NOT NULL AND c.city!=''
""")
city_map = {}
for city, state, diocese in c.fetchall():
    key = (city, state)
    if key not in city_map:
        city_map[key] = diocese
print(f"City→Diocese map: {len(city_map)} cities")

# Assign by city+state
city_updated = 0
for (city, state), diocese in city_map.items():
    c.execute(f"""
        UPDATE church_enrichment SET diocese=?
        WHERE church_id IN (
            SELECT c.rowid FROM churches c
            WHERE c.country='US' AND {CATH}
              AND LOWER(COALESCE(c.city,''))=?
              AND COALESCE(c.state,'')=?
        ) AND (diocese IS NULL OR diocese='')
    """, (diocese, city, state))
    city_updated += c.rowcount
db.commit()
print(f"City assignment: {city_updated:,} updated")

# Final stats
c.execute(f"SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND {CATH} AND ce.diocese IS NOT NULL AND ce.diocese!=''")
final_with = c.fetchone()[0]
print(f"\nFinal: {final_with:,}/{total_catholic:,} US Catholic entries have diocese ({final_with/total_catholic*100:.0f}%)")

# Top dioceses
c.execute(f"""
SELECT ce.diocese, COUNT(*) as cnt FROM churches c
JOIN church_enrichment ce ON c.rowid=ce.church_id
WHERE c.country='US' AND {CATH} AND ce.diocese IS NOT NULL
GROUP BY ce.diocese ORDER BY cnt DESC LIMIT 10
""")
print("\nTop dioceses:")
for r in c.fetchall():
    print(f'  {r[0]:40s}: {r[1]:>6d}')

# Provenance
c.execute("INSERT INTO provenance_log (source,script_name,started_at,completed_at,churches_updated,fields_populated,status,notes) VALUES (?,?,?,?,?,?,?,?)",
    ('county_diocese_assignment','assign_diocese_by_county.py',NOW,
     datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
     updated+city_updated,'diocese','completed',
     f'Geographic diocese assignment: county→diocese propagation for US Catholic. {final_with:,} now have diocese.'))
db.commit()
db.close()
print("\nProvenance logged. Done!")

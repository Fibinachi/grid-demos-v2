"""
Create county_diocese_map lookup table — the single source of truth.
church_enrichment.diocese auto-derives from county_fips via this table.
Add/update rows in county_diocese_map to expand coverage.
"""
import sqlite3
from datetime import datetime, timezone

DB = 'churches.db'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
CATH = "(LOWER(COALESCE(c.faith_tradition,'')) LIKE '%cath%' OR LOWER(COALESCE(c.faith,'')) LIKE '%cath%' OR LOWER(COALESCE(c.denomination,'')) LIKE '%cath%')"

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# 1. Create lookup table
c.execute("""
CREATE TABLE IF NOT EXISTS county_diocese_map (
    county_fips TEXT PRIMARY KEY,
    diocese TEXT NOT NULL,
    source TEXT DEFAULT 'derived',
    confidence INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
)
""")
db.commit()
print("Created county_diocese_map table")

# 2. Populate from existing church_enrichment diocese assignments
c.execute(f"""
INSERT OR IGNORE INTO county_diocese_map (county_fips, diocese, source, confidence)
SELECT DISTINCT ce.county_fips, ce.diocese, 'existing_enrichment', 2
FROM churches c
JOIN church_enrichment ce ON c.rowid = ce.church_id
WHERE c.country = 'US' AND {CATH}
  AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND ce.county_fips IS NOT NULL AND ce.county_fips != ''
""")
db.commit()
seeded = c.rowcount
print(f"Seeded {seeded} county→diocese mappings from existing data")

c.execute("SELECT COUNT(*) FROM county_diocese_map")
total = c.fetchone()[0]
print(f"Total county→diocese mappings: {total}")

# 3. Auto-populate ALL church_enrichment rows from the map
c.execute("""
UPDATE church_enrichment SET diocese = (
    SELECT cdm.diocese FROM county_diocese_map cdm
    WHERE cdm.county_fips = church_enrichment.county_fips
)
WHERE county_fips IN (SELECT county_fips FROM county_diocese_map)
  AND (diocese IS NULL OR diocese = '' 
       OR diocese != (SELECT cdm.diocese FROM county_diocese_map cdm WHERE cdm.county_fips = church_enrichment.county_fips))
""")
db.commit()
synced = c.rowcount
print(f"Synced {synced} rows from county_diocese_map")

# 4. Final stats
c.execute(f"""
SELECT COUNT(*) FROM churches c
JOIN church_enrichment ce ON c.rowid = ce.church_id
WHERE c.country = 'US' AND {CATH} AND ce.diocese IS NOT NULL AND ce.diocese != ''
""")
with_diocese = c.fetchone()[0]
c.execute(f"SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND {CATH}")
total_cath = c.fetchone()[0]
print(f"\nUS Catholic with diocese: {with_diocese:,}/{total_cath:,} ({with_diocese/total_cath*100:.0f}%)")
print(f"Still need: {total_cath - with_diocese:,}")

# Top dioceses
c.execute("SELECT diocese, COUNT(*) FROM county_diocese_map GROUP BY diocese ORDER BY COUNT(*) DESC LIMIT 5")
print("\nLargest diocese maps:")
for r in c.fetchall(): print(f'  {r[0]:45s}: {r[1]} counties')

# Provenance
c.execute("INSERT INTO provenance_log (source,script_name,started_at,completed_at,churches_updated,fields_populated,status,notes) VALUES (?,?,?,?,?,?,?,?)",
    ('county_diocese_map','create_county_diocese_map.py',NOW,NOW,total,'county_diocese_map','completed',
     f'Created county_diocese_map lookup. {total} county→diocese mappings. church_enrichment.diocese auto-derived.'))
db.commit()
db.close()
print("Provenance logged.")

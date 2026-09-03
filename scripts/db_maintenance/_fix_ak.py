"""Fix AK: create enrichment rows + assign by latitude."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Create missing enrichment rows for AK Catholic churches
c.execute("""INSERT OR IGNORE INTO church_enrichment (church_id)
  SELECT id FROM churches 
  WHERE country='US' AND state='AK' 
  AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')""")
print(f"Enrichment rows created: {c.rowcount}")

# Assign by latitude: Fairbanks (>=63N), Anchorage-Juneau (<63N)
c.execute("""UPDATE church_enrichment SET diocese = 
  CASE WHEN ch.latitude >= 63.0 THEN 'Fairbanks' ELSE 'Anchorage-Juneau' END
  FROM churches ch
  WHERE church_enrichment.church_id = ch.id
    AND ch.state='AK' AND ch.country='US'
    AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
    AND (church_enrichment.diocese IS NULL OR church_enrichment.diocese = '')
    AND ch.latitude IS NOT NULL""")
print(f"AK assigned: {c.rowcount}")
conn.commit()

# Verify
c.execute("""SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id
  WHERE ch.state='AK' AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
print(f"AK with diocese: {c.fetchone()[0]} / 76")

conn.close()

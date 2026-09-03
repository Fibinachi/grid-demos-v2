"""Fix remaining edge cases: churches with US diocese but blank/wrong state."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Show the 10 Fairbanks with blank state
c.execute("""SELECT ch.id, ch.name, ch.state, ch.country, ch.latitude, ch.longitude, ce.diocese
  FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id
  WHERE ce.diocese='Fairbanks' AND (ch.state IS NULL OR ch.state='' OR ch.state!='AK')""")
print("Fairbanks diocese but not state=AK:")
for r in c.fetchall():
    print(f'  id={r[0]} name={str(r[1] or "")[:50]} state={r[2]} country={r[3]} lat={r[4]} lon={r[5]}')

# Fix: NULL diocese where state is blank/empty for US-only dioceses
c.execute("""UPDATE church_enrichment SET diocese=NULL, diocese_detail=NULL, province=NULL, province_detail=NULL
  WHERE diocese IN ('Fairbanks','Anchorage-Juneau','Boise','Seattle','Spokane','Yakima','Baker','Portland in Oregon')
  AND church_id IN (SELECT id FROM churches WHERE state IS NULL OR state='')""")
print(f'Fixed {c.rowcount} entries with blank state')

conn.commit()

# Re-verify
c.execute("SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id WHERE ce.diocese='Fairbanks' AND (ch.state IS NULL OR ch.state='' OR ch.state!='AK')")
print(f'\nFairbanks NOT in AK remaining: {c.fetchone()[0]}')

c.execute("SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese!='' AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')")
print(f'US Catholic with diocese: {c.fetchone()[0]:,}')

conn.close()

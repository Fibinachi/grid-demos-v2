"""
Clean up ungeocoded Catholic entries: delete junk, tag unverifiable, assign diocese.
"""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

single_diocese = {
    'DC': 'Washington', 'DE': 'Wilmington', 'HI': 'Honolulu',
    'ID': 'Boise', 'ME': 'Portland in Maine', 'MS': 'Jackson',
    'MT': 'Great Falls-Billings', 'NC': 'Raleigh', 'ND': 'Bismark',
    'NH': 'Manchester', 'NV': 'Las Vegas', 'RI': 'Providence',
    'SC': 'Charleston', 'SD': 'Sioux Falls', 'TN': 'Nashville',
    'UT': 'Salt Lake City', 'VA': 'Richmond', 'VT': 'Burlington',
    'WV': 'Wheeling-Charleston', 'WY': 'Cheyenne', 'AR': 'Little Rock',
}

# 1. Delete clear junk
print("=== Deleting clear junk ===")
c.execute("""SELECT id FROM churches
  WHERE country='US' 
  AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
  AND (latitude IS NULL OR longitude IS NULL)
  AND (
    LOWER(name) LIKE '%act of hope%' OR LOWER(name) LIKE '%prayer o lord%'
    OR LOWER(name) LIKE '%for strength in%' OR LOWER(name) LIKE '%you are christ%'
    OR LOWER(name) LIKE '%holy spirit prayer%' OR LOWER(name) LIKE '%unveils%economic%'
    OR LOWER(name) LIKE '%economic impact%' OR LOWER(name) LIKE '%billion%'
    OR LOWER(name) LIKE '%merge to form%' OR LOWER(name) LIKE '%new report unveils%'
    OR LOWER(name) LIKE '%from pigs eye%' OR LOWER(name) LIKE '%ministry leaders to examine%'
    OR LOWER(name) LIKE '%amid national unrest%' OR LOWER(name) LIKE '%as st. francis said%'
    OR LOWER(name) LIKE '%st. patricks day dispensation%'
    OR LOWER(name) LIKE '%commencement%' OR LOWER(name) LIKE '%to close%campus%'
    OR LOWER(name) LIKE '%president dies%' OR LOWER(name) LIKE '%awards degrees%'
    OR LOWER(name) LIKE '%ranks no%' OR LOWER(name) LIKE '%best for vets%'
    OR LOWER(name) LIKE '%free english workshops%'
    OR (LOWER(name) LIKE '%university%' AND source != 'wikipedia_catholic_uni')
  )""")
junk_ids = [r[0] for r in c.fetchall()]
print(f"  Found {len(junk_ids):,} junk entries")

for chunk in [junk_ids[i:i+500] for i in range(0, len(junk_ids), 500)]:
    ph = ','.join(['?']*len(chunk))
    c.execute(f"DELETE FROM church_enrichment WHERE church_id IN ({ph})", chunk)
    c.execute(f"DELETE FROM churches WHERE id IN ({ph})", chunk)
conn.commit()
print(f"  Deleted")

# 2. Tag unverifiable
print("\n=== Tagging unverifiable (no address, no coords) ===")
c.execute("""UPDATE churches SET confidence_score = 0.1
  WHERE country='US'
  AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
  AND (latitude IS NULL OR longitude IS NULL)
  AND (address IS NULL OR address = '')
  AND source != 'wikipedia_catholic_uni'
  AND confidence_score IS NULL""")
print(f"  Tagged {c.rowcount:,} as low confidence")

# 3. Assign diocese for single-diocese states
print("\n=== Assigning diocese by state inference ===")
total = 0
for st, dio in single_diocese.items():
    c.execute("""INSERT OR IGNORE INTO church_enrichment (church_id)
      SELECT id FROM churches WHERE country='US' AND state=?
      AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')""", (st,))
    c.execute("""UPDATE church_enrichment SET diocese=?
      WHERE church_id IN (SELECT id FROM churches WHERE country='US' AND state=?
        AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%'))
      AND (diocese IS NULL OR diocese='')""", (dio, st))
    if c.rowcount > 0:
        print(f"  {st}: +{c.rowcount} -> {dio}")
        total += c.rowcount
conn.commit()
print(f"  Total new: {total:,}")

# 4. Final stats
c.execute("""SELECT COUNT(*) FROM churches WHERE country='US' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')""")
tot = c.fetchone()[0]
c.execute("""SELECT COUNT(*) FROM churches WHERE country='US' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%') AND latitude IS NOT NULL""")
coords = c.fetchone()[0]
c.execute("""SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese!='' AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
dio = c.fetchone()[0]
print(f"\n=== FINAL ===")
print(f"Total US Catholic: {tot:,}")
print(f"With coordinates: {coords:,} ({100*coords/tot:.0f}%)")
print(f"With diocese: {dio:,} ({100*dio/tot:.0f}%)")

conn.close()

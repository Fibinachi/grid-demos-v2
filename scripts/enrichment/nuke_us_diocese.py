"""
NUKE: Clear all US Catholic diocese assignments, then rebuild from cleaner Burchfiel data only.
This removes ALL pre-existing wrong data (Fairbanks in NJ, Portland in FL, etc.)
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

conn = connect()
c = conn.cursor()

# Count before
c.execute("""SELECT COUNT(*) FROM church_enrichment ce
  JOIN churches ch ON ch.id=ce.church_id
  WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
before = c.fetchone()[0]
print(f"Before: {before:,} US Catholic with diocese")

# NUKE: clear all diocese/province for US Catholic churches
print("\nClearing ALL US Catholic diocese assignments...")
c.execute("""UPDATE church_enrichment SET diocese=NULL, diocese_detail=NULL, 
  province=NULL, province_detail=NULL
  WHERE church_id IN (
    SELECT id FROM churches 
    WHERE country='US' 
    AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
  )""")
print(f"  Cleared {c.rowcount:,} rows")
conn.commit()

# Verify
c.execute("""SELECT COUNT(*) FROM church_enrichment ce
  JOIN churches ch ON ch.id=ce.church_id
  WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
print(f"After: {c.fetchone()[0]:,} US Catholic with diocese")

conn.close()
print("\nNow re-run in order:")
print("  1. scripts/enrichment/import_us_diocese.py")
print("  2. scripts/enrichment/spatial_join_diocese.py")
print("  3. scripts/enrichment/assign_state_diocese.py")
print("  4. _fix_ak.py")

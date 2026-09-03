"""
Assign diocese to remaining unassigned US Catholic churches using state fallback.
For Alaska: 2 dioceses (Fairbanks north, Anchorage-Juneau south)
For single-diocese states: assign the only diocese
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

conn = connect()
c = conn.cursor()

# Single-diocese states from Burchfiel mapper
single_diocese_states = {
    'AK': {'Anchorage-Juneau', 'Fairbanks'},  # 2 dioceses - need lat split
    'AL': {'Mobile'},  'AR': {'Little Rock'}, 'CT': {'Hartford'},
    'DC': {'Washington'}, 'DE': {'Wilmington'}, 'GA': {'Atlanta'},
    'HI': {'Honolulu'}, 'ID': {'Boise'}, 'KY': {'Lexington'},
    'ME': {'Portland in Maine'}, 'MS': {'Jackson'}, 'MT': {'Great Falls-Billings'},
    'NC': {'Raleigh'}, 'ND': {'Bismark'}, 'NH': {'Manchester'},
    'NV': {'Las Vegas'}, 'RI': {'Providence'}, 'SC': {'Charleston'},
    'SD': {'Sioux Falls'}, 'TN': {'Nashville'}, 'UT': {'Salt Lake City'},
    'VA': {'Richmond'}, 'VT': {'Burlington'}, 'WV': {'Wheeling-Charleston'},
    'WY': {'Cheyenne'},
}

# Non-single-diocese states that need spatial — skip those
multi_diocese = {'CA','CO','FL','IA','IL','IN','KS','LA','MA','MD','MI','MN','MO','NC',
                 'NE','NJ','NM','NY','OH','OK','OR','PA','TX','WA','WI'}

print("Assigning diocese via state fallback...")

# AK: Fairbanks for latitude >= 63, Anchorage-Juneau for < 63
c.execute("""
    UPDATE church_enrichment 
    SET diocese = CASE 
        WHEN ch.latitude >= 63.0 THEN 'Fairbanks'
        ELSE 'Anchorage-Juneau'
    END
    FROM churches ch
    WHERE church_enrichment.church_id = ch.id
      AND ch.state='AK' AND ch.country='US'
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND (church_enrichment.diocese IS NULL OR church_enrichment.diocese = '')
      AND ch.latitude IS NOT NULL
""")
print(f"  AK lat-split: {c.rowcount} assigned")

# Single-diocese states (only 1 diocese)
for state, dioceses in single_diocese_states.items():
    if state == 'AK' or len(dioceses) != 1:
        continue
    diocese = list(dioceses)[0]
    c.execute(f"""
        UPDATE church_enrichment 
        SET diocese = ?
        FROM churches ch
        WHERE church_enrichment.church_id = ch.id
          AND ch.state='{state}' AND ch.country='US'
          AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
          AND (church_enrichment.diocese IS NULL OR church_enrichment.diocese = '')
    """, (diocese,))
    if c.rowcount > 0:
        print(f"  {state}: {c.rowcount} assigned to {diocese}")

conn.commit()

# Final stats
c.execute("""SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id
  WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')")
cath_total = c.fetchone()[0]
print(f"\nFinal: {total:,} / {cath_total:,} ({100*total/cath_total:.1f}%)")

# AK specific
c.execute("""SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id
  WHERE ch.state='AK' AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
ak = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE state='AK' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')")
ak_total = c.fetchone()[0]
print(f"  AK: {ak:,} / {ak_total:,} ({100*ak/ak_total:.0f}%)")

# FL specific  
c.execute("""SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id
  WHERE ch.state='FL' AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
fl = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE state='FL' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')")
fl_total = c.fetchone()[0]
print(f"  FL: {fl:,} / {fl_total:,} ({100*fl/fl_total:.0f}%)")

conn.close()

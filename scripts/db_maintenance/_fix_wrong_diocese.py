"""
Smart cleanup: NULL out wrong-state diocese assignments, then re-import from Burchfiel.
Only keeps diocese assignments where church state matches diocese's expected states.
"""
import sqlite3, csv
from collections import defaultdict

conn = sqlite3.connect('churches.db')
c = conn.cursor()

# ── Build: diocese name → set of valid states from Burchfiel mapper ──
print("Building diocese→valid_states map from Burchfiel CSV...")
diocese_states = defaultdict(set)  # diocese name → {state_codes}
with open('data/diocese_mapper/counties_by_diocese.csv', 'r') as f:
    for row in csv.DictReader(f):
        diocese_states[row['Diocese'].strip()].add(row['State_Code'].strip())

print(f"  {len(diocese_states)} diocese names from mapper")

# Eastern Rite / national dioceses that span many states — these are OK
multi_state_ok = {
    'Military Services of the United States [Military Archdiocese]',
    'Chair of Saint Peter',  # Ordinariate
}
for d in diocese_states:
    if '[' in d:  # Eastern Rite eparchies
        multi_state_ok.add(d)

# ── Find wrong assignments ──
print("\n=== Finding wrong-state diocese assignments ===")

# Get all US Catholic churches with diocese
c.execute("""
    SELECT ce.church_id, ch.state, ce.diocese
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
""")

wrong_ids = []
wrong_summary = defaultdict(int)  # (diocese, state) → count

for church_id, state, diocese in c.fetchall():
    state = (state or '').upper().strip()
    diocese = (diocese or '').strip()
    
    # Skip if empty
    if not state or not diocese:
        continue
    
    # Eastern Rite / national = always OK
    if diocese in multi_state_ok:
        continue
    
    # Check if diocese name is known and state is valid
    if diocese in diocese_states:
        if state not in diocese_states[diocese]:
            wrong_ids.append(church_id)
            wrong_summary[(diocese, state)] += 1
    # If diocese not in Burchfiel mapper at all, check if it looks like a
    # generic city name that might be ambiguous
    elif diocese not in diocese_states:
        # Unknown diocese name — could be from global data, flag it
        wrong_ids.append(church_id)
        wrong_summary[(diocese, state)] += 1

print(f"\n  Wrong-state assignments to NULL out: {len(wrong_ids):,}")
print(f"  Unique (diocese, state) combos: {len(wrong_summary)}")

# Show top offenders
print("\nTop wrong combos:")
for (diocese, state), cnt in sorted(wrong_summary.items(), key=lambda x: -x[1])[:20]:
    expected = ', '.join(sorted(diocese_states.get(diocese, ['?' ])))
    print(f"  {diocese:35s} in {state:5s} -> {cnt:>4,} churches (expected states: {expected})")

# ── NULL them out ──
if wrong_ids:
    print(f"\n=== NULLing {len(wrong_ids):,} wrong diocese assignments ===")
    # Process in batches of 500
    batch_size = 500
    for i in range(0, len(wrong_ids), batch_size):
        batch = wrong_ids[i:i+batch_size]
        placeholders = ','.join(['?']*len(batch))
        c.execute(f"""
            UPDATE church_enrichment 
            SET diocese=NULL, diocese_detail=NULL, province=NULL, province_detail=NULL
            WHERE church_id IN ({placeholders})
        """, batch)
        if (i // batch_size) % 50 == 0:
            print(f"  Processed {i:,} / {len(wrong_ids):,}")
    conn.commit()
    print(f"  Done. NULLed {c.rowcount:,} rows")

# ── Final state ──
c.execute("""
    SELECT COUNT(*) FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
""")
print(f"\nCatholic US churches with valid diocese: {c.fetchone()[0]:,}")

conn.close()
print("\nNow re-run: import_us_diocese.py to fill the NULLs with correct Burchfiel data")

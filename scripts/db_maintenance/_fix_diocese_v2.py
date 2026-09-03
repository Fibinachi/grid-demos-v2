"""
Smart diocese cleanup v2: normalize name formats, then detect wrong-state assignments.
"""
import sqlite3, csv
from collections import defaultdict

conn = sqlite3.connect('churches.db')
c = conn.cursor()

# ── Normalize diocese names ──
def normalize(name):
    """Normalize diocese name for comparison."""
    n = name.strip()
    # Remove prefixes
    for prefix in ['Archdiocese of ', 'Diocese of ', 'Archdiocese ', 'Diocese ']:
        if n.startswith(prefix):
            n = n[len(prefix):]
    # Remove suffixes in parens
    if ' (' in n:
        n = n[:n.index(' (')]
    return n.strip()

# ── Build: normalized_name → set of valid state codes ──
print("Building normalized diocese→states map...")
diocese_states = defaultdict(set)
diocese_original = {}  # normalized → original name from CSV
with open('data/diocese_mapper/counties_by_diocese.csv', 'r') as f:
    for row in csv.DictReader(f):
        orig = row['Diocese'].strip()
        norm = normalize(orig)
        diocese_states[norm].add(row['State_Code'].strip())
        diocese_original[norm] = orig

print(f"  {len(diocese_states)} unique normalized diocese names")

# Eastern Rite / national — always valid multi-state
multi_state_patterns = ['[', 'Chair of Saint Peter', 'Military']
def is_multi_state_ok(name):
    return any(p in name for p in multi_state_patterns)

# ── Find bad assignments ──
print("\n=== Finding wrong-state assignments ===")

c.execute("""
    SELECT ce.church_id, ch.state, ce.diocese
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
""")

wrong_ids = []
wrong_by_name = defaultdict(lambda: defaultdict(int))

for church_id, state, diocese in c.fetchall():
    state = (state or '').upper().strip()
    if not state or not diocese:
        continue
    
    norm = normalize(diocese)
    
    if is_multi_state_ok(diocese) or is_multi_state_ok(norm):
        continue
    
    if norm in diocese_states:
        if state not in diocese_states[norm]:
            wrong_ids.append(church_id)
            wrong_by_name[norm][state] += 1
    # else: unknown diocese, could be global data — skip for now

print(f"\n  Definitely wrong (known diocese, wrong state): {len(wrong_ids):,}")

# Show top wrong combos
print("\nWrong combos (diocese → state):")
flat = []
for norm, states in wrong_by_name.items():
    for st, cnt in states.items():
        flat.append((cnt, norm, st, ', '.join(sorted(diocese_states[norm]))))
flat.sort(key=lambda x: -x[0])
for cnt, norm, st, expected in flat[:25]:
    print(f"  {norm:35s} in {st:5s} -> {cnt:>4,} (expected: {expected})")

# ── NULL them out ──
if wrong_ids:
    print(f"\n=== NULLing {len(wrong_ids):,} wrong entries ===")
    batch_size = 500
    for i in range(0, len(wrong_ids), batch_size):
        batch = wrong_ids[i:i+batch_size]
        c.execute(f"""
            UPDATE church_enrichment 
            SET diocese=NULL, diocese_detail=NULL, province=NULL, province_detail=NULL
            WHERE church_id IN ({','.join(['?']*len(batch))})
        """, batch)
        if i % 5000 == 0:
            print(f"  {i:,} / {len(wrong_ids):,}")
    conn.commit()
    print(f"  Done. NULLed wrong entries")

# ── Remaining valid ──
c.execute("""SELECT COUNT(*) FROM church_enrichment ce
JOIN churches ch ON ch.id=ce.church_id
WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
print(f"\nRemaining valid Catholic US diocese assignments: {c.fetchone()[0]:,}")

conn.close()
print("\nNext: re-run import_us_diocese.py")

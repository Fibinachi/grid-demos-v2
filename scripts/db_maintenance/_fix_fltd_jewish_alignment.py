#!/usr/bin/env python3
"""
_fix_fltd_jewish_alignment.py — Restructure FLTD taxonomy + reassign all Jewish taxonomy_ids.

Problems found:
  1. 92% of Jewish entries map to catch-all "Jewish" node (id=242)
  2. Taxonomy tree has Orthodox/Hasidic/etc nested under "Reform" (wrong hierarchy)
  3. 6 entries have taxonomy_id=2 (Christian)
  4. 1 entry has NULL taxonomy_id
  5. 287 entries have non-canonical tradition values (DeepSeek verbosity)
  6. 1 "Messianic (Netzarita)" should be Christian

Fix plan:
  A. Restructure taxonomy: proper Judaic hierarchy
  B. Normalize 49 non-canonical traditions → canonical FLTD
  C. Reassign all 23,451 taxonomy_ids based on tradition
  D. Fix edge cases (6 Christian, 1 NULL, 1 Messianic)
"""
import sqlite3, time, sys
from datetime import datetime, timezone
from collections import defaultdict

DB = "churches.db"
SCRIPT_NAME = "fix_fltd_jewish_alignment"
STARTED_AT = datetime.now(timezone.utc).isoformat()
CHUNK_SIZE = 500

conn = sqlite3.connect(f"E:\\grid\\{DB}", timeout=60)
c = conn.cursor()
c.execute("PRAGMA busy_timeout=30000")
c.execute("PRAGMA journal_mode=WAL")

def progress_bar(current, total, label="", width=40):
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = chr(9608) * filled + chr(9617) * (width - filled)
    print(f"\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)", end="", flush=True)

# ═══════════════════════════════════════════════════════════════
# STEP A: Fix taxonomy tree structure
# ═══════════════════════════════════════════════════════════════
print("Step A: Fixing taxonomy tree...")

# Check current tree
c.execute("SELECT id, name, parent_id FROM taxonomy WHERE id=5")
judaism = c.fetchone()
print(f"  Judaism root: {judaism}")

# The taxonomy table may not have direct parent-child links for the new nodes.
# Let's check what nodes exist from build_remaining_taxonomy.py
c.execute("""SELECT id, name, parent_id FROM taxonomy 
WHERE id IN (5, 539, 540, 541, 542, 543, 544, 545, 546, 547, 548, 549, 550, 551, 552, 553, 554)
ORDER BY id""")
existing = {r[0]: (r[1], r[2]) for r in c.fetchall()}
print(f"  Existing FLTD nodes: {len(existing)}")

# The correct hierarchy from build_remaining_taxonomy.py:
# Judaism (id=5)
#   Rabbinic (id=539)
#     Orthodox (id=542), Orthodox (Chabad) (id=543), Orthodox (Hasidic) (id=544),
#     Orthodox (Modern) (id=545), Orthodox (Yeshiva) (id=546), Conservative (id=547),
#     Reform (id=548), Reconstructionist (id=549), Sephardic (id=550),
#     Mizrahi (id=551), Humanistic (id=552), Rabbinic (general) (id=553)
#   Karaite (id=540)
#     Karaite (general) (id=554)
#   Other (id=541)

# Fix parent relationships
FIXES = [
    # (node_id, new_parent_id)
    (32, 539),     # Conservative → Rabbinic
    (33, 541),     # Judaism (under Other) → Other
    (34, 540),     # Karaite → Karaite (correct)
    (35, 539),     # Orthodox → Rabbinic
    (37, 539),     # Reconstructionist → Rabbinic
    (38, 539),     # Reform → Rabbinic
    (235, 542),    # Chabad → Orthodox
    (236, 544),    # Hasidic → Orthodox (Hasidic)
    (237, 543),    # Jewish (Chabad) → Orthodox (Chabad)
    (239, 544),    # Orthodox (Hasidic) → Orthodox (Hasidic)
    (238, 543),    # Orthodox (Chabad) → Orthodox (Chabad)
    (240, 550),    # Sephardic → Sephardic
    (241, 552),    # Humanistic Judaism → Humanistic
    (242, 539),    # Jewish → Rabbinic (catch-all)
    (243, 541),    # Orthodox Union → Other
]

fixed_parents = 0
for node_id, new_parent in FIXES:
    if node_id in existing:
        old_parent = existing[node_id][1]
        if old_parent != new_parent:
            c.execute("UPDATE taxonomy SET parent_id=? WHERE id=?", (new_parent, node_id))
            fixed_parents += 1
            print(f"    Fixed id={node_id} ({existing[node_id][0]}): parent {old_parent} → {new_parent}")

print(f"  Fixed {fixed_parents} parent relationships")

# Remove broken "Reform" children that shouldn't exist (id=38's old children already fixed above)
# The nodes 542-554 already have correct parent references from build_remaining_taxonomy.py
# Let's verify
c.execute("""SELECT t.id, t.name, t.parent_id, p.name as parent_name 
FROM taxonomy t LEFT JOIN taxonomy p ON t.parent_id = p.id 
WHERE t.id IN (539,540,541,542,543,544,545,546,547,548,549,550,551,552,553,554)
ORDER BY t.id""")
print("\n  Final taxonomy tree:")
for r in c.fetchall():
    print(f"    id={r[0]}: {r[1]} (parent={r[2]}={r[3]})")

conn.commit()

# ═══════════════════════════════════════════════════════════════
# STEP B: Normalize non-canonical traditions
# ═══════════════════════════════════════════════════════════════
print("\nStep B: Normalizing non-canonical traditions...")

TRADITION_MAP = {
    # Chabad variants
    'Chabad (Orthodox)': 'Orthodox (Chabad)',
    'Chabad (Orthodox/Hasidic)': 'Orthodox (Chabad)',
    
    # Hasidic variants
    'Hasidic': 'Orthodox (Hasidic)',
    'Hassidic': 'Orthodox (Hasidic)',
    'Orthodox (Chasidic)': 'Orthodox (Hasidic)',
    'Orthodox (Hasidic - Satmar)': 'Orthodox (Hasidic)',
    'Orthodox (Hasidic - Belz)': 'Orthodox (Hasidic)',
    'Breslov': 'Orthodox (Hasidic)',
    'Carlebach': 'Orthodox (Hasidic)',
    
    # Sephardic variants
    'Sephardic (Bukharian)': 'Sephardic',
    'Yemenite': 'Sephardic',
    
    # Ethnic/cultural → Rabbinic
    'Ashkenazi': 'Rabbinic',
    'Italian': 'Rabbinic',
    'Jewish (non-denominational)': 'Rabbinic',
    'Choral': 'Rabbinic',
    'General': 'Rabbinic',
    'Memorial': 'Rabbinic',
    
    # Miscellaneous
    'Neolog': 'Conservative',
    'Liberal': 'Reform',
    'Progressive': 'Reform',
    'Liberal/Reform': 'Reform',
    'Masorti': 'Conservative',
    'Masorti (Conservative)': 'Conservative',
    'Status Quo': 'Conservative',
    'Status Quo Ante': 'Conservative',
    'Conservative/Reform': 'Conservative',
    'Conservative/Reform (likely)': 'Conservative',
    'Reform/Conservative (likely)': 'Conservative',
    'Orthodox Union': 'Orthodox',
    'Orthodox (Agudath Israel)': 'Orthodox',
    'Orthodox (Sephardic)': 'Sephardic',
    'Religious Zionist': 'Orthodox',
    'Zionist': 'Orthodox',
    'Kabbalistic': 'Orthodox',
    'Orthodox (likely Hasidic/European heritage)': 'Orthodox (Hasidic)',
    'Samaritan': 'Karaite',
    
    # Uncertain → Rabbinic (default)
    'Unspecified': 'Rabbinic',
    'Uncertain': 'Rabbinic',
    'Unspecified (likely Conservative/Reform)': 'Rabbinic',
    'Unspecified (likely Orthodox)': 'Rabbinic',
    'Unspecified (likely Reform/Conservative)': 'Rabbinic',
    'Unspecified (likely Orthodox/Conservative)': 'Rabbinic',
    'Orthodox (likely)': 'Orthodox',
    'Rabbinic (unspecified)': 'Rabbinic',
    
    # Non-religious / other
    'Secular': 'Humanistic',
    'Unaffiliated': 'Humanistic',
    'Unaffiliated (Museum)': 'Humanistic',
    'Jewish (educational institution)': 'Rabbinic',
    'Ancient': 'Karaite',
    
    # Christian — this one needs faith change too
    'Messianic (Netzarita)': None,  # handled separately
}

# Also handle "Reform" under taxonomy (already canonical but path was wrong)
# These are already canonical but need taxonomy_id reassignment

normalized_count = 0
edge_cases = []

for old_trad, new_trad in TRADITION_MAP.items():
    if new_trad is None:
        # Messianic — handle separately
        c.execute("SELECT id, name, city, state FROM churches WHERE faith='Judaism' AND tradition=?", (old_trad,))
        for r in c.fetchall():
            edge_cases.append(('messianic', r[0], r[1], r[2], r[3]))
        continue
    
    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND tradition=?", (old_trad,))
    cnt = c.fetchone()[0]
    if cnt > 0:
        c.execute("UPDATE churches SET tradition=? WHERE faith='Judaism' AND tradition=?", (new_trad, old_trad))
        normalized_count += cnt
        print(f"  {old_trad} → {new_trad}: {cnt}")

print(f"  Normalized {normalized_count} tradition values")
conn.commit()

# ═══════════════════════════════════════════════════════════════
# STEP C: Reassign taxonomy_ids based on tradition
# ═══════════════════════════════════════════════════════════════
print("\nStep C: Reassigning taxonomy_ids...")

# Map tradition → taxonomy_id
c.execute("SELECT id, name FROM taxonomy WHERE parent_id IN (539, 540, 541) OR id IN (539, 540, 541)")
tax_nodes = {r[1]: r[0] for r in c.fetchall()}
# Also add the root
tax_nodes['Judaism'] = 5

print(f"  Taxonomy nodes available: {len(tax_nodes)}")

# Build tradition→taxonomy_id map
TRADITION_TO_TAX = {
    # Rabbinic sub-traditions → their specific nodes
    'Orthodox': tax_nodes.get('Orthodox', 539),
    'Orthodox (Chabad)': tax_nodes.get('Orthodox (Chabad)', 543),
    'Orthodox (Hasidic)': tax_nodes.get('Orthodox (Hasidic)', 544),
    'Orthodox (Modern)': tax_nodes.get('Orthodox (Modern)', 545),
    'Orthodox (Yeshiva)': tax_nodes.get('Orthodox (Yeshiva)', 546),
    'Conservative': tax_nodes.get('Conservative', 547),
    'Reform': tax_nodes.get('Reform', 548),
    'Reconstructionist': tax_nodes.get('Reconstructionist', 549),
    'Sephardic': tax_nodes.get('Sephardic', 550),
    'Mizrahi': tax_nodes.get('Mizrahi', 551),
    'Humanistic': tax_nodes.get('Humanistic', 552),
    'Rabbinic': tax_nodes.get('Rabbinic (general)', 553),
    
    # Karaite
    'Karaite': tax_nodes.get('Karaite (general)', 554),
    
    # Other
    'Judaism': 541,  # Other
}

# Load all Jewish entries
c.execute("SELECT id, tradition FROM churches WHERE faith='Judaism'")
rows = c.fetchall()
total = len(rows)
print(f"  {total:,} entries to reassign")

reassigned = 0
for i in range(0, total, CHUNK_SIZE):
    chunk = rows[i:i+CHUNK_SIZE]
    
    for church_id, tradition in chunk:
        new_tax_id = TRADITION_TO_TAX.get(tradition)
        if new_tax_id is None:
            new_tax_id = 541  # Other as fallback
        
        c.execute("SELECT taxonomy_id FROM churches WHERE id=?", (church_id,))
        old_tax = c.fetchone()[0]
        if old_tax != new_tax_id:
            c.execute("UPDATE churches SET taxonomy_id=? WHERE id=?", (new_tax_id, church_id))
            reassigned += 1
    
    conn.commit()
    progress_bar(i + len(chunk), total, "  Reassigning")

print(f"\n  Reassigned {reassigned:,} entries")

# ═══════════════════════════════════════════════════════════════
# STEP D: Fix edge cases
# ═══════════════════════════════════════════════════════════════
print("\nStep D: Fixing edge cases...")

# D1: Fix 6 entries with taxonomy_id=2 (Christian) but faith=Judaism
c.execute("SELECT id, name, tradition FROM churches WHERE faith='Judaism' AND taxonomy_id=2")
christian_mapped = c.fetchall()
print(f"  Christian-mapped (id=2): {len(christian_mapped)}")
for rid, name, trad in christian_mapped:
    new_tax = TRADITION_TO_TAX.get(trad, 541)
    c.execute("UPDATE churches SET taxonomy_id=? WHERE id=?", (new_tax, rid))
    print(f"    #{rid}: {name} → taxonomy_id={new_tax}")

# D2: Fix 1 NULL taxonomy_id
c.execute("SELECT id, name, tradition FROM churches WHERE faith='Judaism' AND taxonomy_id IS NULL")
null_tax = c.fetchall()
for rid, name, trad in null_tax:
    new_tax = TRADITION_TO_TAX.get(trad, 541)
    c.execute("UPDATE churches SET taxonomy_id=? WHERE id=?", (new_tax, rid))
    print(f"  NULL tax #{rid}: {name} → taxonomy_id={new_tax}")

# D3: Move Messianic (Netzarita) to Christian
for case_type, rid, name, city, state in edge_cases:
    if case_type == 'messianic':
        c.execute("SELECT id FROM taxonomy WHERE name='Christian'")
        christian_root = c.fetchone()
        if christian_root:
            c.execute("""UPDATE churches SET faith='Christian', tradition='Messianic', 
                taxonomy_id=?, jewish_confidence=NULL, jewish_classification_source='corrected_messianic',
                jewish_updated=? WHERE id=?""", 
                (christian_root[0], datetime.now(timezone.utc).isoformat(), rid))
            print(f"  Messianic → Christian: #{rid}: {name} | {city}, {state}")

conn.commit()

# ═══════════════════════════════════════════════════════════════
# STEP E: Verify
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
print(f"Total Judaism: {total:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND taxonomy_id IS NULL")
print(f"NULL taxonomy_id: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND taxonomy_id = 2")
print(f"Christian-mapped (id=2): {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND jewish_confidence IS NULL")
print(f"NULL jewish_confidence: {c.fetchone()[0]}")

print("\nTaxonomy distribution:")
c.execute("""SELECT t.name, COUNT(*) FROM churches ch 
JOIN taxonomy t ON ch.taxonomy_id = t.id 
WHERE ch.faith='Judaism' 
GROUP BY t.name ORDER BY COUNT(*) DESC""")
for name, cnt in c.fetchall():
    pct = cnt / total * 100
    print(f"  {name}: {cnt:,} ({pct:.1f}%)")

# Verify taxonomy tree
print("\nTaxonomy tree verification:")
c.execute("""WITH RECURSIVE subtree AS (
    SELECT id, name, parent_id, 0 AS depth FROM taxonomy WHERE id=5
    UNION ALL
    SELECT t.id, t.name, t.parent_id, s.depth+1 
    FROM taxonomy t JOIN subtree s ON t.parent_id=s.id
) SELECT name, depth, parent_id FROM subtree ORDER BY depth, name""")
for name, depth, pid in c.fetchall():
    indent = "  " * depth
    c2 = conn.cursor()
    c2.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=(SELECT id FROM taxonomy WHERE name=? AND parent_id=?)", (name, pid))
    cnt = c2.fetchone()[0]
    print(f"  {indent}{name}: {cnt:,} entries")

# Log provenance
c.execute("""INSERT INTO provenance_log (script_name, started_at, completed_at, notes) 
VALUES (?, ?, ?, ?)""", (
    SCRIPT_NAME, STARTED_AT, datetime.now(timezone.utc).isoformat(),
    f"FLTD alignment fix: restructured taxonomy tree ({fixed_parents} parent fixes), "
    f"normalized {normalized_count} traditions, reassigned {reassigned} taxonomy_ids, "
    f"fixed {len(christian_mapped)} Christian-mapped + {len(null_tax)} NULL + {len(edge_cases)} edge cases."
))
conn.commit()

conn.close()
print("\nDone.")

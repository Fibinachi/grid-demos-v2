"""Full FLTD alignment audit for Judaism."""
import sqlite3

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

print("=" * 60)
print("FLTD Alignment Audit — Judaism")
print("=" * 60)

# 1. Taxonomy tree under Judaism
print("\n--- Taxonomy nodes under Judaism ---")
c.execute("SELECT id, name, parent_id FROM taxonomy WHERE name='Judaism'")
judaism_root = c.fetchone()
judaism_id = judaism_root[0] if judaism_root else None
print(f"Judaism root: id={judaism_id}")

if judaism_id:
    c.execute("""WITH RECURSIVE subtree AS (
        SELECT id, name, parent_id, 0 AS depth FROM taxonomy WHERE id=?
        UNION ALL
        SELECT t.id, t.name, t.parent_id, s.depth+1 
        FROM taxonomy t JOIN subtree s ON t.parent_id=s.id
    ) SELECT id, name, depth FROM subtree ORDER BY depth, name""", (judaism_id,))
    for tid, name, depth in c.fetchall():
        indent = "  " * depth
        c2 = conn.cursor()
        try:
            c2.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=?", (tid,))
            cnt = c2.fetchone()[0]
        except:
            cnt = 0
        print(f"  {indent}id={tid}: {name} ({cnt:,} churches)")

# 2. Taxonomy IDs actually used
print("\n--- Taxonomy IDs used by Judaism churches ---")
c.execute("""SELECT taxonomy_id, COUNT(*) FROM churches 
WHERE faith='Judaism' GROUP BY taxonomy_id ORDER BY COUNT(*) DESC""")
for tid, cnt in c.fetchall():
    c2 = conn.cursor()
    c2.execute("SELECT name FROM taxonomy WHERE id=?", (tid,))
    row = c2.fetchone()
    name = row[0] if row else ">>> NOT IN TAXONOMY <<<"
    print(f"  id={tid}: {name} ({cnt:,} entries)")

# 3. NULL taxonomy_id
print("\n--- Entries with NULL taxonomy_id ---")
c.execute("""SELECT id, name, city, state, country, tradition 
FROM churches WHERE faith='Judaism' AND taxonomy_id IS NULL""")
for r in c.fetchall():
    print(f"  #{r[0]}: {r[1]} | {r[2]}, {r[3]}, {r[4]} | trad={r[5]}")

# 4. Non-canonical traditions
print("\n--- Non-canonical traditions ---")
CANONICAL = {
    'Rabbinic', 'Orthodox', 'Orthodox (Chabad)', 'Orthodox (Hasidic)',
    'Orthodox (Modern)', 'Orthodox (Yeshiva)', 'Reform', 'Conservative',
    'Reconstructionist', 'Sephardic', 'Mizrahi', 'Humanistic', 'Karaite',
    'Judaism'  # root-level
}
c.execute("""SELECT tradition, COUNT(*) FROM churches 
WHERE faith='Judaism' GROUP BY tradition ORDER BY COUNT(*) DESC""")
non_canon = []
for trad, cnt in c.fetchall():
    if trad not in CANONICAL:
        non_canon.append((trad, cnt))
        print(f"  {trad}: {cnt:,}")

if not non_canon:
    print("  ✅ All traditions canonical")
else:
    total_non_canon = sum(c for _, c in non_canon)
    print(f"\n  Total non-canonical: {total_non_canon:,} of 23,451")

# 5. Faith=NULL check
print("\n--- Global NULL faith check ---")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL")
print(f"  NULL faith: {c.fetchone()[0]:,}")

conn.close()
print("\nDone.")

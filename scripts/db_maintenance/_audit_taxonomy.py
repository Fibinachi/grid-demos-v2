import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")

# --- TAXONOMY STRUCTURE ---
cur = db.execute("SELECT id, name, parent_id, full_path, depth, root_id, tradition_id, family_id FROM taxonomy ORDER BY id")
rows = cur.fetchall()
print(f"Total taxonomy nodes: {len(rows)}")
print()

# Print first-level nodes (depth=0)
print("=== ROOT NODES (depth=0) ===")
for r in rows:
    if r[3] == 0:  # depth
        print(f"  id={r[0]}  name={r[1]}  full_path={r[7]}")
print()

# --- SEARCH FOR MISCLASSIFICATIONS ---
print("=" * 70)
print("HINDU-TAGGED ENTRIES WITH CHRISTIAN NAMES")
print("=" * 70)

# Hindu-tagged with Christian keywords
keywords = ['%baptist%', '%church%', '%christ%', '%jesus%', '%catholic%', '%methodist%', 
            '%pentecostal%', '%anglican%', '%lutheran%', '%presbyterian%',
            '%gospel%', '%apostolic%', '%trinity%', '%calvary%', '%chapel%',
            '%cathedral%', '%basilica%', '%monsieur%', '%saint%', '%st %']

for kw in keywords:
    query = """
        SELECT c.id, c.name, c.city, c.state, c.country, t.name as tax_name, t.full_path
        FROM churches c
        JOIN taxonomy t ON c.taxonomy_id = t.id
        WHERE (t.full_path LIKE '%Hindu%' OR t.root_id = 3)
        AND LOWER(c.name) LIKE ?
        ORDER BY c.country, c.state, c.city
        LIMIT 50
    """
    results = db.execute(query, (kw,)).fetchall()
    if results:
        print(f"\n--- Hindu-tagged with '{kw.replace('%','')}' ({len(results)} found) ---")
        for r in results[:10]:
            print(f"  #{r[0]} | {r[1][:55]:<55} | {r[2]}, {r[3]} {r[4]} | tax={r[5][:20]} | path={r[6]}")

# --- Christian-tagged with Hindu keywords ---
print()
print("=" * 70)
print("CHRISTIAN-TAGGED ENTRIES WITH HINDU NAMES")
print("=" * 70)

for kw in ['%hindu%', '%mandir%', '%temple%', '%devi%', '%shiva%', '%krishna%', '%vishnu%', '%ram%']:
    query = """
        SELECT c.id, c.name, c.city, c.state, c.country, t.name as tax_name, t.full_path
        FROM churches c
        JOIN taxonomy t ON c.taxonomy_id = t.id
        WHERE (t.full_path LIKE '%Christian%' OR t.root_id = 2)
        AND LOWER(c.name) LIKE ?
        ORDER BY c.country, c.state, c.city
        LIMIT 50
    """
    results = db.execute(query, (kw,)).fetchall()
    if results:
        print(f"\n--- Christian-tagged with '{kw.replace('%','')}' ({len(results)} found) ---")
        for r in results[:10]:
            print(f"  #{r[0]} | {r[1][:55]:<55} | {r[2]}, {r[3]} {r[4]} | tax={r[5][:20]} | path={r[6]}")

# --- Check all churches where name and taxonomy conflict ---
print()
print("=" * 70)
print("QUICK SUMMARY: 'Baptist' in name by faith")
print("=" * 70)
cur = db.execute("""
    SELECT c.faith, COUNT(*) as cnt
    FROM churches c
    WHERE LOWER(c.name) LIKE '%baptist%'
    GROUP BY c.faith
    ORDER BY cnt DESC
""")
for faith, cnt in cur.fetchall():
    print(f"  {faith:<30} {cnt:>8,}")

# Depth distribution
print()
print("=" * 70)
print("TAXONOMY DEPTH DISTRIBUTION")
print("=" * 70)
cur = db.execute("""
    SELECT t.depth, COUNT(*) as cnt
    FROM churches c
    JOIN taxonomy t ON c.taxonomy_id = t.id
    GROUP BY t.depth
    ORDER BY t.depth
""")
for depth, cnt in cur.fetchall():
    print(f"  depth={depth}: {cnt:>10,}")

# NULL taxonomy
null_cnt = db.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IS NULL").fetchone()[0]
print(f"\n  NULL taxonomy_id: {null_cnt:>10,}")
print(f"  Classified:       {db.execute('SELECT COUNT(*) FROM churches WHERE taxonomy_id IS NOT NULL').fetchone()[0]:>10,}")
print(f"  TOTAL:            {db.execute('SELECT COUNT(*) FROM churches').fetchone()[0]:>10,}")

db.close()

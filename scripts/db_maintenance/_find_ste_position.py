"""Find where STE records fall in the Phase 2 candidate ordering."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')

# Total STE candidates
cur = db.execute("""
    SELECT rowid, name FROM churches
    WHERE (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %')
    ORDER BY rowid
""")
rows = cur.fetchall()
print(f"Total STE candidates in query: {len(rows)}")

# Show first 5
for r, n in rows[:5]:
    print(f"  rowid={r}: {n}")
print("...")
# Show last 5
for r, n in rows[-5:]:
    print(f"  rowid={r}: {n}")

# Total Phase 2 candidates
cur2 = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE ((name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
        OR (name LIKE '% CTR %')
        OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
        OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
        OR (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %'))
""")
total = cur2.fetchone()[0]
print(f"Total Phase 2 candidates (updated): {total}")

# Position of first STE record
first_ste = rows[0][0]
cur3 = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE ((name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
        OR (name LIKE '% CTR %')
        OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
        OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
        OR (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %'))
    AND rowid < ?
""", (first_ste,))
before = cur3.fetchone()[0]
print(f"First STE (rowid={first_ste}) is candidate #{before+1} -- batch ~{before//100 + 1}")

# Find all STE records' batch positions
ste_batches = set()
for r, n in rows:
    cur4 = db.execute("""
        SELECT COUNT(*) FROM churches
        WHERE ((name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
            OR (name LIKE '% CTR %')
            OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
            OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
            OR (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %'))
        AND rowid < ?
    """, (r,))
    pos = cur4.fetchone()[0]
    ste_batches.add(pos // 100 + 1)

print(f"\nSTE records span batches: {sorted(ste_batches)}")

db.close()

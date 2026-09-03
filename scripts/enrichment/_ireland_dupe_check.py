"""Check Ireland duplicate stats."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Total Ireland records
total = conn.execute("SELECT COUNT(*) FROM churches WHERE country='Ireland'").fetchone()[0]
print(f"Total Ireland records: {total:,}")

# By source
print("\nBy source:")
for s in conn.execute("SELECT source, COUNT(*) FROM churches WHERE country='Ireland' GROUP BY source ORDER BY COUNT(*) DESC").fetchall():
    print(f"  {s[0] or 'NULL'}: {s[1]}")

# Exact name duplicates within Ireland
dupes = conn.execute("""
    SELECT UPPER(name), COUNT(*) as cnt, GROUP_CONCAT(source) as sources
    FROM churches WHERE country='Ireland' AND name IS NOT NULL
    GROUP BY UPPER(name) HAVING cnt > 1
    ORDER BY cnt DESC
""").fetchall()

print(f"\nExact name duplicates: {len(dupes)} groups")
total_extra = sum(d[1] - 1 for d in dupes)
print(f"Extra records (beyond first): {total_extra}")

# Show the worst
for d in dupes[:10]:
    print(f"  {d[1]}x: {d[0][:50]}")
    for s in d[2].split(','):
        print(f"    source: {s}")

# Overlap between ireland_charities_register and ireland_places_of_worship
overlap = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT UPPER(ch.name) FROM churches ch
        WHERE ch.source = 'ireland_charities_register' AND ch.country='Ireland'
        INTERSECT
        SELECT UPPER(pw.name) FROM churches pw
        WHERE pw.source = 'ireland_places_of_worship' AND pw.country='Ireland'
    )
""").fetchone()[0]
print(f"\nOverlap between charities & worship datasets: {overlap}")

conn.close()

"""Check Monsey NY state after collapse."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

c.execute("SELECT landmark_type, COUNT(*) FROM churches WHERE faith='Judaism' AND city='Monsey' AND state='NY' AND country='US' GROUP BY landmark_type ORDER BY COUNT(*) DESC")
print("Monsey NY Judaism entries:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':20s} {r[1]:>5}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND city='Monsey' AND state='NY'")
print(f"\nTotal: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND city='Monsey' AND state='NY' AND merged_into IS NOT NULL")
print(f"Merged into primary: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND city='Monsey' AND state='NY' AND merged_into IS NULL")
print(f"Primary entries remaining: {c.fetchone()[0]}")

# Show the primaries
c.execute("""
    SELECT id, name, landmark_type, tradition, 
           (SELECT COUNT(*) FROM churches s WHERE s.merged_into = p.id) as merged
    FROM churches p 
    WHERE faith='Judaism' AND city='Monsey' AND state='NY' AND merged_into IS NULL
    ORDER BY name
""")
print(f"\nPrimary entries:")
for r in c.fetchall():
    print(f"  #{r[0]:>8} {str(r[1] or '')[:50]:50s} [{r[2] or ''}] merged={r[4]}")

# Show some ministries
c.execute("""
    SELECT id, name, landmark_type, merged_into FROM churches 
    WHERE faith='Judaism' AND city='Monsey' AND state='NY' AND merged_into IS NOT NULL
    LIMIT 10
""")
print(f"\nSample of merged entries:")
for r in c.fetchall():
    c.execute("SELECT name FROM churches WHERE id=?", (r[3],))
    primary = c.fetchone()
    print(f"  #{r[0]} {str(r[1] or '')[:45]:45s} [{r[2] or ''}] -> #{r[3]} {str(primary[0] if primary else '')[:30]}")

conn.close()

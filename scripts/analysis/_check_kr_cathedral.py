"""Check Korean cathedral info."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

print("=== Catholic dioceses/cathedrals in South Korea ===")
c.execute("""
    SELECT id, name, city FROM churches 
    WHERE country='KR' AND faith='Christian' 
      AND LOWER(COALESCE(name,'')) LIKE '%cathedral%'
""")
for r in c.fetchall():
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:60]:60s} | {r[2] or '?'}")

print("\n=== Masan area Catholic churches ===")
c.execute("""
    SELECT id, name, city FROM churches 
    WHERE country='KR' AND faith='Christian' 
      AND (LOWER(COALESCE(name,'')) LIKE '%masan%' OR city IN ('Masan', 'Changwon'))
      AND tradition='Catholic Churches'
    ORDER BY name
""")
for r in c.fetchall():
    print(f"  {r[0]:>8d} | {str(r[1] or '')[:60]:60s} | {r[2] or '?'}")

# Check the Jung-dong one
print("\n=== Jung-dong Cathedral record ===")
c.execute("SELECT id, name, faith, tradition, city FROM churches WHERE id=3496257")
r = c.fetchone()
print(f"  {r[0]:>8d} | {r[1]} | {r[2]} | {r[3]} | {r[4]}")

conn.close()

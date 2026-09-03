"""Final check of Europe scan."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Check 'temple' entries
c.execute("SELECT id, name, city, country FROM churches WHERE faith='Judaism' AND landmark_type='temple'")
print("'temple' type entries (may need -> synagogue):")
for r in c.fetchall():
    print(f"  #{r[0]} {r[1]} {r[2]} {r[3]}")

# Check odd types with spaces
c.execute("SELECT landmark_type, COUNT(*) FROM churches WHERE faith='Judaism' AND landmark_type LIKE '% %' GROUP BY landmark_type")
print("\nOdd types with spaces:")
for r in c.fetchall():
    print(f"  '{r[0]}': {r[1]}")

# Check overall worldwide Judaism
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
il = c.fetchone()[0]
print(f"\nWorldwide Judaism: {total:,} (Israel: {il:,}, ex-Israel: {total-il:,})")
print(f"Problematic worldwide: ", end="")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))")
print(c.fetchone()[0])

conn.close()

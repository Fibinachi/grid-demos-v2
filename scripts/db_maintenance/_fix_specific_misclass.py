"""Find and fix specific misclassified entries, then save reference note."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Find the specific entries
queries = [
    "SELECT id, name, faith, tradition, country FROM churches WHERE LOWER(COALESCE(name,'')) LIKE '%reel recovery%'",
    "SELECT id, name, faith, tradition, country FROM churches WHERE LOWER(COALESCE(name,'')) LIKE '%new life%' AND faith='Judaism'",
    "SELECT id, name, faith, tradition, country FROM churches WHERE LOWER(COALESCE(name,'')) LIKE '%foothills presbytery%'",
]

for q in queries:
    c.execute(q)
    for r in c.fetchall():
        print(f"  {r[0]:>8d} | {str(r[1] or '')[:55]:55s} | {r[2]:15s} | {str(r[3] or ''):25s} | {r[4] or '?'}")

# Fix Reel Recovery - Christian ministry
c.execute("SELECT id, name FROM churches WHERE LOWER(COALESCE(name,'')) LIKE '%reel recovery%'")
for r in c.fetchall():
    c.execute("UPDATE churches SET faith='Christian', tradition='Protestant', landmark_type='ministry', last_updated=datetime('now') WHERE id=?", (r[0],))
    print(f"Fixed Reel Recovery: {r[0]}")

# Fix New Life entries under Judaism
c.execute("SELECT id, name FROM churches WHERE faith='Judaism' AND LOWER(COALESCE(name,'')) LIKE '%new life%'")
for r in c.fetchall():
    c.execute("UPDATE churches SET faith='Christian', tradition='Protestant', landmark_type=NULL, last_updated=datetime('now') WHERE id=?", (r[0],))
    print(f"Fixed New Life: {r[0]} | {str(r[1])[:50]}")

# Fix Foothills Presbytery
c.execute("SELECT id, name FROM churches WHERE LOWER(COALESCE(name,'')) LIKE '%foothills presbytery%'")
for r in c.fetchall():
    c.execute("UPDATE churches SET faith='Christian', tradition='Presbyterian', landmark_type=NULL, last_updated=datetime('now') WHERE id=?", (r[0],))
    print(f"Fixed Foothills Presbytery: {r[0]}")

conn.commit()

# Also scan for "Presbytery" under Judaism
print("\n=== Other 'Presbytery' in Judaism ===")
c.execute("SELECT id, name FROM churches WHERE faith='Judaism' AND LOWER(COALESCE(name,'')) LIKE '%presbytery%'")
for r in c.fetchall():
    c.execute("UPDATE churches SET faith='Christian', tradition='Presbyterian', landmark_type=NULL, last_updated=datetime('now') WHERE id=?", (r[0],))
    print(f"  Fixed: {r[0]} | {str(r[1])[:50]}")

conn.commit()
conn.close()

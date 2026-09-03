"""Find states that still need DeepSeek processing."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# States with entries that have non-Jewish landmark types or no landmark type
c.execute("""
    SELECT state, COUNT(*) as cnt FROM churches
    WHERE faith='Judaism' AND country='US'
    AND (landmark_type IS NULL OR landmark_type = '' 
         OR landmark_type IN ('church','chapel','cathedral','mosque','abbey','shrine'))
    GROUP BY state
    ORDER BY cnt DESC
""")
rows = c.fetchall()
print(f"States needing cleanup: {len(rows)}")
for r in rows:
    print(f"  {r[0] or '?':20s}: {r[1]:,} entries")

total = sum(r[1] for r in rows)
print(f"\nTotal entries needing review: {total:,}")

conn.close()

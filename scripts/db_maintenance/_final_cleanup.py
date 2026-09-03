"""Fix last remaining stragglers worldwide."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Fix temple -> synagogue
c.execute("UPDATE churches SET landmark_type='synagogue' WHERE id=4749653")
print(f"Fixed temple->synagogue: {c.rowcount}")

# Fix community center
c.execute("UPDATE churches SET landmark_type='community_center' WHERE faith='Judaism' AND landmark_type='community center'")
print(f"Fixed community center: {c.rowcount}")

# Fix any remaining problematic entries
c.execute("SELECT id, name, landmark_type FROM churches WHERE faith='Judaism' AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))")
for r in c.fetchall():
    print(f"Problematic: #{r[0]} {r[1]} type={r[2]}")
    c.execute("UPDATE churches SET landmark_type='synagogue' WHERE id=?", (r[0],))
    print(f"  Fixed")

# Final verification
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))")
print(f"\nProblematic entries worldwide: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
il = c.fetchone()[0]
print(f"Worldwide Judaism: {total:,} (Israel: {il:,})")

conn.commit()
conn.close()
print("Done!")

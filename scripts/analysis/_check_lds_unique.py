"""Check what's causing unique constraint violations."""
import sqlite3
conn = sqlite3.connect('churches.db')
c = conn.cursor()

# How many have church_id?
c.execute("SELECT COUNT(*), COUNT(church_id) FROM lds_hierarchy")
total, has_church_id = c.fetchone()
print(f"Total: {total:,}, with church_id: {has_church_id:,}")

# Check for duplicate (church_id, parent_id, relationship) combinations
# Since parent_id and relationship are currently NULL, check church_id duplicates
c.execute("""
    SELECT church_id, COUNT(*) as cnt FROM lds_hierarchy 
    WHERE church_id IS NOT NULL 
    GROUP BY church_id HAVING cnt > 1 
    ORDER BY cnt DESC LIMIT 10
""")
print("\nDuplicate church_id values (non-NULL):")
for row in c.fetchall():
    c2 = conn.cursor()
    c2.execute("SELECT id, lds_type, name FROM lds_hierarchy WHERE church_id=?", (row[0],))
    print(f"  church_id={row[0]} appears {row[1]}x:")
    for r2 in c2.fetchall():
        print(f"    id={r2[0]}, type={r2[1]}, name={r2[2][:50]}")

# Also check how many have church_id=NULL
c.execute("SELECT COUNT(*) FROM lds_hierarchy WHERE church_id IS NULL")
print(f"\nWith church_id=NULL: {c.fetchone()[0]:,}")

# The unique constraint is on (church_id, parent_id, relationship)
# When we UPDATE, we set parent_id and relationship to non-NULL values
# If two rows have church_id=NULL, same parent_id, same relationship
# In SQLite, NULLs ARE distinct in UNIQUE constraints
# So the issue might be with rows that share a church_id

conn.close()

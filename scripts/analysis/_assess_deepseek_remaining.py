"""Assess remaining entries for deepseek Jewish scan."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Show the 83 entries with landmark_type='church'
print("=== Entries with landmark_type='church' ===")
c.execute("""
    SELECT id, name, city, state, tradition, landmark_type
    FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='church'
    ORDER BY state, name
    LIMIT 200
""")
rows = c.fetchall()
for r in rows:
    print(f"  #{r[0]:>8} {str(r[1] or ''):40s} {str(r[2] or ''):20s} {str(r[3] or ''):10s} trad={str(r[4] or ''):15s} type={r[5]}")
print(f"Total church-type: {len(rows)}")

# Show the 3 NULL entries
print("\n=== Entries with landmark_type=NULL ===")
c.execute("""
    SELECT id, name, city, state, tradition, landmark_type
    FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type IS NULL
""")
for r in c.fetchall():
    print(f"  #{r[0]:>8} {str(r[1] or ''):40s} {str(r[2] or ''):20s} {str(r[3] or ''):10s} trad={str(r[4] or ''):15s} type={r[5]}")

# Show entries needing normalization - lowercase variants
print("\n=== Entries needing type normalization ===")
c.execute("""
    SELECT landmark_type, COUNT(*) FROM churches 
    WHERE faith='Judaism' AND country='US' 
    AND landmark_type IN ('community center','chabad','temple','senior home')
    GROUP BY landmark_type
""")
for r in c.fetchall():
    print(f"  '{r[0]}': {r[1]:,} entries")

# Show entries with odd tradition values
print("\n=== Entries with non-standard traditions ===")
c.execute("""
    SELECT tradition, COUNT(*) FROM churches 
    WHERE faith='Judaism' AND country='US'
    AND tradition NOT IN ('Rabbinic','Orthodox (Chabad)','Reform','Orthodox (Yeshiva)','Orthodox',
                          'Orthodox (Hasidic)','Conservative','Reconstructionist','Humanistic',
                          'Sephardic','Orthodox Union','Mizrahi')
    AND tradition != ''
    GROUP BY tradition
    ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  '{r[0]}': {r[1]:,}")

# Also check how many Chabad houses have wrong type
print("\n=== Chabad entries with 'chabad' type (should be chabad_house) ===")
c.execute("""
    SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='chabad'
""")
print(f"  {c.fetchone()[0]} entries")

# Count entries that still could use a scan (non-standard landmark_type)
print("\n=== Summary of fixable issues ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='church'")
print(f"  church type:      {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='community center'")
print(f"  'community center': {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='chabad'")
print(f"  'chabad':         {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='temple'")
print(f"  'temple':         {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='senior home'")
print(f"  'senior home':    {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type IS NULL")
print(f"  NULL:             {c.fetchone()[0]:,}")

conn.close()

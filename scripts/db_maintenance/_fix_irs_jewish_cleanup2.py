"""Finish IRS Jewish cleanup (steps 3-5 from _fix_irs_jewish_nonprofits.py)"""
import sqlite3, datetime
DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total_fixes = 0

# Step 3: Ministries that aren't clearly Jewish → Christian
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christianity', religion_type='christian'
    WHERE country='US' AND faith='Jewish' AND source LIKE 'irs%'
      AND LOWER(name) LIKE '%ministries%'
      AND LOWER(name) NOT LIKE '%jewish%'
      AND LOWER(name) NOT LIKE '%torah%'
      AND LOWER(name) NOT LIKE '%chabad%'
""")
print(f"  'Ministries' → Christian: {c.rowcount}")
total_fixes += c.rowcount

# Step 4: Fellowship orgs → Christian
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christianity', religion_type='christian'
    WHERE country='US' AND faith='Jewish' AND source LIKE 'irs%'
      AND LOWER(name) LIKE '%fellowship%'
      AND LOWER(name) NOT LIKE '%jewish%'
      AND LOWER(name) NOT LIKE '%hebrew%'
""")
print(f"  'Fellowship' → Christian: {c.rowcount}")
total_fixes += c.rowcount

conn.commit()

# Step 5: Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_fix_irs_jewish_cleanup2.py', TS, TS,
      total_fixes, 0, 'faith,faith_tradition,religion_type', 'completed',
      f'Additional {total_fixes} IRS cleanup: ministries/fellowship → Christian'))

conn.commit()

# Summary
print(f"\nFinal fixes this run: {total_fixes}")
print("\nIRS Jewish records — religion_type breakdown:")
c.execute("""
    SELECT religion_type, COUNT(*) FROM churches 
    WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish'
    GROUP BY religion_type ORDER BY COUNT(*) DESC
""")
for rt, cnt in c.fetchall():
    print(f"  {str(rt):<20} {cnt:>6,}")

print("\nGlobal Jewish faith — top countries:")
c.execute("""
    SELECT country, COUNT(*) FROM churches WHERE faith='Jewish'
    GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10
""")
for country, cnt in c.fetchall():
    print(f"  {country:<6} {cnt:>6,}")

conn.close()
print("\nDone!")

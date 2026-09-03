"""Quick: list remaining New Age records and fix community center false positives."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

# Show remaining New Age-tagged
c.execute("SELECT name, city, state FROM churches WHERE country='US' AND faith='Other' AND religion_type='new_age' ORDER BY name")
rows = c.fetchall()
print(f"New Age records: {len(rows)}")
for name, city, state in rows:
    cname = str(name)[:60] if name else ''
    ccity = str(city or '')[:15]
    cstate = str(state or '')[:4]
    print(f"  {cname:<60} | {ccity:<15} | {cstate}")

# Fix community centers caught by unity substring
c.execute("""UPDATE churches SET faith='Jewish', religion_type='unknown'
WHERE country='US' AND source LIKE 'irs%' AND faith='Other' AND religion_type='new_age'
AND LOWER(name) LIKE '%community center%'""")
print(f"\nReverted community centers (broad): {c.rowcount}")
conn.commit()
conn.close()

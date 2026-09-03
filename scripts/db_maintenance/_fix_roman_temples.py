"""Fix two Roman temple archaeological sites: Temple of Janus (FR) and Temple of Hercules (DE)."""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

sites = [
    ('Temple of Janus', 'FR', 'Roman'),
    ('Temple of Hercules', 'DE', 'Roman'),
]

for name, country, tradition in sites:
    c.execute("""
        UPDATE churches
        SET faith = 'Other', faith_tradition = ?
        WHERE name LIKE ? AND country = ? AND (faith IS NULL OR faith != 'Other' OR faith_tradition != ?)
    """, (tradition, f'%{name}%', country, tradition))
    n = c.rowcount
    print(f"{name} ({country}): {n} row(s) updated → faith=Other, faith_tradition={tradition}")

conn.commit()

# Log provenance for any rows that have an id
c.execute("""
    SELECT id, name FROM churches
    WHERE (name LIKE '%Temple of Janus%' OR name LIKE '%Temple of Hercules%')
      AND country IN ('FR', 'DE')
""")
from datetime import datetime
ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
for r in c.fetchall():
    c.execute("""
        INSERT INTO provenance_log (church_id, source, action, timestamp, details)
        VALUES (?, ?, 'updated', ?, ?)
    """, (r[0], 'roman_temple_fix', ts, f'faith: Hindu->Other, faith_tradition: Hinduism->Roman ({r[1]})'))
conn.commit()

print("✓ Provenance logged")

# Verify
c.execute("""
    SELECT name, faith, faith_tradition, country FROM churches
    WHERE (name LIKE '%Temple of Janus%' OR name LIKE '%Temple of Hercules%')
      AND country IN ('FR', 'DE')
""")
print("\nVerification:")
for r in c.fetchall():
    print(f"  {str(r[0] or ''):50s} | {r[1]:10s} | {r[2]:15s} | {r[3]}")

conn.close()

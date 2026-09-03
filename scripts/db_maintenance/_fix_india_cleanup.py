"""Final edge-case faith fixes for India."""
import sqlite3, datetime
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
ts = datetime.datetime.now().isoformat()
fixes = 0

# Gurudwaras tagged Christian
c.execute("UPDATE churches SET faith='Sikh',faith_tradition='Sikhism' WHERE country='IN' AND faith='Christian' AND (LOWER(name) LIKE '%gurudwara%' OR LOWER(name) LIKE '%gurdwara%' OR LOWER(name) LIKE '%harmandir%')")
print(f'Sikh fixes: {c.rowcount}'); fixes += c.rowcount

# Masjids tagged Christian
c.execute("UPDATE churches SET faith='Islam',faith_tradition='Islam' WHERE country='IN' AND faith='Christian' AND LOWER(name) LIKE '%masjid%'")
print(f'Islam fixes: {c.rowcount}'); fixes += c.rowcount

# Temple of Vedic Planetarium (ISKCON) → Hindu
c.execute("UPDATE churches SET faith='Hindu',faith_tradition='Hinduism' WHERE country='IN' AND LOWER(name) LIKE '%vedic planetarium%'")
print(f'Hindu fixes: {c.rowcount}'); fixes += c.rowcount

c.execute("INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_updated,churches_inserted,fields_populated,status,notes) VALUES(?,?,?,?,?,?,?,?,?)",
    ('manual','_fix_india_cleanup.py',ts,ts,fixes,0,'faith,faith_tradition','completed',f'Final cleanup: {fixes} edge-case fixes'))
conn.commit()
print(f'Total: {fixes}')
conn.close()

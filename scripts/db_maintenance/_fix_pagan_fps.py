"""Fix Pagan false positives."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
fixes = 0

# Hellenic Orthodox = Greek Christian, NOT pagan
c.execute("""UPDATE churches SET faith=NULL, religion_type=NULL
WHERE faith='Pagan' AND LOWER(name) LIKE '%hellenic orthodox%'""")
print(f'Hellenic Orthodox reverted: {c.rowcount}'); fixes += c.rowcount

# Reconstructionist congregations = Jewish
c.execute("""UPDATE churches SET faith='Jewish', religion_type='jewish'
WHERE faith='Pagan' AND (LOWER(name) LIKE '%reconstructionist congregation%'
  OR LOWER(name) LIKE '%reconstructionist havurah%'
  OR LOWER(name) LIKE '%bnai%reconstructionist%' OR LOWER(name) LIKE '%b nai%reconstructionist%')""")
print(f'Reconstructionist Jewish: {c.rowcount}'); fixes += c.rowcount

# Druid Hills = neighborhood, not religion
c.execute("""UPDATE churches SET faith=NULL, religion_type=NULL
WHERE faith='Pagan' AND LOWER(name) LIKE '%druid hills%'""")
print(f'Druid Hills: {c.rowcount}'); fixes += c.rowcount

# Odin church that is Christian
c.execute("""UPDATE churches SET faith='Christian', religion_type='christian'
WHERE faith='Pagan' AND LOWER(name) LIKE '%odin%'
  AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%christian%')
  AND LOWER(name) NOT LIKE '%odinism%' AND LOWER(name) NOT LIKE '%asatru%'""")
print(f'Odin church → Christian: {c.rowcount}'); fixes += c.rowcount

# 'switch' matching 'witch'
c.execute("""UPDATE churches SET faith=NULL, religion_type=NULL
WHERE faith='Pagan' AND LOWER(name) LIKE '%switch%'
  AND LOWER(name) NOT LIKE '%witchcraft%' AND LOWER(name) NOT LIKE '%wicca%'""")
print(f'Switch: {c.rowcount}'); fixes += c.rowcount

# jedna rodina = Czech "one family" (matched %odin%)
c.execute("""UPDATE churches SET faith=NULL, religion_type=NULL
WHERE faith='Pagan' AND LOWER(name) LIKE '%jedna rodina%'""")
print(f'Jedna rodina: {c.rowcount}'); fixes += c.rowcount

# General: Pagan-tagged with church/parish → Christian
c.execute("""UPDATE churches SET faith='Christian', religion_type='christian'
WHERE faith='Pagan' AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%parish%'
  OR LOWER(name) LIKE '%orthodox%')
  AND LOWER(name) NOT LIKE '%pagan church%' AND LOWER(name) NOT LIKE '%wicca%'
  AND LOWER(name) NOT LIKE '%witch%' AND LOWER(name) NOT LIKE '%druid%'""")
print(f'General church→Christian: {c.rowcount}'); fixes += c.rowcount

conn.commit()
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Pagan'")
print(f'\nRemaining Pagan: {c.fetchone()[0]}')
conn.close()
print(f'Total reverts: {fixes}')

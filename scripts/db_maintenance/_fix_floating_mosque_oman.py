"""
Fix: Move floating mosque from Indian Ocean to Oman (latitude sign error)

Rowid=1271221 — "Sayyedena Abu Bakr Siddique (R.A) Masjid"
- Current: lat=-20.632784, lon=56.25, country=MU (Mauritius)
  → Open ocean, 130 km from nearest land
- Fixed:   lat= 20.632784, lon=56.25, country=OM (Oman)
  → Central Oman, Arabian Peninsula (Middle East)

Root cause: holy_sites_import had latitude sign flipped (South instead of North).
Longitude was correct (56.25°E runs through central Oman).
"""

import sqlite3
from datetime import datetime

DB = 'E:/grid/churches.db'
ROWID = 1271221
NOW = datetime.utcnow().isoformat()

# Before values
old_lat = -20.632784
old_lon = 56.25
old_country = 'MU'

# After values
new_lat = 20.632784
new_lon = 56.25
new_country = 'OM'

db = sqlite3.connect(DB)
cur = db.cursor()

# --- 1. Verify current state ---
cur.execute('SELECT name, latitude, longitude, country, source FROM churches WHERE rowid = ?', (ROWID,))
row = cur.fetchone()
if not row:
    print(f"ERROR: rowid {ROWID} not found!")
    db.close()
    exit(1)

name, lat, lon, country, source = row
print(f"Current: rowid={ROWID} | {name} | lat={lat} | lon={lon} | country={country} | source={source}")

if lat != old_lat or country != old_country:
    print(f"WARNING: Current values don't match expected! Expected lat={old_lat} country={old_country}")
    proceed = input("Proceed anyway? (y/N): ")
    if proceed.lower() != 'y':
        print("Aborted.")
        db.close()
        exit(0)

# --- 2. Record provenance_log entry ---
prov_cursor = cur.execute('''
    INSERT INTO provenance_log 
        (source, script_name, started_at, completed_at, churches_updated, 
         churches_inserted, fields_populated, parameters, records_attempted,
         records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    'manual_fix',
    '_fix_floating_mosque_oman.py',
    NOW, NOW, 1, 0,
    'latitude,country',
    '{"rowid":1271221,"old_lat":-20.632784,"new_lat":20.632784,"old_country":"MU","new_country":"OM"}',
    1, 1, 'completed',
    f'Fixed latitude sign for "{name}" — was -20.63°S (Indian Ocean), corrected to +20.63°N (Oman, Arabian Peninsula). Longitude 56.25°E unchanged. Country MU→OM.'
))
prov_id = prov_cursor.lastrowid
print(f"Provenance logged: id={prov_id}")

# --- 3. Update churches table ---
cur.execute('UPDATE churches SET latitude = ?, country = ? WHERE rowid = ?',
            (new_lat, new_country, ROWID))
print(f"Updated churches: lat {old_lat} → {new_lat}, country {old_country} → {new_country}")

# --- 4. Log enrichment_change_log entries ---
# Latitude change
cur.execute('''
    INSERT INTO enrichment_change_log 
        (church_id, field_name, old_value, new_value, change_source)
    VALUES (?, ?, ?, ?, ?)
''', (ROWID, 'latitude', str(old_lat), str(new_lat), '_fix_floating_mosque_oman.py'))

# Country change
cur.execute('''
    INSERT INTO enrichment_change_log 
        (church_id, field_name, old_value, new_value, change_source)
    VALUES (?, ?, ?, ?, ?)
''', (ROWID, 'country', old_country, new_country, '_fix_floating_mosque_oman.py'))

# Also log longitude (even though unchanged) for completeness
cur.execute('''
    INSERT INTO enrichment_change_log 
        (church_id, field_name, old_value, new_value, change_source)
    VALUES (?, ?, ?, ?, ?)
''', (ROWID, 'longitude', str(old_lon), str(new_lon), '_fix_floating_mosque_oman.py'))

print("Enrichment change log: 3 entries written")

# --- 5. Commit and verify ---
db.commit()

cur.execute('SELECT name, latitude, longitude, country FROM churches WHERE rowid = ?', (ROWID,))
row = cur.fetchone()
print(f"\nVerified: rowid={ROWID} | {row[0]} | lat={row[1]} | lon={row[2]} | country={row[3]}")

# Quick reverse-geocode check
if 20 < row[1] < 21 and 55 < row[2] < 57:
    print("✅ Coordinates fall within Oman (20-21°N, 55-57°E)")
else:
    print(f"⚠️ Coordinates may need review: lat={row[1]}, lon={row[2]}")

db.close()
print("\nDone!")

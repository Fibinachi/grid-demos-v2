"""Fix LDS classification for all three churches
Also fix the DELIVERANCE TEMPLE in San Antonio that looks misclassified as LDS.

User said: "make sure the buildings are attached the right mormons"
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
try:
    from gw_db import get_db
    db = get_db()
    provenance = True
except ImportError:
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), "churches.db"))
    provenance = False

c = db.cursor()

def fix_church(church_id, tradition_val, legacy_val, taxonomy_id, denomination_val=None, 
               city_fix=None, details_extra=""):
    """Update a church's LDS classification with provenance logging."""
    updates = []
    params = []
    
    if tradition_val:
        updates.append("tradition = ?")
        params.append(tradition_val)
    if legacy_val is not None:
        updates.append("legacy = ?")
        params.append(legacy_val)
    if taxonomy_id:
        updates.append("taxonomy_id = ?")
        params.append(taxonomy_id)
    if denomination_val:
        updates.append("denomination = ?")
        params.append(denomination_val)
    if city_fix:
        updates.append("city = ?")
        params.append(city_fix)
    
    if not updates:
        return
    
    params.append(church_id)
    c.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id = ?", tuple(params))
    
    if provenance and c.rowcount > 0:
        detail_parts = []
        if tradition_val:
            detail_parts.append(f"tradition->{tradition_val}")
        if legacy_val is not None:
            detail_parts.append(f"legacy->{legacy_val}")
        if taxonomy_id:
            c.execute("SELECT name FROM taxonomy WHERE id = ?", (taxonomy_id,))
            t = c.fetchone()
            tname = f" ({t[0]})" if t else ""
            detail_parts.append(f"taxonomy_id->{taxonomy_id}{tname}")
        if denomination_val:
            detail_parts.append(f"denomination->{denomination_val}")
        if city_fix:
            detail_parts.append(f"city->{city_fix}")
        if details_extra:
            detail_parts.append(details_extra)
            
        c.execute("""
            INSERT INTO provenance_log (church_id, source, action, details)
            VALUES (?, 'manual', 'updated', ?)
        """, (church_id, '; '.join(detail_parts)))
    
    return c.rowcount

# ====== 1. Community Of Jesus Christ-Lds (ID 463015) ======
print("=== 1. Community Of Jesus Christ-Lds (ID 463015) ===")
c.execute("SELECT id, name, tradition, legacy, taxonomy_id, city, state FROM churches WHERE id = 463015")
r = c.fetchone()
print(f"  Before: tradition={r[2]}, legacy={r[3]}, taxonomy_id={r[4]}")
rc = fix_church(463015, 'lds', 'Other LDS', 167, 'Community of Christ')
print(f"  Fixed: {rc} rows affected")

# ====== 2. WORLDS CROSSING INC (ID 256577) ======
print("\n=== 2. WORLDS CROSSING INC (ID 256577) ===")
c.execute("SELECT id, name, tradition, legacy, taxonomy_id, city, state, zip FROM churches WHERE id = 256577")
r = c.fetchone()
print(f"  Before: tradition={r[2]}, legacy={r[3]}, taxonomy_id={r[4]}, city={r[5]}")
# City should be Godley based on zip 76044 being Godley, TX
rc = fix_church(256577, 'lds', 'Other LDS', 167, 'Community of Christ', 
                city_fix='Godley',
                details_extra='city corrected from Nakhon Nayok to Godley')
print(f"  Fixed: {rc} rows affected")

# ====== 3. Church of Jesus Christ of Latter-day Saints (San Antonio, TX null-ID) ======
print("\n=== 3. LDS churches in San Antonio, TX (null-ID records) ===")
# Find the null-ID records by matching name and location
c.execute("""
    SELECT rowid, id, name, address, city, state, latitude, longitude
    FROM churches
    WHERE id IS NULL
      AND name = 'Church of Jesus Christ of Latter-day Saints'
      AND state = 'TX'
""")
lds_records = c.fetchall()
print(f"  Found {len(lds_records)} null-ID records")

for row in lds_records:
    rowid = row[0]
    addr = row[3]
    lat = row[6]
    lon = row[7]
    print(f"  Updating rowid={rowid}: {addr} ({lat}, {lon})")
    # Can't update by id since id is null, update by rowid
    c.execute("""
        UPDATE churches SET tradition = 'lds', legacy = 'Other LDS', 
               taxonomy_id = 172, denomination = 'The Church of Jesus Christ of Latter-day Saints'
        WHERE rowid = ?
    """, (rowid,))
    print(f"    Affected: {c.rowcount}")

# ====== 4. Also check DELIVERANCE TEMPLE APOSTOLIC CHURCH OF JESUS CHRIST ======
print("\n=== 4. Checking DELIVERANCE TEMPLE (ID 359555) ===")
c.execute("SELECT id, name, tradition, legacy, taxonomy_id, city, state, landmark_type FROM churches WHERE id = 359555")
r = c.fetchone()
if r:
    print(f"  {r[1]} — tradition={r[2]}, legacy={r[3]}, taxonomy_id={r[4]}, landmark_type={r[7]}")
    print(f"  This 'Apostolic' church is likely misclassified as LDS (same pattern as Temple of Praise)")
    # 'Apostolic' in name usually means Oneness Pentecostal, not LDS
    fix_church(359555, 'pentecostal', '', 218, 'Apostolic Pentecostal',
               details_extra='misclassified as LDS; Apostolic = Oneness Pentecostal')
    print(f"  Fixed to pentecostal")

db.commit()

# Verify
print("\n=== VERIFICATION ===")
for church_id in [463015, 256577, 359555]:
    c.execute("SELECT id, name, tradition, legacy, taxonomy_id FROM churches WHERE id = ?", (church_id,))
    r = c.fetchone()
    c.execute("SELECT name, full_path FROM taxonomy WHERE id = ?", (r[4],))
    t = c.fetchone()
    print(f"  ID {r[0]}: {r[1][:50]}...")
    print(f"    tradition={r[2]}, legacy={r[3]}, taxonomy={t[0] if t else '?'}")

print(f"\nProvenance logged: {provenance}")
db.close()
print("\nDone!")

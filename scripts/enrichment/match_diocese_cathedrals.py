"""
Match diocese/archdiocese nodes to GRID churches by name to get GPS coordinates.
Strategy: For each diocese node without GPS, find a church whose name contains
the diocese city (e.g., "Archdiocese of Jakarta" → church in Jakarta with "cathedral" in name).
"""
import sqlite3
import re

DB = "E:/grid/churches.db"
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# ── Get dioceses without GPS ──
print("Finding dioceses without GPS...")
dioceses = db.execute("""
    SELECT id, name, cath_type, country, city
    FROM catholic_hierarchy
    WHERE cath_type IN ('diocese','archdiocese')
      AND (lat IS NULL OR lat = 0)
    ORDER BY country, name
""").fetchall()
print(f"Dioceses without GPS: {len(dioceses)}")

# ── For each diocese, find matching cathedral/church in GRID ──
updated = 0
no_match = 0

for dio in dioceses:
    # Extract city name from diocese name
    # "Archdiocese of Jakarta" → "Jakarta"
    # "Diocese of Bandung" → "Bandung"
    name = dio["name"]
    m = re.search(r'(?:Archdiocese|Diocese|Eparchy|Vicariate)\s+of\s+(.+?)$', name, re.IGNORECASE)
    if not m:
        m = re.search(r'of\s+(.+?)$', name, re.IGNORECASE)
    
    if not m:
        no_match += 1
        continue
    
    city_part = m.group(1).strip()
    # Remove parenthetical suffixes like "Archdiocese of Ende (Indonesia)"
    city_part = re.sub(r'\s*\(.*?\)\s*$', '', city_part)
    
    # Try to find a cathedral church in this country+city
    # Strategy 1: church name contains "Cathedral" and city_part, same country
    match = db.execute("""
        SELECT id, name, city, latitude, longitude
        FROM churches
        WHERE country = ?
          AND name LIKE '%Cathedral%'
          AND (city = ? OR name LIKE ?)
          AND latitude IS NOT NULL
        LIMIT 1
    """, (dio["country"], city_part, f'%{city_part}%')).fetchone()
    
    # Strategy 2: church name contains city_part and "Catholic", same country
    if not match:
        match = db.execute("""
            SELECT id, name, city, latitude, longitude
            FROM churches
            WHERE country = ?
              AND name LIKE '%Catholic%'
              AND (city = ? OR name LIKE ?)
              AND latitude IS NOT NULL
            LIMIT 1
        """, (dio["country"], city_part, f'%{city_part}%')).fetchone()
    
    # Strategy 3: any church with city_part as city, same country, prefer Catholic taxonomy
    if not match:
        match = db.execute("""
            SELECT id, name, city, latitude, longitude
            FROM churches
            WHERE country = ?
              AND city = ?
              AND taxonomy_id IN (14,86,92,100)
              AND latitude IS NOT NULL
            LIMIT 1
        """, (dio["country"], city_part)).fetchone()
    
    if not match:
        # Strategy 4: broader - any church with city_part in name, same country
        match = db.execute("""
            SELECT id, name, city, latitude, longitude
            FROM churches
            WHERE country = ?
              AND name LIKE ?
              AND latitude IS NOT NULL
            LIMIT 1
        """, (dio["country"], f'%{city_part}%')).fetchone()
    
    if match:
        db.execute("""
            UPDATE catholic_hierarchy 
            SET lat=?, lon=?, city=?, church_id=?, notes=COALESCE(notes || '; ','') || ?
            WHERE id=?
        """, (
            match["latitude"], match["longitude"],
            match["city"], match["id"],
            f"Cathedral matched: {match['name']} via name match",
            dio["id"]
        ))
        updated += 1
        if updated <= 20 or updated % 100 == 0:
            print(f"  ✅ {dio['name'][:45]} → {match['name'][:40]} ({match['city']}, {dio['country']})")
    else:
        no_match += 1
        if no_match <= 10:
            print(f"  ❌ {dio['name'][:45]} | city_part='{city_part}' | country={dio['country']}")

db.commit()

print(f"\n=== RESULTS ===")
print(f"GPS assigned: {updated}")
print(f"No match: {no_match}")
print(f"Total without GPS: {len(dioceses)}")

# Now count bishop seats with GPS
r = db.execute("""
    SELECT COUNT(1) FROM catholic_hierarchy
    WHERE cath_type IN ('diocese','archdiocese')
      AND lat IS NOT NULL AND lat != 0
""").fetchone()
print(f"Dioceses WITH GPS now: {r[0]}")

db.close()

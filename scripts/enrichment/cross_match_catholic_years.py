#!/usr/bin/env python3
"""Geocode 2021 Catholic Directory entries via city centroids, then cross-match 1868->2021."""
import sqlite3
from pathlib import Path

DIR_DB = Path("E:/grid/data/catholic_directory.db")
GRID_DB = Path("E:/grid/churches.db")
CHUNK_SIZE = 500

def ensure_columns():
    db = sqlite3.connect(str(DIR_DB))
    for col in ['latitude', 'longitude', 'geocode_source', 'grid_church_rowid', 'geocode_confidence']:
        try: db.execute(f"ALTER TABLE dir_entries ADD COLUMN {col} REAL" if 'REAL' in 'REAL' else f"ALTER TABLE dir_entries ADD COLUMN {col} TEXT")
        except: pass
    db.commit()
    db.close()

# ── Phase 1: Geocode 2021 by city centroid ──
print("=" * 60)
print("Phase 1: Geocode 2021 entries via city centroids")
print("=" * 60)

dir_db = sqlite3.connect(str(DIR_DB))
dir_db.row_factory = sqlite3.Row

# Get unique city+state pairs from 2021
pairs = dir_db.execute("""
    SELECT DISTINCT city, state FROM dir_entries
    WHERE directory_year=2021 AND city IS NOT NULL AND state IS NOT NULL
    AND latitude IS NULL
""").fetchall()
print(f"  {len(pairs):,} unique (city, state) pairs")

# Load US city centroids from GRID
grid = sqlite3.connect(str(GRID_DB))
print("  Loading city centroids from GRID...")
centroids = {}
for row in grid.execute("""
    SELECT UPPER(city), UPPER(state), AVG(latitude), AVG(longitude), COUNT(*)
    FROM churches WHERE country='US'
    AND latitude IS NOT NULL AND longitude IS NOT NULL AND latitude != 0
    AND city IS NOT NULL AND state IS NOT NULL
    GROUP BY UPPER(city), UPPER(state)
"""):
    if row[2] and row[3]:
        centroids[(row[0], row[1])] = (round(row[2], 6), round(row[3], 6))
grid.close()
print(f"  Loaded {len(centroids):,} US city centroids")

# Match and batch-update
updates = []
resolved = 0
for pair in pairs:
    city, state = pair['city'], pair['state']
    if not city or not state: continue
    key = (city.upper().strip(), state.upper().strip())
    if key in centroids:
        lat, lon = centroids[key]
        updates.append((lat, lon, city, state))
        resolved += 1

for i in range(0, len(updates), CHUNK_SIZE):
    chunk = updates[i:i+CHUNK_SIZE]
    dir_db.executemany("""
        UPDATE dir_entries SET latitude=?, longitude=?,
        geocode_source='grid_city_centroid', geocode_confidence=0.7
        WHERE directory_year=2021 AND city=? AND state=? AND latitude IS NULL
    """, chunk)
dir_db.commit()

geo_count = dir_db.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=2021 AND latitude IS NOT NULL").fetchone()[0]
print(f"  Resolved {resolved:,}/{len(pairs):,} city pairs")
print(f"  Geocoded {geo_count:,} entries")

# ── Phase 2: Cross-match 1868 parishes to 2021 ──
print("\n" + "=" * 60)
print("Phase 2: Match 1868 parishes to 2021 parishes")
print("=" * 60)

# Get 1868 and 2021 entries with coords
e1868 = dir_db.execute("""
    SELECT id, name, city, state, latitude, longitude, entity_type
    FROM dir_entries WHERE directory_year=1868
    AND latitude IS NOT NULL AND entity_type IN ('parish','cathedral','mission','chapel')
""").fetchall()

e2021 = dir_db.execute("""
    SELECT id, name, city, state, latitude, longitude, entity_type
    FROM dir_entries WHERE directory_year=2021
    AND latitude IS NOT NULL AND entity_type IN ('parish','cathedral','mission','chapel')
""").fetchall()

print(f"  1868 worship sites with coords: {len(e1868):,}")
print(f"  2021 worship sites with coords: {len(e2021):,}")

# Build 2021 lookup by (city, state)
from collections import defaultdict
import re

lookup_2021 = defaultdict(list)
for e in e2021:
    key = ((e['city'] or '').upper().strip(), (e['state'] or '').upper().strip())
    lookup_2021[key].append(e)

def clean_name(n):
    if not n: return ''
    n = n.lower().strip()
    for w in ['church', 'chapel', 'cathedral', 'saint', 'st.', 'st ', 'catholic',
               'roman', 'parish', 'mission', 'of', 'the', 'and', "'s", "school",
               "academy", "college", "seminary", "convent", "hospital", "orphan"]:
        n = n.replace(w, '')
    return re.sub(r'\s+', ' ', n).strip()

matches = []
for e in e1868:
    ekey = ((e['city'] or '').upper().strip(), (e['state'] or '').upper().strip())
    if ekey not in lookup_2021: continue
    
    ename_clean = clean_name(e['name'])
    if not ename_clean or len(ename_clean) < 3: continue
    
    best, best_score = None, 0
    for e2 in lookup_2021[ekey]:
        cname = clean_name(e2['name'])
        if not cname or len(cname) < 3: continue
        
        # Score: word overlap
        ew = set(ename_clean.split())
        cw = set(cname.split())
        common = ew & cw
        if not common: continue
        
        score = len(common) * 30
        if ename_clean == cname: score = 100
        if len(common) == len(ew) and len(common) == len(cw): score = 95
        
        if score > best_score:
            best_score = score
            best = e2
    
    if best and best_score >= 60:
        matches.append((best['latitude'], best['longitude'], best['id'], e['id']))

print(f"  Matched: {len(matches):,} 1868 entries to 2021 entries")

# Write cross-reference and update 1868 coordinates from 2021
if matches:
    # Create cross-reference table
    dir_db.execute("""
        CREATE TABLE IF NOT EXISTS dir_cross_year (
            year_from INTEGER, entry_from_id INTEGER,
            year_to INTEGER, entry_to_id INTEGER,
            match_score REAL, match_type TEXT
        )
    """)
    
    for i in range(0, len(matches), CHUNK_SIZE):
        chunk = matches[i:i+CHUNK_SIZE]
        # Update 1868 coords from matched 2021 entry
        dir_db.executemany("""
            UPDATE dir_entries SET latitude=?, longitude=?,
            geocode_source='2021_cross_match', geocode_confidence=0.75
            WHERE id=?
        """, [(lat, lon, eid) for lat, lon, e2021_id, eid in chunk])
        
        # Record cross-reference
        dir_db.executemany("""
            INSERT OR IGNORE INTO dir_cross_year (year_from, entry_from_id, year_to, entry_to_id, match_score, match_type)
            VALUES (1868, ?, 2021, ?, 75, 'name_city')
        """, [(eid, e2021_id) for _, _, e2021_id, eid in chunk])
    
    dir_db.commit()

# ── Summary ──
print("\n" + "=" * 60)
print("Final Summary")
print("=" * 60)
for yr in [1865, 1868, 2021]:
    t = dir_db.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=?", (yr,)).fetchone()[0]
    g = dir_db.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=? AND latitude IS NOT NULL", (yr,)).fetchone()[0]
    m = dir_db.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=? AND grid_church_rowid IS NOT NULL", (yr,)).fetchone()[0]
    print(f"  {yr}: {t:>6,} total  |  geocoded {g:>6,} ({g/t*100:.0f}%)  |  GRID-matched {m:>6,}")

# Cross-match stats
x = dir_db.execute("SELECT COUNT(*) FROM dir_cross_year WHERE year_from=1868 AND year_to=2021").fetchone()[0]
print(f"\n  1868->2021 cross-matches: {x:,}")

# Show a few surviving parishes
print("\nSample surviving parishes (1868 -> 2021):")
for r in dir_db.execute("""
    SELECT d1.name as name1868, d1.city, d1.state,
           d2.name as name2021
    FROM dir_cross_year x
    JOIN dir_entries d1 ON x.entry_from_id = d1.id
    JOIN dir_entries d2 ON x.entry_to_id = d2.id
    WHERE x.year_from=1868 AND x.year_to=2021
    LIMIT 12
"""):
    print(f'  {r[0][:35]:35s} -> {r[3][:35]}   ({r[1]}, {r[2]})')

dir_db.close()
print("\nDone.")

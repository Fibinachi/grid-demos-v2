#!/usr/bin/env python3
"""Geocode 1865 and cross-match all three years (1865, 1868, 2021)."""
import sqlite3, re
from pathlib import Path
from collections import defaultdict

DIR_DB = Path("E:/grid/data/catholic_directory.db")
GRID_DB = Path("E:/grid/churches.db")
CHUNK = 500

dir_db = sqlite3.connect(str(DIR_DB))
dir_db.row_factory = sqlite3.Row

# ── Phase 1: Geocode 1865 by city centroid ──
print("=" * 60)
print("Phase 1: Geocode 1865 via city centroids")
print("=" * 60)

pairs = dir_db.execute("""
    SELECT DISTINCT city, state FROM dir_entries
    WHERE directory_year=1865 AND city IS NOT NULL AND state IS NOT NULL
    AND latitude IS NULL
""").fetchall()
print(f"  {len(pairs):,} unique (city, state) pairs")

grid = sqlite3.connect(str(GRID_DB))
centroids = {}
for row in grid.execute("""
    SELECT UPPER(city), UPPER(state), AVG(latitude), AVG(longitude)
    FROM churches WHERE country='US'
    AND latitude IS NOT NULL AND longitude IS NOT NULL AND latitude != 0
    AND city IS NOT NULL AND state IS NOT NULL
    GROUP BY UPPER(city), UPPER(state)
"""):
    if row[2] and row[3]:
        centroids[(row[0], row[1])] = (round(row[2], 6), round(row[3], 6))
grid.close()
print(f"  Loaded {len(centroids):,} US city centroids")

updates, resolved = [], 0
for pair in pairs:
    city, state = pair['city'], pair['state']
    if not city or not state: continue
    key = (city.upper().strip(), state.upper().strip())
    if key in centroids:
        updates.append((*centroids[key], city, state))
        resolved += 1

for i in range(0, len(updates), CHUNK):
    dir_db.executemany("""
        UPDATE dir_entries SET latitude=?, longitude=?,
        geocode_source='grid_city_centroid', geocode_confidence=0.7
        WHERE directory_year=1865 AND city=? AND state=? AND latitude IS NULL
    """, updates[i:i+CHUNK])
dir_db.commit()

geo1865 = dir_db.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=1865 AND latitude IS NOT NULL").fetchone()[0]
print(f"  Resolved {resolved:,}/{len(pairs):,} city pairs -> {geo1865:,} entries geocoded")

# ── Phase 2: Cross-match 1865 -> 2021 ──
print("\n" + "=" * 60)
print("Phase 2: Match 1865 parishes to 2021")
print("=" * 60)

def clean_name(n):
    if not n: return ''
    n = n.lower().strip()
    for w in ['church', 'chapel', 'cathedral', 'saint', 'st.', 'st ', 'catholic',
               'roman', 'parish', 'mission', 'of', 'the', 'and', "'s", "school",
               "academy", "college", "seminary", "convent", "hospital", "orphan",
               "boys", "girls", "asylum"]:
        n = n.replace(w, '')
    return re.sub(r'\s+', ' ', n).strip()

def cross_match(year_from, year_to):
    e_from = dir_db.execute(f"""
        SELECT id, name, city, state, latitude, longitude, entity_type
        FROM dir_entries WHERE directory_year={year_from}
        AND latitude IS NOT NULL AND entity_type IN ('parish','cathedral','mission','chapel')
    """).fetchall()

    e_to = dir_db.execute(f"""
        SELECT id, name, city, state, latitude, longitude, entity_type
        FROM dir_entries WHERE directory_year={year_to}
        AND latitude IS NOT NULL AND entity_type IN ('parish','cathedral','mission','chapel')
    """).fetchall()

    # Build lookup by city+state
    lookup = defaultdict(list)
    for e in e_to:
        lookup[((e['city'] or '').upper().strip(), (e['state'] or '').upper().strip())].append(e)

    matches = []
    for e in e_from:
        ekey = ((e['city'] or '').upper().strip(), (e['state'] or '').upper().strip())
        if ekey not in lookup: continue
        ename = clean_name(e['name'])
        if not ename or len(ename) < 3: continue

        best, best_score = None, 0
        for e2 in lookup[ekey]:
            cname = clean_name(e2['name'])
            if not cname or len(cname) < 3: continue
            ew, cw = set(ename.split()), set(cname.split())
            common = ew & cw
            if not common: continue
            score = len(common) * 30
            if ename == cname: score = 100
            if score > best_score:
                best_score = score
                best = e2

        if best and best_score >= 60:
            matches.append((best['latitude'], best['longitude'], best['id'], e['id']))

    if matches:
        for i in range(0, len(matches), CHUNK):
            chunk = matches[i:i+CHUNK]
            dir_db.executemany(f"""
                UPDATE dir_entries SET latitude=?, longitude=?,
                geocode_source='{year_to}_cross_match', geocode_confidence=0.75
                WHERE id=?
            """, [(lat, lon, eid) for lat, lon, _, eid in chunk])
            dir_db.executemany("""
                INSERT OR IGNORE INTO dir_cross_year (year_from, entry_from_id, year_to, entry_to_id, match_score, match_type)
                VALUES (?, ?, ?, ?, 75, 'name_city')
            """, [(year_from, eid, year_to, e2id) for _, _, e2id, eid in chunk])
        dir_db.commit()

    return len(matches)

m1865_2021 = cross_match(1865, 2021)
print(f"  1865->2021: {m1865_2021:,} matched")

# ── Phase 3: Cross-match 1865 -> 1868 ──
print("\n" + "=" * 60)
print("Phase 3: Match 1865 parishes to 1868")
print("=" * 60)
m1865_1868 = cross_match(1865, 1868)
print(f"  1865->1868: {m1865_1868:,} matched")

# ── Final Summary ──
print("\n" + "=" * 60)
print("Full 3-Year Catholic Directory Pipeline")
print("=" * 60)
for yr in [1865, 1868, 2021]:
    t = dir_db.execute(f"SELECT COUNT(*) FROM dir_entries WHERE directory_year={yr}").fetchone()[0]
    g = dir_db.execute(f"SELECT COUNT(*) FROM dir_entries WHERE directory_year={yr} AND latitude IS NOT NULL").fetchone()[0]
    gr = dir_db.execute(f"SELECT COUNT(*) FROM dir_entries WHERE directory_year={yr} AND grid_church_rowid IS NOT NULL").fetchone()[0]
    print(f"  {yr}: {t:>6,} total  |  geocoded {g:>6,} ({g/t*100:.0f}%)  |  GRID-matched {gr:>6,}")

print("\nCross-year links:")
for fy, ty in [(1865, 1868), (1865, 2021), (1868, 2021)]:
    c = dir_db.execute("SELECT COUNT(*) FROM dir_cross_year WHERE year_from=? AND year_to=?", (fy, ty)).fetchone()[0]
    print(f"  {fy}->{ty}: {c:,}")

# Sample triple-match: parishes in all 3 years
print("\nSample parishes in ALL THREE years (1865 + 1868 + 2021):")
for r in dir_db.execute("""
    SELECT d1.name, d2.name, d3.name, d1.city, d1.state
    FROM dir_cross_year x1
    JOIN dir_entries d1 ON x1.entry_from_id = d1.id
    JOIN dir_entries d2 ON x1.entry_to_id = d2.id
    JOIN dir_cross_year x2 ON d2.id = x2.entry_from_id
    JOIN dir_entries d3 ON x2.entry_to_id = d3.id
    WHERE x1.year_from=1865 AND x1.year_to=1868
    AND x2.year_from=1868 AND x2.year_to=2021
    LIMIT 15
"""):
    print(f"  1865: {r[0][:30]:30s}  1868: {r[1][:30]:30s}  2021: {r[2][:30]:30s}  ({r[3]}, {r[4]})")

dir_db.close()
print("\nDone.")

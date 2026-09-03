"""Compute county-level elevation averages from tract_elevation,
then join to churches via county_fips_5.

This gives instant elevation coverage for 885K US churches.
"""
import sqlite3, csv, os
from pathlib import Path
from datetime import datetime

DB_PATH = "E:/grid/churches.db"
db = sqlite3.connect(DB_PATH)
c = db.cursor()

# Add elevation_m column if needed
try:
    db.execute("ALTER TABLE churches ADD COLUMN elevation_m REAL")
    print('Added elevation_m column')
except:
    print('elevation_m column exists')

# Step 1: Compute county-level average elevation from tract_elevation
# tract_fips format: SSCCCTTTTTT where first 5 chars = state+county FIPS
print('Computing county elevation averages from tract_elevation...')
county_elev = {}
rows = c.execute("SELECT tract_fips, elevation_m FROM tract_elevation WHERE elevation_m IS NOT NULL").fetchall()
for tract_fips, elev in rows:
    county_fips = tract_fips[:5]  # First 5 chars = state + county
    if county_fips not in county_elev:
        county_elev[county_fips] = []
    county_elev[county_fips].append(elev)

county_avg = {}
for fips, elevations in county_elev.items():
    county_avg[fips] = round(sum(elevations) / len(elevations), 1)

print(f'  Computed averages for {len(county_avg):,} counties from {len(rows):,} tracts')

# Step 2: Update churches with county elevation
# churches.county_fips_5 matches tract_fips first 5 chars
total = c.execute("SELECT COUNT(*) FROM churches WHERE county_fips_5 IS NOT NULL AND county_fips_5 != ''").fetchone()[0]
print(f'\nUpdating {total:,} churches with county-level elevation...')

# Batch update
updates = []
fips_list = list(county_avg.keys())
for fips in fips_list:
    elev = county_avg[fips]
    # Churches where county_fips_5 matches
    affected = c.execute(
        "UPDATE churches SET elevation_m=? WHERE county_fips_5=? AND elevation_m IS NULL",
        (elev, fips)
    ).rowcount
    if affected > 0:
        updates.append((fips, elev, affected))

db.commit()
total_updated = sum(u[2] for u in updates)
print(f'  Updated {total_updated:,} churches across {len(updates):,} counties')

# Step 3: Coverage check
with_elev = c.execute("SELECT COUNT(*) FROM churches WHERE elevation_m IS NOT NULL").fetchone()[0]
with_gps = c.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND latitude != '' AND longitude IS NOT NULL AND longitude != ''").fetchone()[0]
print(f'\n=== Elevation Coverage ===')
print(f'  With GPS:     {with_gps:>9,}')
print(f'  With elevation: {with_elev:>9,}')
print(f'  Remaining:    {with_gps - with_elev:>9,}')

# Step 4: Show Kentucky bbox
min_lat, min_lon, max_lat, max_lon = 37.0, -86.0, 39.0, -84.5
ky_with = c.execute("SELECT COUNT(*) FROM churches WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? AND elevation_m IS NOT NULL", (min_lat, max_lat, min_lon, max_lon)).fetchone()[0]
ky_total = c.execute("SELECT COUNT(*) FROM churches WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?", (min_lat, max_lat, min_lon, max_lon)).fetchone()[0]
print(f'\n  KY bbox: {ky_with:,}/{ky_total:,} with elevation ({ky_with/ky_total*100:.0f}%)')

# Sample
print('\n  Sample KY elevations:')
for r in c.execute("SELECT name, city, county, elevation_m FROM churches WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? AND elevation_m IS NOT NULL LIMIT 5", (min_lat, max_lat, min_lon, max_lon)):
    print(f'    {r[0][:35] if r[0] else "?":35s} | {r[1]:15s} | {r[2]:10s} | {r[3]}m')

# Step 5: Log provenance
try:
    db.execute("""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at,
            churches_updated, fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'county_elevation', 'compute_elevation_county.py',
        datetime.now().isoformat(), datetime.now().isoformat(),
        total_updated, 'elevation_m', 'completed',
        f'County-level elevation from tract_elevation, {len(county_avg)} counties, {total_updated:,} churches.'
    ))
    db.commit()
except Exception as e:
    print(f'Provenance log: {e}')

db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
db.close()
print('\nDone!')

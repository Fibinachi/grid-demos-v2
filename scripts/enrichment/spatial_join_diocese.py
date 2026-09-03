"""
Spatial join: assign diocese to churches using point-in-polygon against Burchfiel's
diocese boundary geojson. This catches churches with lat/lon but no FIPS code.
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance
import geopandas as gpd
from shapely.geometry import Point
from shapely import prepared

BOUNDARIES_GEOJSON = 'data/diocese_mapper/diocese_boundaries_revised.geojson'

print("Loading diocese boundaries...")
dioceses = gpd.read_file(BOUNDARIES_GEOJSON)
print(f"  {len(dioceses)} diocese polygons")

# Prepare for fast spatial lookup
print("  Preparing spatial index...")
diocese_prep = {}
for _, row in dioceses.iterrows():
    name = row.get('Diocese', '')
    if name and row.geometry and row.geometry.is_valid:
        diocese_prep[name] = (prepared.prep(row.geometry), row.geometry)

print(f"  {len(diocese_prep)} valid polygons prepared")

# ── Get unassigned US Catholic churches with lat/lon ──
conn = connect()
c = conn.cursor()
c.execute("""
    SELECT ch.id, ch.latitude, ch.longitude, ch.name, ch.state, ch.city
    FROM churches ch
    LEFT JOIN church_enrichment ce ON ce.church_id = ch.id
    WHERE ch.country='US'
      AND ch.latitude IS NOT NULL AND ch.longitude IS NOT NULL
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND (ce.diocese IS NULL OR ce.diocese = '')
""")

print("Performing spatial join...")
matched = 0
no_match = 0
updates = []

for church_id, lat, lon, name, state, city in c.fetchall():
    if not lat or not lon:
        no_match += 1
        continue
    
    point = Point(lon, lat)
    found = None
    
    for dio_name, (prep_geom, geom) in diocese_prep.items():
        try:
            if prep_geom.contains(point) or geom.contains(point):
                found = dio_name
                break
        except:
            pass
    
    if found:
        # Get diocese detail/province from the Burchfiel CSV
        updates.append((found, '', '', '', church_id))
        matched += 1
    else:
        no_match += 1
    
    if matched % 1000 == 0 and matched > 0:
        print(f"  Matched: {matched:,}, No match: {no_match:,}")

print(f"\n  Total matched: {matched:,}")
print(f"  No match: {no_match:,}")

if updates:
    print(f"\nApplying {len(updates):,} spatial diocese assignments...")
    with Provenance(conn, "spatial_join_diocese.py", source="us_diocese_mapper",
                    action="enriched", fields="diocese"):
        c.executemany("""
            UPDATE church_enrichment 
            SET diocese = ?, diocese_detail = ?, province = ?, province_detail = ?
            WHERE church_id = ?
        """, updates)
        conn.commit()
    
    # Stats
    c.execute("""SELECT COUNT(*) FROM church_enrichment ce
      JOIN churches ch ON ch.id=ce.church_id
      WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')")
    cath_total = c.fetchone()[0]
    print(f"\nCatholic US diocese coverage: {total:,} / {cath_total:,} ({100*total/cath_total:.1f}%)")
    
    # TX specifically
    c.execute("""SELECT COUNT(*) FROM church_enrichment ce
      JOIN churches ch ON ch.id=ce.church_id
      WHERE ch.state='TX' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
    tx_with = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE state='TX' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')")
    tx_total = c.fetchone()[0]
    print(f"TX Catholic diocese coverage: {tx_with:,} / {tx_total:,} ({100*tx_with/tx_total:.1f}%)")

conn.close()

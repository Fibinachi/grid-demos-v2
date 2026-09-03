"""
Fix: re-run spatial join for unassigned churches using sjoin (geopandas built-in)
which handles multipolygons and edge cases much better than manual contains().
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd

BOUNDARIES_GEOJSON = 'data/diocese_mapper/diocese_boundaries_revised.geojson'

print("Loading diocese boundaries...")
dioceses = gpd.read_file(BOUNDARIES_GEOJSON)
dioceses = dioceses[['Diocese', 'geometry']].copy()
print(f"  {len(dioceses)} diocese polygons")

# ── Get unassigned US Catholic churches with lat/lon ──
conn = connect()
c = conn.cursor()
c.execute("""
    SELECT ch.id, ch.latitude, ch.longitude
    FROM churches ch
    LEFT JOIN church_enrichment ce ON ce.church_id = ch.id
    WHERE ch.country='US'
      AND ch.latitude IS NOT NULL AND ch.longitude IS NOT NULL
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND (ce.diocese IS NULL OR ce.diocese = '')
""")

rows = c.fetchall()
print(f"  {len(rows):,} unassigned churches with coords")

# Create GeoDataFrame for churches
church_df = pd.DataFrame(rows, columns=['church_id', 'lat', 'lon'])
church_df['geometry'] = church_df.apply(lambda r: Point(r['lon'], r['lat']), axis=1)
church_gdf = gpd.GeoDataFrame(church_df, geometry='geometry', crs='EPSG:4326')
# Ensure same CRS
if dioceses.crs != church_gdf.crs:
    dioceses = dioceses.to_crs(church_gdf.crs)

# Spatial join using geopandas built-in (much more robust)
print("Running spatial join...")
joined = gpd.sjoin(church_gdf, dioceses, how='left', predicate='within')
print(f"  Joined: {joined['Diocese'].notna().sum():,} matched, {joined['Diocese'].isna().sum():,} unmatched")

# Prepare updates
updates = []
for _, row in joined.iterrows():
    if pd.notna(row.get('Diocese')):
        updates.append((row['Diocese'], '', '', '', row['church_id']))

print(f"\n  New matches to apply: {len(updates):,}")

if updates:
    with Provenance(conn, "spatial_join_v2.py", source="us_diocese_mapper",
                    action="enriched", fields="diocese"):
        c.executemany("""
            UPDATE church_enrichment 
            SET diocese = ?, diocese_detail = ?, province = ?, province_detail = ?
            WHERE church_id = ?
        """, updates)
        conn.commit()

# Final stats
c.execute("""SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id
  WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
  AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
total_with = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')")
cath_total = c.fetchone()[0]
print(f"\nFinal: {total_with:,} / {cath_total:,} ({100*total_with/cath_total:.1f}%)")

# AK and FL specifically
for state in ['AK', 'FL']:
    c.execute(f"""SELECT COUNT(*) FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id
      WHERE ch.state='{state}' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')""")
    with_d = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM churches WHERE state='{state}' AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')")
    total_d = c.fetchone()[0]
    print(f"  {state}: {with_d:,} / {total_d:,} ({100*with_d/total_d:.0f}%)")

conn.close()

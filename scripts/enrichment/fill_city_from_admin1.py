"""
Fill missing city/state from Natural Earth admin1 boundaries via point-in-polygon spatial join.
For records where Nominatim couldn't resolve a city, this assigns the admin1 (state/province/governorate)
name as the state, and also uses admin1 + nearest populated place as city.

Usage:
  python scripts/enrichment/fill_city_from_admin1.py --dry-run     # test 5 samples
  python scripts/enrichment/fill_city_from_admin1.py                # process all
  python scripts/enrichment/fill_city_from_admin1.py --limit 100
"""
import sqlite3, sys, os, time, math
import geopandas as gpd
from shapely.geometry import Point
from shapely import STRtree
from tqdm import tqdm

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
SHP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   'data', 'natural_earth', 'ne_10m_admin_1_states_provinces.shp')

DRY_RUN = '--dry-run' in sys.argv
LIMIT = None
for i, a in enumerate(sys.argv):
    if a.startswith('--limit='):
        LIMIT = int(a.split('=')[1])
    elif a == '--limit' and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])

# ── Load admin1 boundaries ──
print(f"Loading: {SHP}")
start = time.time()
gdf = gpd.read_file(SHP)
# Filter to only countries we need
db = sqlite3.connect(DB)
c = db.cursor()
c.execute("""
    SELECT DISTINCT country FROM churches
    WHERE (city IS NULL OR city = '')
      AND latitude IS NOT NULL AND latitude != 0
      AND country != 'US'
""")
needed_countries = set(r[0] for r in c.fetchall())

# Natural Earth uses iso_a2 or name for country matching
# Build mapping: iso_a2 -> country name, name -> iso_a2
country_codes = {
    'YE': 'Yemen', 'NG': 'Nigeria', 'DZ': 'Algeria', 'IN': 'India',
    'BH': 'Bahrain', 'ET': 'Ethiopia', 'SY': 'Syria', 'IQ': 'Iraq',
    'LK': 'Sri Lanka', 'GR': 'Greece', 'UG': 'Uganda', 'NP': 'Nepal',
    'MM': 'Myanmar', 'SD': 'Sudan', 'EG': 'Egypt', 'TZ': 'Tanzania',
    'CD': 'DR Congo', 'AO': 'Angola', 'SA': 'Saudi Arabia', 'CA': 'Canada',
    'PK': 'Pakistan', 'AF': 'Afghanistan', 'KE': 'Kenya', 'SO': 'Somalia',
    'ML': 'Mali', 'NE': 'Niger', 'TD': 'Chad', 'CM': 'Cameroon', 'GH': 'Ghana',
    'BJ': 'Benin', 'TG': 'Togo', 'BF': 'Burkina Faso', 'CI': "Côte d'Ivoire",
    'SN': 'Senegal', 'ZM': 'Zambia', 'ZW': 'Zimbabwe', 'MW': 'Malawi',
    'MZ': 'Mozambique', 'MG': 'Madagascar', 'BW': 'Botswana', 'NA': 'Namibia',
    'MR': 'Mauritania', 'LY': 'Libya', 'TN': 'Tunisia', 'MA': 'Morocco',
    'JO': 'Jordan', 'LB': 'Lebanon', 'KW': 'Kuwait', 'AE': 'UAE', 'OM': 'Oman',
    'QA': 'Qatar', 'PS': 'Palestine', 'IL': 'Israel', 'IR': 'Iran',
    'TR': 'Turkey', 'RU': 'Russia', 'UA': 'Ukraine', 'PL': 'Poland',
    'DE': 'Germany', 'FR': 'France', 'GB': 'United Kingdom', 'IT': 'Italy',
    'ES': 'Spain', 'PT': 'Portugal', 'NL': 'Netherlands', 'BE': 'Belgium',
    'CH': 'Switzerland', 'AT': 'Austria', 'CZ': 'Czechia', 'SK': 'Slovakia',
    'HU': 'Hungary', 'RO': 'Romania', 'BG': 'Bulgaria', 'HR': 'Croatia',
    'RS': 'Serbia', 'BA': 'Bosnia and Herz.', 'SI': 'Slovenia', 'MK': 'North Macedonia',
    'AL': 'Albania', 'ME': 'Montenegro', 'XK': 'Kosovo',
    'SE': 'Sweden', 'NO': 'Norway', 'FI': 'Finland', 'DK': 'Denmark',
    'IS': 'Iceland', 'IE': 'Ireland', 'EE': 'Estonia', 'LV': 'Latvia', 'LT': 'Lithuania',
    'JP': 'Japan', 'KR': 'South Korea', 'KP': 'North Korea', 'CN': 'China',
    'TW': 'Taiwan', 'MN': 'Mongolia', 'VN': 'Vietnam', 'LA': 'Laos',
    'KH': 'Cambodia', 'TH': 'Thailand', 'MY': 'Malaysia', 'SG': 'Singapore',
    'PH': 'Philippines', 'ID': 'Indonesia', 'TL': 'Timor-Leste',
    'BD': 'Bangladesh', 'BT': 'Bhutan', 'MV': 'Maldives',
    'AU': 'Australia', 'NZ': 'New Zealand', 'PG': 'Papua New Guinea',
    'FJ': 'Fiji', 'SB': 'Solomon Islands', 'VU': 'Vanuatu',
    'MX': 'Mexico', 'GT': 'Guatemala', 'BZ': 'Belize', 'HN': 'Honduras',
    'SV': 'El Salvador', 'NI': 'Nicaragua', 'CR': 'Costa Rica', 'PA': 'Panama',
    'CU': 'Cuba', 'JM': 'Jamaica', 'HT': 'Haiti', 'DO': 'Dominican Republic',
    'BS': 'Bahamas', 'BB': 'Barbados', 'TT': 'Trinidad and Tobago',
    'CO': 'Colombia', 'VE': 'Venezuela', 'EC': 'Ecuador', 'PE': 'Peru',
    'BO': 'Bolivia', 'PY': 'Paraguay', 'UY': 'Uruguay', 'AR': 'Argentina',
    'CL': 'Chile', 'GY': 'Guyana', 'SR': 'Suriname', 'GF': 'French Guiana',
    'BR': 'Brazil',
}

# Filter gdf to needed countries
needed_names = set()
for code in needed_countries:
    if code in country_codes:
        needed_names.add(country_codes[code])
    else:
        needed_names.add(code)  # try raw code

# Natural Earth uses 'admin' for country name and 'iso_a2' for country code
gdf_filtered = gdf[gdf['admin'].isin(needed_names) | gdf['iso_a2'].isin(needed_countries)]
print(f"  Filtered to {len(gdf_filtered):,} polygons covering needed countries (from {len(gdf):,} total)")

# Build spatial index
print("Building STRtree spatial index...")
geoms = gdf_filtered.geometry.values
tree = STRtree(geoms)
print(f"  Done in {time.time()-start:.0f}s")

# ── Fetch records to process ──
sql = """SELECT c.id, c.latitude, c.longitude, c.country, c.name
FROM churches c
WHERE (c.city IS NULL OR c.city = '')
  AND c.latitude IS NOT NULL AND c.latitude != 0
  AND c.country != 'US'
ORDER BY c.id"""
if LIMIT:
    sql += f' LIMIT {LIMIT}'

all_rows = list(c.execute(sql).fetchall())
total = len(all_rows)
print(f"\nRecords to process: {total:,}")

if DRY_RUN:
    print("DRY RUN — sample only:\n")

# ── Process ──
CHUNK = 500
batch = []
updated = 0
no_match = 0
start = time.time()

# Build reverse lookup: iso_a2 -> country name from gdf
iso_to_name = dict(zip(gdf_filtered['iso_a2'], gdf_filtered['admin']))

def lookup_admin1(lat, lon, country_code):
    """Find admin1 name for a point. Returns (admin1_name, country_name) or (None, None)."""
    point = Point(lon, lat)
    # Query spatial index for candidate polygons
    candidates_idx = tree.query(point, predicate='intersects')
    if len(candidates_idx) == 0:
        # Try small buffer
        candidates_idx = tree.query(point.buffer(0.01), predicate='intersects')
    if len(candidates_idx) == 0:
        return None, None
    
    # Check each candidate polygon
    for idx in candidates_idx:
        geom = geoms[idx]
        if geom.contains(point) or geom.buffer(0.01).contains(point):
            row = gdf_filtered.iloc[idx]
            admin1_name = row.get('name', '') or row.get('name_en', '') or ''
            country_name = row.get('admin', '') or ''
            return admin1_name, country_name
    
    # If no exact match, return closest polygon's admin1
    idx = candidates_idx[0]
    row = gdf_filtered.iloc[idx]
    return (row.get('name', '') or row.get('name_en', '') or ''), (row.get('admin', '') or '')

for chid, lat, lon, country, name in tqdm(all_rows, desc="Spatial join", unit='rec'):
    admin1, country_match = lookup_admin1(lat, lon, country)
    
    if admin1:
        # Use admin1 as state, and also as city if it's specific enough
        batch.append((admin1, admin1, chid))
    else:
        no_match += 1
        if no_match <= 5:
            tqdm.write(f"  [#{chid}] ({lat:.5f},{lon:.5f}) '{name[:50] if name else 'N/A'}' [{country}] -> NO ADMIN MATCH")
    
    if DRY_RUN and len(batch) >= 5:
        break
    
    if len(batch) >= CHUNK:
        c.executemany(
            """UPDATE churches SET 
               city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END,
               state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END
               WHERE id=?""",
            batch
        )
        db.commit()
        updated += len(batch)
        batch = []

# Final flush
if batch:
    c.executemany(
        """UPDATE churches SET 
           city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END,
           state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END
           WHERE id=?""",
        batch
    )
    db.commit()
    updated += len(batch)

elapsed = time.time() - start
print(f"\nDone in {elapsed:.0f}s ({elapsed/60:.1f}m)")
print(f"  Updated:    {updated:,}")
print(f"  No match:   {no_match:,}")
print(f"  Rate:       {total/elapsed:.0f} rec/s")

# Check remaining
c.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (city IS NULL OR city = '')
      AND latitude IS NOT NULL AND latitude != 0
      AND country != 'US'
""")
remaining = c.fetchone()[0]
print(f"  Remaining:  {remaining:,}")

db.close()

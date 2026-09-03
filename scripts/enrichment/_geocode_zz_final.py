"""
Final clean ZZ geocoding:
1. Point-in-polygon for records with valid IDs
2. Name-based fallback for records with country in the name
3. Handle NULL-id records separately
"""
import sqlite3, geopandas as gpd, pandas as pd, datetime, re
from pathlib import Path
from shapely.geometry import Point

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
DATA_DIR = Path('data/shapefiles')
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# ── Load world ──────────────────────────────────────────────────────────────
world = gpd.read_file(DATA_DIR / 'ne_50m_admin_0_countries.shp')
world = world[['ISO_A2', 'NAME', 'geometry']].copy()
world = world[world['ISO_A2'] != '-99']
world_sindex = world.sindex
print(f"Countries: {len(world)}")

# ── Load ZZ records ─────────────────────────────────────────────────────────
c.execute("SELECT COUNT(*) FROM churches WHERE country='ZZ' AND latitude IS NOT NULL")
total_zz = c.fetchone()[0]
print(f"ZZ records with coords: {total_zz:,}")

c.execute("SELECT id, name, latitude, longitude FROM churches WHERE country='ZZ' AND latitude IS NOT NULL")
records = c.fetchall()

# ── Step 1: Point-in-polygon ────────────────────────────────────────────────
mapping = {}  # id → ISO_A2
unmatched = []
null_id_matches = []

for rid, name, lat, lon in records:
    if lat is None or lon is None:
        continue
    
    point = Point(lon, lat)
    candidates = list(world_sindex.intersection(point.bounds))
    found = False
    for idx in candidates:
        geom = world.iloc[idx].geometry
        if geom.contains(point) or geom.intersects(point):
            iso = world.iloc[idx]['ISO_A2']
            if rid is not None:
                mapping[rid] = iso
            else:
                null_id_matches.append((name, lat, lon, iso))
            found = True
            break
    
    if not found:
        unmatched.append((rid, name, lat, lon))

print(f"Point-in-polygon matches: {len(mapping)} (valid IDs) + {len(null_id_matches)} (NULL IDs)")
print(f"Unmatched: {len(unmatched)}")

# ── Step 2: Name-based fallback ─────────────────────────────────────────────
# Build country name → ISO lookup from world dataset
name_to_iso = {}
for _, row in world.iterrows():
    name_to_iso[row['NAME'].lower()] = row['ISO_A2']
# Add common variants
name_variants = {
    'usa': 'US', 'united states': 'US', 'america': 'US',
    'uk': 'GB', 'england': 'GB', 'britain': 'GB',
    'russia': 'RU', 'china': 'CN', 'india': 'IN',
    'uae': 'AE', 'dubai': 'AE', 'iran': 'IR',
    'syria': 'SY', 'jordan': 'JO', 'lebanon': 'LB',
    'brazil': 'BR', 'mexico': 'MX', 'canada': 'CA',
    'mozambique': 'MZ', 'norway': 'NO', 'france': 'FR',
    'germany': 'DE', 'italy': 'IT', 'spain': 'ES',
    'japan': 'JP', 'korea': 'KR', 'australia': 'AU',
    'egypt': 'EG', 'south africa': 'ZA', 'nigeria': 'NG',
    'kenya': 'KE', 'ghana': 'GH', 'ethiopia': 'ET',
    'philippines': 'PH', 'indonesia': 'ID', 'vietnam': 'VN',
    'thailand': 'TH', 'myanmar': 'MM', 'malaysia': 'MY',
    'singapore': 'SG', 'pakistan': 'PK', 'bangladesh': 'BD',
    'poland': 'PL', 'ukraine': 'UA', 'romania': 'RO',
    'hungary': 'HU', 'czech': 'CZ', 'slovakia': 'SK',
    'austria': 'AT', 'switzerland': 'CH', 'netherlands': 'NL',
    'belgium': 'BE', 'sweden': 'SE', 'norway': 'NO',
    'denmark': 'DK', 'finland': 'FI', 'portugal': 'PT',
    'greece': 'GR', 'turkey': 'TR', 'israel': 'IL',
    'argentina': 'AR', 'chile': 'CL', 'peru': 'PE',
    'colombia': 'CO', 'venezuela': 'VE', 'ecuador': 'EC',
    'bolivia': 'BO', 'paraguay': 'PY', 'uruguay': 'UY',
    'cuba': 'CU', 'dominican': 'DO', 'haiti': 'HT',
    'jamaica': 'JM', 'trinidad': 'TT', 'barbados': 'BB',
    'samoa': 'WS', 'tonga': 'TO', 'fiji': 'FJ',
    'mauritius': 'MU', 'seychelles': 'SC', 'maldives': 'MV',
    'cambodia': 'KH', 'laos': 'LA', 'mongolia': 'MN',
    'nepal': 'NP', 'sri lanka': 'LK', 'bhutan': 'BT',
    'oman': 'OM', 'kuwait': 'KW', 'bahrain': 'BH',
    'qatar': 'QA', 'yemen': 'YE', 'iraq': 'IQ',
    'afghanistan': 'AF', 'turkmenistan': 'TM', 'uzbekistan': 'UZ',
    'kazakhstan': 'KZ', 'azerbaijan': 'AZ', 'georgia': 'GE',
    'armenia': 'AM', 'belarus': 'BY', 'lithuania': 'LT',
    'latvia': 'LV', 'estonia': 'EE', 'moldova': 'MD',
    'albania': 'AL', 'croatia': 'HR', 'serbia': 'RS',
    'bosnia': 'BA', 'slovenia': 'SI', 'montenegro': 'ME',
    'macedonia': 'MK', 'bulgaria': 'BG', 'cyprus': 'CY',
    'malta': 'MT', 'iceland': 'IS', 'luxembourg': 'LU',
    'monaco': 'MC', 'liechtenstein': 'LI', 'andorra': 'AD',
    'san marino': 'SM', 'vatican': 'VA', 'palestine': 'PS',
    'morocco': 'MA', 'algeria': 'DZ', 'tunisia': 'TN',
    'libya': 'LY', 'sudan': 'SD', 'mali': 'ML',
    'senegal': 'SN', 'ivory coast': 'CI', "cote d'ivoire": 'CI',
    'burkina faso': 'BF', 'niger': 'NE', 'chad': 'TD',
    'cameroon': 'CM', 'gabon': 'GA', 'congo': 'CG',
    'angola': 'AO', 'namibia': 'NA', 'botswana': 'BW',
    'zimbabwe': 'ZW', 'zambia': 'ZM', 'malawi': 'MW',
    'tanzania': 'TZ', 'uganda': 'UG', 'rwanda': 'RW',
    'burundi': 'BI', 'somalia': 'SO', 'eritrea': 'ER',
    'djibouti': 'DJ', 'madagascar': 'MG', 'comoros': 'KM',
    'mauritania': 'MR', 'gambia': 'GM', 'guinea': 'GN',
    'sierra leone': 'SL', 'liberia': 'LR', 'togo': 'TG',
    'benin': 'BJ', 'panama': 'PA', 'costa rica': 'CR',
    'nicaragua': 'NI', 'honduras': 'HN', 'el salvador': 'SV',
    'guatemala': 'GT', 'belize': 'BZ', 'suriname': 'SR',
    'guyana': 'GY', 'new zealand': 'NZ', 'papua new guinea': 'PG',
    'solomon islands': 'SB', 'vanuatu': 'VU', 'kiribati': 'KI',
    'micronesia': 'FM', 'palau': 'PW', 'marshall islands': 'MH',
    'tuvalu': 'TV', 'nauru': 'NR', 'brunei': 'BN',
    'timor': 'TL', 'east timor': 'TL', 'taiwan': 'TW',
    'hong kong': 'HK', 'macau': 'MO',
}

name_fixes = 0
still_unmatched = []
for rid, name, lat, lon in unmatched:
    if name is None:
        still_unmatched.append((rid, name, lat, lon))
        continue
    
    name_lower = name.lower()
    found = False
    # Try to find country name in the record name (e.g., "Oslo Norway Temple" → Norway)
    for country_name, iso in name_variants.items():
        if country_name in name_lower:
            if rid is not None:
                mapping[rid] = iso
            name_fixes += 1
            found = True
            break
    
    if not found:
        # Try the world dataset names
        for country_name, iso in name_to_iso.items():
            if country_name in name_lower and len(country_name) > 3:
                if rid is not None:
                    mapping[rid] = iso
                name_fixes += 1
                found = True
                break
    
    if not found:
        still_unmatched.append((rid, name, lat, lon))

print(f"Name-based fixes: {name_fixes}")
print(f"Still unmatched: {len(still_unmatched)}")

# ── Step 3: Apply updates ───────────────────────────────────────────────────
# For records with valid IDs
valid_mapping = {k: v for k, v in mapping.items() if k is not None}
print(f"\nValid-ID updates: {len(valid_mapping)}")

c.execute("CREATE TEMP TABLE IF NOT EXISTS _zz_map (id INTEGER PRIMARY KEY, country TEXT)")
c.execute("DELETE FROM _zz_map")
items = list(valid_mapping.items())
for i in range(0, len(items), 1000):
    c.executemany("INSERT OR REPLACE INTO _zz_map VALUES (?, ?)", items[i:i+1000])

c.execute("""
    UPDATE churches SET country = (SELECT country FROM _zz_map WHERE id = churches.id)
    WHERE id IN (SELECT id FROM _zz_map)
""")
updated_by_id = c.rowcount
print(f"Updated by ID: {updated_by_id}")

# For NULL-id records: use (latitude, longitude) as composite key
null_id_updates = 0
for name, lat, lon, iso in null_id_matches:
    c.execute("""
        UPDATE churches SET country=?
        WHERE rowid = (
            SELECT rowid FROM churches
            WHERE country='ZZ' AND id IS NULL
              AND latitude=? AND longitude=?
            LIMIT 1
        )
    """, (iso, lat, lon))
    null_id_updates += c.rowcount

print(f"Updated NULL-id records: {null_id_updates}")
conn.commit()
total_updated = updated_by_id + null_id_updates

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_geocode_zz_final.py', TS, TS,
      total_updated, 0, 'country', 'completed',
      f'Geocoded {total_updated} ZZ→country (point-in-polygon + name fallback + NULL-id fix)'))

conn.commit()

# Final count
c.execute("SELECT COUNT(*) FROM churches WHERE country='ZZ'")
remaining = c.fetchone()[0]
print(f"\nRemaining ZZ: {remaining:,}")

if still_unmatched:
    print(f"\nStill unmatched sample (remaining {len(still_unmatched)}):")
    for rid, name, lat, lon in still_unmatched[:15]:
        print(f"  ID={rid} {str(name)[:50]:<50} ({lat:.4f}, {lon:.4f})")

conn.close()
print("Done!")

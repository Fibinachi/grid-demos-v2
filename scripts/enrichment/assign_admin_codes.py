"""
Spatial join: assign admin codes (ADM0, ADM1, ADM2) to every church with GPS.
Uses geoBoundaries GeoJSON polygons with shapely + STRtree spatial index.

Processes country by country. For US, uses existing Census county_fips_5 + state.

Usage:
  python scripts/enrichment/assign_admin_codes.py           # all countries
  python scripts/enrichment/assign_admin_codes.py --dry-run # test US only, 5 samples
  python scripts/enrichment/assign_admin_codes.py --country CAN  # single country
"""
import sqlite3, sys, os, json, time
from collections import defaultdict
from tqdm import tqdm

try:
    from shapely.geometry import shape, Point, mapping
    from shapely import STRtree
except ImportError:
    print("ERROR: shapely>=2.0 required. Install: pip install shapely")
    sys.exit(1)

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(BASE, 'churches.db')
BOUNDARIES = os.path.join(BASE, 'data', 'world_boundaries')

DRY_RUN = '--dry-run' in sys.argv
SINGLE_COUNTRY = None
for a in sys.argv:
    if a.startswith('--country='):
        SINGLE_COUNTRY = a.split('=', 1)[1].upper()


def s(v):
    return (v or '').strip()


def load_geojson(path):
    """Load GeoJSON file, return list of (geometry, properties_dict)."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    features = data.get('features', [])
    results = []
    for feat in features:
        geom = feat.get('geometry')
        props = feat.get('properties', {})
        if geom and props:
            try:
                shp = shape(geom)
                if shp.is_valid and not shp.is_empty:
                    results.append((shp, props))
            except Exception:
                pass
    return results


def get_admin_name(props, country_iso3):
    """Extract best admin name from geoBoundaries properties."""
    return (props.get('shapeName') or props.get('name') or 
            props.get('admin1Name') or props.get('admin2Name') or '')


def get_admin_code(props, country_iso3, level):
    """Extract admin code from geoBoundaries properties."""
    # geoBoundaries uses different key names per level
    if level == 0:
        return props.get('shapeISO') or props.get('iso3') or country_iso3
    elif level == 1:
        return (props.get('shapeISO') or props.get('ISO3166_2') or 
                props.get('code') or props.get('admin1Code') or '')
    else:
        return (props.get('shapeISO') or props.get('code') or 
                props.get('admin2Code') or props.get('shapeID') or '')


def process_us(cursor, dry=False):
    """US already has county_fips_5 and state. Just normalize."""
    # For US, admin0 = 'US', admin1 = state code, admin2 = county_fips_5
    print("US: using existing Census county_fips_5 + state")
    
    # Count how many US churches already have county_fips_5
    total = cursor.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND latitude IS NOT NULL AND latitude!=0").fetchone()[0]
    has_fips = cursor.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND county_fips_5 IS NOT NULL AND county_fips_5!=''").fetchone()[0]
    print(f"  {has_fips:,} / {total:,} have county_fips_5 ({has_fips/total*100:.1f}%)")
    
    if dry:
        return
    
    # admin0_code = 'US' for all US churches
    cursor.execute("UPDATE churches SET admin0_code='US' WHERE country='US'")
    # admin1_code = state (already in state column, normalize to 2-letter)
    cursor.execute("""
        UPDATE churches SET admin1_code=UPPER(SUBSTR(state,1,2))
        WHERE country='US' AND state IS NOT NULL AND state!=''
    """)
    # admin2_code = county_fips_5
    cursor.execute("""
        UPDATE churches SET admin2_code=county_fips_5
        WHERE country='US' AND county_fips_5 IS NOT NULL AND county_fips_5!=''
    """)
    return total


def process_country(iso3, cursor, dry=False):
    """Spatial join churches in one country to geoBoundaries admin levels."""
    # Find available admin level files
    levels = {}
    for level in [0, 1, 2]:
        path = os.path.join(BOUNDARIES, f"geoBoundaries-{iso3}-ADM{level}.geojson")
        if os.path.exists(path):
            levels[level] = path
    
    if not levels:
        return 0
    
    # Get churches in this country with GPS
    # Map ISO3 to possible country name variants
    iso2 = iso3_to_iso2(iso3)
    
    # First try ISO2 match, then name match
    churches = cursor.execute("""
        SELECT id, latitude, longitude, country FROM churches
        WHERE country=? AND latitude IS NOT NULL AND latitude!=0
    """, (iso2,)).fetchall()
    
    if not churches:
        # Try matching by full country name
        churches = cursor.execute("""
            SELECT id, latitude, longitude, country FROM churches
            WHERE UPPER(country)=? AND latitude IS NOT NULL AND latitude!=0
        """, (iso3,)).fetchall()
    
    if not churches:
        return 0
    
    count = len(churches)
    
    if dry:
        churches = churches[:5]
        count = len(churches)
    
    print(f"\n{iso3}: {count:,} churches with GPS, levels={sorted(levels.keys())}")
    
    # Load geometries and build spatial indices
    geo_index = {}
    for level, path in levels.items():
        features = load_geojson(path)
        if not features:
            print(f"  ADM{level}: no valid features, skipping")
            continue
        geoms = [f[0] for f in features]
        tree = STRtree(geoms)
        geo_index[level] = (geoms, features, tree)
        print(f"  ADM{level}: {len(features):,} polygons indexed")
    
    if not geo_index:
        return 0
    
    # Process churches
    # Collect updates by admin level: {level: [(code, name, chid), ...]}
    updates_by_level = {0: [], 1: [], 2: []}
    matched = defaultdict(int)
    
    for chid, lat, lon, country in tqdm(churches, desc=f"  {iso3}", unit='rec'):
        pt = Point(lon, lat)
        
        for level in sorted(geo_index.keys()):
            geoms, features, tree = geo_index[level]
            idx = tree.nearest(pt)
            if idx is None:
                continue
            
            props = features[idx][1]
            code = get_admin_code(props, iso3, level)
            name = get_admin_name(props, iso3)
            
            if code:
                updates_by_level[level].append((code, name, chid))
                matched[level] += 1
    
    # Batch apply updates
    BATCH = 5000
    col_map = {0: ('admin0_code', 'admin0_name'), 1: ('admin1_code', 'admin1_name'), 2: ('admin2_code', 'admin2_name')}
    
    for level in sorted(updates_by_level.keys()):
        updates = updates_by_level[level]
        col_code, col_name = col_map[level]
        
        for i in range(0, len(updates), BATCH):
            batch = updates[i:i+BATCH]
            cursor.executemany(f"UPDATE churches SET {col_code}=?, {col_name}=? WHERE id=?", batch)
    
    print(f"  Matched: ADM0={matched[0]:,} ADM1={matched[1]:,} ADM2={matched[2]:,}")
    return count


# ISO3 → ISO2 mapping (for DB country lookup)
ISO3_TO_ISO2 = {v: k for k, v in {
    'AF':'AFG','AL':'ALB','DZ':'DZA','AS':'ASM','AD':'AND','AO':'AGO',
    'AR':'ARG','AM':'ARM','AU':'AUS','AT':'AUT','AZ':'AZE','BS':'BHS',
    'BH':'BHR','BD':'BGD','BB':'BRB','BY':'BLR','BE':'BEL','BZ':'BLZ',
    'BJ':'BEN','BM':'BMU','BT':'BTN','BO':'BOL','BA':'BIH','BW':'BWA',
    'BR':'BRA','BN':'BRN','BG':'BGR','BF':'BFA','BI':'BDI','CV':'CPV',
    'KH':'KHM','CM':'CMR','CA':'CAN','KY':'CYM','CF':'CAF','TD':'TCD',
    'CL':'CHL','CN':'CHN','CO':'COL','KM':'COM','CG':'COG','CD':'COD',
    'CR':'CRI','CI':'CIV','HR':'HRV','CU':'CUB','CY':'CYP','CZ':'CZE',
    'DK':'DNK','DJ':'DJI','DO':'DOM','EC':'ECU','EG':'EGY','SV':'SLV',
    'GQ':'GNQ','ER':'ERI','EE':'EST','SZ':'SWZ','ET':'ETH','FJ':'FJI',
    'FI':'FIN','FR':'FRA','GA':'GAB','GM':'GMB','GE':'GEO','DE':'DEU',
    'GH':'GHA','GR':'GRC','GL':'GRL','GT':'GTM','GN':'GIN','GW':'GNB',
    'GY':'GUY','HT':'HTI','HN':'HND','HK':'HKG','HU':'HUN','IS':'ISL',
    'IN':'IND','ID':'IDN','IR':'IRN','IQ':'IRQ','IE':'IRL','IL':'ISR',
    'IT':'ITA','JM':'JAM','JP':'JPN','JO':'JOR','KZ':'KAZ','KE':'KEN',
    'KI':'KIR','KP':'PRK','KR':'KOR','KW':'KWT','KG':'KGZ','LA':'LAO',
    'LV':'LVA','LB':'LBN','LS':'LSO','LR':'LBR','LY':'LBY','LI':'LIE',
    'LT':'LTU','LU':'LUX','MO':'MAC','MG':'MDG','MW':'MWI','MY':'MYS',
    'MV':'MDV','ML':'MLI','MT':'MLT','MH':'MHL','MR':'MRT','MU':'MUS',
    'MX':'MEX','FM':'FSM','MD':'MDA','MC':'MCO','MN':'MNG','ME':'MNE',
    'MA':'MAR','MZ':'MOZ','MM':'MMR','NA':'NAM','NR':'NRU','NP':'NPL',
    'NL':'NLD','NZ':'NZL','NI':'NIC','NE':'NER','NG':'NGA','MK':'MKD',
    'MP':'MNP','NO':'NOR','OM':'OMN','PK':'PAK','PW':'PLW','PS':'PSE',
    'PA':'PAN','PG':'PNG','PY':'PRY','PE':'PER','PH':'PHL','PL':'POL',
    'PT':'PRT','PR':'PRI','QA':'QAT','RO':'ROU','RU':'RUS','RW':'RWA',
    'WS':'WSM','SM':'SMR','ST':'STP','SA':'SAU','SN':'SEN','RS':'SRB',
    'SC':'SYC','SL':'SLE','SG':'SGP','SK':'SVK','SI':'SVN','SB':'SLB',
    'SO':'SOM','ZA':'ZAF','SS':'SSD','ES':'ESP','LK':'LKA','SD':'SDN',
    'SR':'SUR','SE':'SWE','CH':'CHE','SY':'SYR','TW':'TWN','TJ':'TJK',
    'TZ':'TZA','TH':'THA','TL':'TLS','TG':'TGO','TO':'TON','TT':'TTO',
    'TN':'TUN','TR':'TUR','TM':'TKM','TV':'TUV','UG':'UGA','UA':'UKR',
    'AE':'ARE','GB':'GBR','US':'USA','UY':'URY','UZ':'UZB','VU':'VUT',
    'VA':'VAT','VE':'VEN','VN':'VNM','VI':'VIR','YE':'YEM','ZM':'ZMB',
    'ZW':'ZWE',
}.items()}


def iso3_to_iso2(iso3):
    return ISO3_TO_ISO2.get(iso3, iso3[:2])


# ── Main ──

def main():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()
    
    # Add admin columns if not exist
    for col in ['admin0_code', 'admin0_name', 'admin1_code', 'admin1_name', 
                'admin2_code', 'admin2_name']:
        try:
            c.execute(f"ALTER TABLE churches ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass  # already exists
    db.commit()
    
    if DRY_RUN:
        print("DRY RUN - US only, 5 samples\n")
        process_us(c, dry=True)
        db.close()
        return
    
    # ── US first (uses Census data, no spatial join needed) ──
    process_us(c)
    db.commit()
    
    if SINGLE_COUNTRY:
        process_country(SINGLE_COUNTRY, c)
        db.commit()
        db.close()
        return
    
    # ── All other countries ──
    # Find which countries have geoBoundaries files
    geo_countries = set()
    for fname in os.listdir(BOUNDARIES):
        if fname.startswith('geoBoundaries-') and fname.endswith('.geojson'):
            # geoBoundaries-XXX-ADM0.geojson -> XXX
            parts = fname.replace('geoBoundaries-', '').split('-')
            if len(parts) >= 2:
                geo_countries.add(parts[0])
    
    # Get countries with churches (by ISO2 code)
    country_counts = c.execute("""
        SELECT country, COUNT(*) n FROM churches
        WHERE country IS NOT NULL AND country!='' AND country!='US'
        AND latitude IS NOT NULL AND latitude!=0
        GROUP BY country ORDER BY n DESC
    """).fetchall()
    
    # Map DB country names to ISO3
    country_to_iso3 = {}
    for cc_name, n in country_counts:
        cc_name_upper = cc_name.strip().upper()
        if len(cc_name_upper) == 2:
            # Already ISO2
            for iso3, iso2 in ISO3_TO_ISO2.items():
                if iso2 == cc_name_upper:
                    country_to_iso3[cc_name] = iso3
                    break
        else:
            # Try direct ISO3 match
            if cc_name_upper in ISO3_TO_ISO2:
                country_to_iso3[cc_name] = cc_name_upper
    
    total = 0
    for country_name, iso3 in sorted(country_to_iso3.items(), key=lambda x: -dict(country_counts).get(x[0], 0)):
        if iso3 not in geo_countries:
            continue
        n = process_country(iso3, c)
        total += n
        db.commit()
    
    # Assign admin0 at minimum for countries without geoBoundaries
    # Use the country name as admin0_code
    c.execute("""
        UPDATE churches SET admin0_code=country
        WHERE admin0_code IS NULL AND country IS NOT NULL AND country!=''
    """)
    db.commit()
    
    print(f"\n{'='*60}")
    print(f"COMPLETE: {total:,} churches processed")
    
    # Stats
    for level in [0, 1, 2]:
        code_col = f'admin{level}_code'
        total_with_gps = c.execute(f"SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND latitude!=0").fetchone()[0]
        assigned = c.execute(f"SELECT COUNT(*) FROM churches WHERE {code_col} IS NOT NULL AND {code_col}!=''").fetchone()[0]
        print(f"  Admin {level}: {assigned:,} / {total_with_gps:,} ({assigned/total_with_gps*100:.1f}%)")
    
    db.close()


if __name__ == '__main__':
    main()

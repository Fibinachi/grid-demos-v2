"""
Church-Free Places Report v3
Uses Census Bureau county centroids for accurate nearest-church distances.
"""
import sqlite3, math, urllib.request, csv, os

DB = 'churches.db'
CENTROID_URL = 'https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt'
CENTROID_CACHE = 'E:/grid/data/county_centroids_2020.csv'

# --- Get county centroids ---
centroids = {}
if os.path.exists(CENTROID_CACHE) and os.path.getsize(CENTROID_CACHE) > 1000:
    print(f"Loading cached centroids...")
    with open(CENTROID_CACHE, 'r') as f:
        for row in csv.DictReader(f):
            centroids[row['fips']] = (float(row['lat']), float(row['lon']))
else:
    print(f"Downloading county centroids from Census Bureau...")
    try:
        req = urllib.request.Request(CENTROID_URL, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=30) as f:
            data = f.read().decode('utf-8')
        lines = data.strip().split('\n')
        for line in lines[1:]:  # skip header
            parts = line.split(',')
            if len(parts) >= 7:
                state_fips = parts[0].strip()
                county_fips = parts[1].strip().zfill(3)  # zero-pad to 3 digits
                fips = state_fips + county_fips
                lat = float(parts[5])  # LATITUDE
                lon = float(parts[6])  # LONGITUDE
                centroids[fips] = (lat, lon)
        # Cache
        with open(CENTROID_CACHE, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['fips', 'lat', 'lon'])
            for fips, (lat, lon) in centroids.items():
                w.writerow([fips, lat, lon])
        print(f"  Downloaded {len(centroids):,} county centroids")
    except Exception as e:
        print(f"  Download failed: {e}")

print(f"Centroids loaded: {len(centroids):,}")

# --- Connect to DB ---
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=DELETE")
conn.execute("PRAGMA synchronous=OFF")

# Get all counties
all_counties = {}
for r in conn.execute("SELECT county_fips, county_name, state_fips, population, total_adherents, adherence_rate FROM county_fips_lookup"):
    fips = r[0]
    all_counties[fips] = {
        'fips': fips, 'name': r[1] or '', 'state_fips': r[2] or '',
        'population': r[3] or 0, 'adherents': r[4] or 0, 'adherence_rate': r[5] or 0
    }

church_counties = set()
for r in conn.execute("SELECT DISTINCT county_fips FROM churches WHERE county_fips IS NOT NULL AND county_fips != ''"):
    church_counties.add(r[0])

no_church = {f: all_counties[f] for f in all_counties if f not in church_counties}
print(f"Counties: {len(all_counties):,} total | {len(church_counties):,} with churches | {len(no_church):,} church-free")

# Build church index
print("Building church index...")
church_data = []
for r in conn.execute("""
    SELECT latitude, longitude, name, city, state, denomination 
    FROM churches 
    WHERE country='US' AND latitude IS NOT NULL AND longitude IS NOT NULL
    AND latitude != 0 AND longitude != 0
"""):
    church_data.append(r)
print(f"  {len(church_data):,} US churches indexed")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def safe(s):
    """Replace non-ASCII chars for cp1252 terminal compatibility."""
    if s is None:
        return ''
    return s.encode('ascii', errors='replace').decode('ascii')

state_names = {
    '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE',
    '11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA',
    '20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN',
    '28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM',
    '36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI',
    '45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA',
    '54':'WV','55':'WI','56':'WY','60':'AS','66':'GU','69':'MP','72':'PR','78':'VI'
}

print()
print("=" * 85)
print("  CHURCH-FREE COUNTIES with Demographics and Nearest Church")
print("=" * 85)

for fips, co in sorted(no_church.items()):
    state_fips = co['state_fips']
    state_abbr = state_names.get(state_fips, state_fips)
    pop = co['population']
    name = co['name'] or '(unnamed)'
    rate = co['adherence_rate']
    
    if fips in centroids:
        ref_lat, ref_lon = centroids[fips]
        coord_source = "census centroid"
    else:
        ref_lat, ref_lon = None, None
        coord_source = "no centroid"
    
    print(f"\n{'='*85}")
    print(f"  {name}, {state_abbr}  (FIPS: {fips})")
    print(f"  Population: {pop:,}  |  Adherents: {co['adherents']:,}  |  Adherence rate: {rate:.1f}%")
    
    if ref_lat is not None:
        nearest = []
        for lat, lon, cname, city, st, denom in church_data:
            d = haversine(ref_lat, ref_lon, lat, lon)
            nearest.append((d, cname, city or '', st, denom or ''))
        nearest.sort(key=lambda x: x[0])
        
        print(f"  Nearest 5 Churches:")
        for i, (dist, cname, city, st, denom) in enumerate(nearest[:5]):
            denom_str = f" [{denom[:40]}]" if denom else ''
            loc = f"{city}, {st}" if city else st
            print(f"    #{i+1}: {dist:>8.1f} km  |  {safe(cname)[:42]:42s}  {safe(loc)[:28]:28s}{safe(denom_str)}")
    else:
        print(f"  (No centroid -- territory)")

# Summary
print(f"\n{'='*85}")
print(f"SUMMARY: {len(no_church)} church-free counties out of {len(all_counties):,}")
total_pop = sum(c['population'] for c in no_church.values())
print(f"Total population in church-free counties: {total_pop:,}")

from collections import Counter
by_state = Counter()
for fips, co in no_church.items():
    by_state[state_names.get(co['state_fips'], co['state_fips'])] += 1

print("\nBy state/territory:")
for st, cnt in by_state.most_common():
    pop_sum = sum(c['population'] for f, c in no_church.items() if state_names.get(c['state_fips'],'') == st)
    print(f"  {st}: {cnt} counties, {pop_sum:,} pop")

conn.close()
print("\nDone.")

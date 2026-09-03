"""
Church-Free Places Report
Shows counties with zero churches, demographics, and the nearest church.
"""
import sqlite3, math

conn = sqlite3.connect('churches.db')
conn.execute("PRAGMA journal_mode=DELETE")
conn.execute("PRAGMA synchronous=OFF")

# Get all counties from lookup
all_counties = {}
for r in conn.execute("SELECT county_fips, county_name, state_fips, population, total_adherents, adherence_rate FROM county_fips_lookup"):
    fips = r[0]
    all_counties[fips] = {
        'fips': fips, 'name': r[1] or '', 'state_fips': r[2] or '',
        'population': r[3] or 0, 'adherents': r[4] or 0, 'adherence_rate': r[5] or 0
    }

# Counties that have at least one church
church_counties = set()
for r in conn.execute("SELECT DISTINCT county_fips FROM churches WHERE county_fips IS NOT NULL AND county_fips != ''"):
    church_counties.add(r[0])

# Church-free counties
no_church = {f: all_counties[f] for f in all_counties if f not in church_counties}
print(f"Total counties: {len(all_counties):,} | With churches: {len(church_counties):,} | Church-free: {len(no_church):,}")

# Build church spatial index
print("Building spatial index...")
church_coords = []
for r in conn.execute("""
    SELECT county_fips, latitude, longitude, name, state, denomination, city
    FROM churches 
    WHERE county_fips IS NOT NULL AND county_fips != '' 
    AND latitude IS NOT NULL AND longitude IS NOT NULL
    AND latitude != 0 AND longitude != 0
"""):
    church_coords.append(r)
print(f"  {len(church_coords):,} churches indexed")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# State abbreviations lookup
state_names = {
    '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE',
    '11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA',
    '20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN',
    '28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM',
    '36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI',
    '45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA',
    '54':'WV','55':'WI','56':'WY','60':'AS','66':'GU','69':'MP','72':'PR','78':'VI'
}

# Get average church lat/lon per state for reference
state_avg = {}
for r in conn.execute("""
    SELECT state, AVG(latitude), AVG(longitude), COUNT(*) 
    FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    AND latitude != 0 AND longitude != 0
    GROUP BY state
"""):
    state_avg[r[0]] = {'lat': r[1], 'lon': r[2], 'count': r[3]}

print("\n\n=== CHURCH-FREE COUNTIES — Demographics & Nearest Church ===\n")

for fips, co in sorted(no_church.items()):
    state_fips = co['state_fips']
    state_abbr = state_names.get(state_fips, state_fips)
    
    # Reference coord: state average or US center
    if state_abbr in state_avg:
        ref_lat, ref_lon = state_avg[state_abbr]['lat'], state_avg[state_abbr]['lon']
    else:
        ref_lat, ref_lon = 39.0, -98.0
    
    # Find nearest 3 churches
    nearest = []
    for f, lat, lon, name, st, denom, city in church_coords:
        d = haversine(ref_lat, ref_lon, lat, lon)
        nearest.append((d, name, st, denom or '', city or '', lat, lon))
    
    nearest.sort(key=lambda x: x[0])
    top3 = nearest[:3]
    
    pop = co['population']
    name = co['name'] or '(unnamed)'
    rate = co['adherence_rate']
    
    print(f"{'='*80}")
    print(f"  {name}, {state_abbr}  (FIPS: {fips})")
    print(f"  Population: {pop:,}  |  Adherents: {co['adherents']:,}  |  Rate: {rate:.1f}%")
    print(f"  --- Nearest Churches ---")
    for i, (dist, cname, cst, denom, city, clat, clon) in enumerate(top3):
        denom_str = f" [{denom[:35]}]" if denom else ''
        loc = f"{city}, {cst}" if city else cst
        print(f"  #{i+1}: {dist:>8.1f} km  |  {cname[:42]:42s}  {loc[:25]:25s}{denom_str}")
    print()

# Summary
print(f"\n{'='*80}")
print(f"SUMMARY: {len(no_church)} counties with zero churches out of {len(all_counties):,}")
total_pop = sum(c['population'] for c in no_church.values())
print(f"Total population in church-free counties: {total_pop:,}")
largest = max(no_church.values(), key=lambda x: x['population'])
smallest = min(no_church.values(), key=lambda x: x['population'])
print(f"Largest church-free: {largest['name']}, {state_names.get(largest['state_fips'],'?')} ({largest['population']:,} pop)")
print(f"Smallest church-free: {smallest['name']}, {state_names.get(smallest['state_fips'],'?')} ({smallest['population']:,} pop)")

# Count by state
from collections import Counter
by_state = Counter()
for fips, co in no_church.items():
    by_state[state_names.get(co['state_fips'], co['state_fips'])] += 1
print("\nBy state/territory:")
for st, cnt in by_state.most_common():
    print(f"  {st}: {cnt}")

conn.close()

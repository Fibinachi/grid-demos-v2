"""Verify CRS for remaining unknown files."""
from pyproj import Transformer
import csv

def test_crs(fname, epsg, xcol, ycol, guess_loc):
    with open(fname, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    t = Transformer.from_crs(epsg, 'EPSG:4326', always_xy=True)
    print(f"\n=== {fname} ===")
    for r in rows[:3]:
        x, y = float(r[xcol]), float(r[ycol])
        lon, lat = t.transform(x, y)
        print(f"  {epsg}: ({lon:.4f}, {lat:.4f})  {r.get('NAME', r.get('LOCATION', r.get('PlaceOfWorshipName','')))[:40]}")

# Test various CRS for unknown files
# Places_of_Worship5 - Prince William VA - try VA North state plane
test_crs('Places_of_Worship5.csv', 'EPSG:2283', 'X', 'Y', 'Prince William VA')  # NAD83 / Virginia North (USft)
test_crs('Places_of_Worship5.csv', 'EPSG:32147', 'X', 'Y', 'Prince William VA')  # NAD83 / Virginia North (m)

# Places_of_Worship_Frederick_County - try MD state plane
test_crs('Places_of_Worship_Frederick_County.csv', 'EPSG:2248', 'X', 'Y', 'Frederick MD')  # NAD83 / Maryland (USft)
test_crs('Places_of_Worship_Frederick_County.csv', 'EPSG:2804', 'X', 'Y', 'Frederick MD')  # NAD83 / Maryland (m)

# Places_of_Worship_Mongomery_County - has LATITUDE/LONGITUDE, but test SP too
test_crs('Places_of_Worship_Mongomery_County.csv', 'EPSG:2248', 'X', 'Y', 'Montgomery MD')

# Churches_410 - Southaven MS - try MS East state plane
test_crs('Churches_4106776180121190077.csv', 'EPSG:2309', 'x', 'y', 'Southaven MS')  # NAD83 / Mississippi East (USft)
test_crs('Churches_4106776180121190077.csv', 'EPSG:3814', 'x', 'y', 'Southaven MS')  # NAD83 / Mississippi East (m)

# Places_of_Worship_746 - Kitchener ON - try UTM 17N
test_crs('Places_of_Worship_7463623507431875562.csv', 'EPSG:26917', 'x', 'y', 'Kitchener ON')

# Places_of_Worship3 - Ontario - try UTM 17N
test_crs('Places_of_Worship3.csv', 'EPSG:26917', 'X', 'Y', 'Ontario')

# Places_of_Worship2 - Ontario
test_crs('Places_of_Worship2.csv', 'EPSG:26917', 'X', 'Y', 'Ontario')

# Places_of_Worship_1730298208157311066 - Huron ON
test_crs('Places_of_Worship_1730298208157311066.csv', 'EPSG:26917', 'x', 'y', 'Huron ON')

# TU_Places - try Web Mercator & try NC state plane
test_crs('TU_Places_of_Worship.csv', 'EPSG:3857', 'X', 'Y', 'Chapel Hill NC')
test_crs('TU_Places_of_Worship.csv', 'EPSG:32119', 'X', 'Y', 'Chapel Hill NC')  # NAD83 / North Carolina (m)
test_crs('TU_Places_of_Worship.csv', 'EPSG:3357', 'X', 'Y', 'Chapel Hill NC')  # NAD83(HARN) / NC (m)

# New_Hampshire - already WGS84 as X,Y
test_crs('New_Hampshire_Places_of_Worship.csv', 'EPSG:4326', 'X', 'Y', 'New Hampshire')

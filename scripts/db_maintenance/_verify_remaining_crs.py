"""Verify CRS for remaining CSVs with known ground truth locations."""
from pyproj import Transformer
import csv

tests = [
    ('Places_of_Worship6.csv', 'Ohio', 'EPSG:3857', 'X', 'Y', 
     [(-81.6, 40.7)]),
    ('Places_of_Worship_2229927523537964322.csv', 'Worcester MA', 'EPSG:2249', 'x', 'y',
     [(-71.8, 42.3)]),
    ('OpenStreetMap_-_Place_of_Worship_(Point) India.csv', 'India OSM', 'EPSG:3857', 'X', 'Y',
     [(74.3, 21.6)]),
    ('HousesOfWorship_-1944034289557826875.csv', 'VA Houses', 'EPSG:3857', 'x', 'y',
     [(-77.1, 38.7)]),
    ('Detroit_Churches_2011.csv', 'Detroit', 'EPSG:4326', 'X', 'Y',
     [(-83.0, 42.3)]),
    ('Places_of_Worship12.csv', 'VA Places12', 'EPSG:3857', 'X', 'Y',
     [(-77.4, 38.8)]),
]

for fname, desc, crs, xcol, ycol, expected in tests:
    with open(fname, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    
    if crs != 'EPSG:4326':
        t = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)
    else:
        t = None
    
    print(f"\n=== {desc} ({fname}) ===")
    print(f"  CRS: {crs}")
    
    for i, row in enumerate(rows[:3]):
        try:
            x, y = float(row[xcol]), float(row[ycol])
            if t:
                lon, lat = t.transform(x, y)
            else:
                lon, lat = x, y
            ref_lon, ref_lat = expected[0] if expected else (None, None)
            match = ""
            if ref_lon and abs(lon - ref_lon) < 2 and abs(lat - ref_lat) < 2:
                match = " ✓"
            name = row.get('NAME', row.get('PlaceOfWorshipName', row.get('Name', row.get('ChurchName', row.get('name', '?')))))
            print(f"  [{i+1}] ({lon:.4f}, {lat:.4f})  {name[:50]}{match}")
        except Exception as e:
            print(f"  [{i+1}] ERROR: {e}")

    # Show x/y range
    xs = [float(r[xcol]) for r in rows if r.get(xcol)]
    ys = [float(r[ycol]) for r in rows if r.get(ycol)]
    if xs:
        print(f"  X range: {min(xs):.1f} - {max(xs):.1f}")
        print(f"  Y range: {min(ys):.1f} - {max(ys):.1f}")

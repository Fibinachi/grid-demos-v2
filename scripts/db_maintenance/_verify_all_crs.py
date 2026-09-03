"""Verify CRS for ArcGIS export files with known locations.""" 
from pyproj import Transformer
import csv

# File: CRS candidates: (name, expected location, lat/lon)
targets = [
    # Worcester MA - x=45K-328K, y=780K-956K - try MA mainland meters
    ('Places_of_Worship_2229927523537964322.csv', 'Worcester MA', 
     [('EPSG:26986', 42.3, -71.8, 'MA mainland m'),
      ('EPSG:2249', 42.3, -71.8, 'MA mainland ft'),
      ('EPSG:3857', 42.3, -71.8, 'Web Mercator')]),
    # Places12 - x=11.7M, y=6.8M - Haymarket VA ~ (38.8, -77.6)
    ('Places_of_Worship12.csv', 'Haymarket VA',
     [('EPSG:2283', 38.8, -77.6, 'VA North ftUS'),
      ('EPSG:2284', 38.8, -77.6, 'VA South m'),
      ('EPSG:3857', 38.8, -77.6, 'Web Mercator')]),
    # HousesOfWorship - x=11.8M, y=3.8M - also VA
    ('HousesOfWorship_-1944034289557826875.csv', 'Virginia',
     [('EPSG:2284', 38.0, -77.5, 'VA South m'),
      ('EPSG:2283', 38.0, -77.5, 'VA North ftUS'),
      ('EPSG:3857', 38.0, -77.5, 'Web Mercator')]),
    # Places5 - x=21.9M-22.6M, y=6.6M-6.9M - Prince William VA
    ('Places_of_Worship5.csv', 'Prince William VA',
     [('EPSG:2283', 38.7, -77.4, 'VA North ftUS'),
      ('EPSG:3857', 38.7, -77.4, 'Web Mercator')]),
    # Montgomery MD - x=429K-503K, y=151K-227K
    ('Places_of_Worship_Mongomery_County.csv', 'Montgomery MD',
     [('EPSG:2248', 39.1, -77.2, 'MD ft'),
      ('EPSG:3857', 39.1, -77.2, 'Web Mercator')]),
    # Frederick MD - x=380K-474K, y=99K-220K
    ('Places_of_Worship_Frederick_County.csv', 'Frederick MD',
     [('EPSG:2248', 39.4, -77.4, 'MD ft'),
      ('EPSG:3857', 39.4, -77.4, 'Web Mercator')]),
    # Places2 Ontario - x=442K-562K, y=4.7M-4.8M
    ('Places_of_Worship2.csv', 'Ontario',
     [('EPSG:26917', 43.5, -80.5, 'UTM 17N'),
      ('EPSG:3857', 43.5, -80.5, 'Web Mercator')]),
    # TU_Places Chapel Hill NC - confirmed EPSG:3857
    ('TU_Places_of_Worship.csv', 'Chapel Hill NC',
     [('EPSG:3857', 35.9, -79.1, 'Web Mercator'),
      ('EPSG:3358', 35.9, -79.1, 'NC ft')]),
    # New Hampshire - was already native lat/lon
    ('New_Hampshire_Places_of_Worship.csv', 'New Hampshire',
     [('EPSG:4326', 43.2, -71.5, 'WGS84'),
      ('EPSG:3857', 43.2, -71.5, 'Web Mercator')]),
]

for fname, desc, candidates in targets:
    try:
        with open(fname, encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"\n=== {desc} — FILE NOT FOUND ===")
        continue
    
    print(f"\n=== {desc} ({fname}) ===")
    
    for epsg, reflat, reflon, label in candidates:
        t = Transformer.from_crs(epsg, 'EPSG:4326', always_xy=True)
        
        # Find x,y cols
        cols = rows[0].keys()
        xcol = next((c for c in ['x','X'] if c in cols), None)
        ycol = next((c for c in ['y','Y'] if c in cols), None)
        
        if xcol and ycol:
            ok = 0
            total = 0
            for r in rows[:5]:
                try:
                    x, y = float(r[xcol]), float(r[ycol])
                    if x == 0 and y == 0:
                        continue
                    lon, lat = t.transform(x, y)
                    total += 1
                    if abs(lon - reflon) < 2 and abs(lat - reflat) < 2:
                        ok += 1
                except:
                    pass
            
            marker = "✓" if ok == total and total > 0 else " "
            print(f"  [{marker}] {epsg:<12s} ({label:<15s}): {ok}/{total} within 2°")
        else:
            print(f"  [ ] {epsg:<12s} ({label}): no x/y cols")

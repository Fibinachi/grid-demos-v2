"""Try more CRS options for Southaven MS churches, including UTM and coord swap."""
from pyproj import Transformer
import csv

with open('Churches_4106776180121190077.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

print(f"Total rows: {len(rows)}")
print(f"Columns: {list(rows[0].keys())}")
print()

# Sample coords from CSV (x=first col, y=second col)
for r in rows[:5]:
    print(f"  x={r['x']}, y={r['y']}  LOCATION={r.get('LOCATION','')[:50]}")
print()

x, y = float(rows[0]['x']), float(rows[0]['y'])

# Try UTM zones that cover Mississippi
tests = {
    # UTM zones
    26916: "NAD83 / UTM zone 16N (covers all MS)",
    26716: "NAD27 / UTM zone 16N",
    32616: "WGS84 / UTM zone 16N",
    # State plane - MS East (meters)
    3814: "NAD83(HARN) / MS East (m)",
    3815: "NAD83(HARN) / MS West (m)",
    # State plane - MS East (feet)
    2251: "NAD83 / MS East (ftUS)",
    2309: "NAD83 / MS East (US ft)",
    6508: "NAD83(2011) / MS East (ftUS)",
    # Try with swapped coord interpretation
}

# First: normal (x=easting, y=northing)
print("=== Normal order (x=easting, y=northing) ===")
for epsg, desc in tests.items():
    try:
        t = Transformer.from_crs(f'EPSG:{epsg}', 'EPSG:4326', always_xy=True)
        lon, lat = t.transform(x, y)
        in_range = -130 < lon < -60 and 20 < lat < 50
        marker = " ✓" if in_range else ""
        print(f"  EPSG:{epsg} ({desc}): ({lon:.4f}, {lat:.4f}){marker}")
    except Exception as e:
        print(f"  EPSG:{epsg}: ERROR {e}")

# Second: swapped (x=northing, y=easting)
print("\n=== Swapped order (x=northing, y=easting) ===")
for epsg, desc in tests.items():
    try:
        t = Transformer.from_crs(f'EPSG:{epsg}', 'EPSG:4326', always_xy=True)
        lon, lat = t.transform(y, x)  # pass y as if it were easting, x as northing
        in_range = -130 < lon < -60 and 20 < lat < 50
        marker = " ✓" if in_range else ""
        print(f"  EPSG:{epsg} ({desc}): ({lon:.4f}, {lat:.4f}){marker}")
    except Exception as e:
        print(f"  EPSG:{epsg}: ERROR {e}")

# Third: try without always_xy
print("\n=== Without always_xy (normal) ===")
for epsg, desc in tests.items():
    try:
        t = Transformer.from_crs(f'EPSG:{epsg}', 'EPSG:4326', always_xy=False)
        lon, lat = t.transform(x, y)  # source CRS expects (x, y) in its native order
        in_range = -130 < lon < -60 and 20 < lat < 50
        marker = " ✓" if in_range else ""
        print(f"  EPSG:{epsg} ({desc}): ({lon:.4f}, {lat:.4f}){marker}")
    except Exception as e:
        print(f"  EPSG:{epsg}: ERROR {e}")

# Check if coordinates might just be native lat/lon scaled
print("\n=== Native lat/lon checks ===")
print(f"  If x=lat, y=lon: ({x:.4f}, {y:.4f})")
print(f"  If x=lon, y=lat: ({y:.4f}, {x:.4f})")

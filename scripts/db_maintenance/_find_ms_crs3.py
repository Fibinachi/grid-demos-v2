"""Inverse approach: take known Southaven MS coordinates and find matching CRS."""
from pyproj import Transformer
import csv

with open('Churches_4106776180121190077.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

x, y = float(rows[0]['x']), float(rows[0]['y'])
print(f"Target: x={x:.1f}, y={y:.1f}")

# Southaven MS is around lat=34.99, lon=-90.00
# Try inverse transform for many codes
tests = {
    2227: "NAD83 / Kentucky North (ftUS)",
    2245: "NAD83 / Tennessee (ftUS)",
    2251: "NAD83 / MS East (ftUS)",
    2252: "NAD83 / MS West (ftUS)",
    2274: "NAD83 / Arkansas North (ftUS)",
    2275: "NAD83 / Arkansas South (ftUS)",
    2278: "NAD83 / Arkansas North (ftUS)",
    2309: "NAD83 / MS East (US ft)",
    26916: "NAD83 / UTM zone 16N",
    26915: "NAD83 / UTM zone 15N",
    32616: "WGS84 / UTM zone 16N",
    32615: "WGS84 / UTM zone 15N",
    3437: "NAD83 / MS East (m)",
    3438: "NAD83 / MS West (m)",
    3814: "NAD83(HARN) / MS East (m)",
    3815: "NAD83(HARN) / MS West (m)",
    6508: "NAD83(2011) / MS East (ftUS)",
    6509: "NAD83(2011) / MS West (ftUS)",
    6526: "NAD83(2011) / Tennessee (ftUS)",
}

print(f"\n--- Inverse test: transform lat=34.99, lon=-90.00 to target CRS ---")
for epsg, desc in tests.items():
    try:
        t = Transformer.from_crs('EPSG:4326', f'EPSG:{epsg}', always_xy=True)
        ex, ny = t.transform(-90.0, 34.99)
        
        # Normalize to 0-10M range for comparison
        ratio_x = ex / x if x != 0 else 0
        ratio_y = ny / y if y != 0 else 0
        
        # Check if result matches (within ~1% tolerance)
        x_ok = abs(ex - x) / x < 0.02 if x != 0 else False
        y_ok = abs(ny - y) / y < 0.02 if y != 0 else False
        
        marker = " ✓✓" if (x_ok and y_ok) else (" ✓" if (x_ok or y_ok) else "")
        print(f"  EPSG:{epsg:5d} ({desc:40s}): x={ex:>12.1f}, y={ny:>12.1f}  ratio=({ratio_x:.6f}, {ratio_y:.6f}){marker}")
    except Exception as e:
        print(f"  EPSG:{epsg:5d}: ERROR {e}")

# Also try: maybe coordinates are in feet * 100 or some scaled version
print(f"\n--- Trying scaled transforms ---")
for epsg, desc in [('2248', 'NAD83 / Maryland'), ('26917', 'NAD83 / UTM 17N'), 
                    ('3362', 'NAD83 / PA South'), ('2283', 'NAD83 / VA South ftUS')]:
    t = Transformer.from_crs('EPSG:4326', f'EPSG:{epsg}', always_xy=True)
    ex, ny = t.transform(-90.0, 34.99)
    print(f"  EPSG:{epsg:5s} ({desc:40s}): x={ex:>12.1f}, y={ny:>12.1f}")

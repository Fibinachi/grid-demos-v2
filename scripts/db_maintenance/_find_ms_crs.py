"""Find correct CRS for Churches_410 (Southaven MS)."""
from pyproj import Transformer
import csv

with open('Churches_4106776180121190077.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

x, y = float(rows[0]['x']), float(rows[0]['y'])
print(f"Test coord: ({x}, {y}) from Southaven MS")

candidates = [
    ('EPSG:2309', 'MS East USft'),
    ('EPSG:3814', 'MS East m'),
    ('EPSG:3437', 'MS East (m) NAVD88'),
    ('EPSG:3438', 'MS West (m)'),
    ('EPSG:2309', 'MS East USft long'),
    ('EPSG:2251', 'NAD83 / MS East (ftUS)'),
    ('EPSG:6508', 'NAD83(2011) / MS East (ftUS)'),
    ('EPSG:2886', 'NAD83(HARN) / MS East (ftUS)'),
    ('EPSG:2245', 'NAD83 / Tennessee (ftUS)'),  # Southaven is near TN border
    ('EPSG:2278', 'NAD83 / Arkansas North (ftUS)'),
    ('EPSG:2279', 'NAD83 / Arkansas South (ftUS)'),
]

for epsg, desc in candidates:
    try:
        t = Transformer.from_crs(epsg, 'EPSG:4326', always_xy=True)
        lon, lat = t.transform(x, y)
        ok = '✓' if (-92 <= lon <= -88 and 30 <= lat <= 36) else ''
        print(f"  {epsg:10s} ({desc:25s}): lon={lon:.4f}, lat={lat:.4f}  {ok}")
    except Exception as e:
        print(f"  {epsg:10s} ({desc:25s}): ERROR {e}")

"""Broader CRS search for Southaven MS coordinates."""
from pyproj import Transformer
import csv

with open('Churches_4106776180121190077.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

x, y = float(rows[0]['x']), float(rows[0]['y'])
print(f"Target: x={x:.1f}, y={y:.1f}")
print(f"Expected Southaven MS: ~(-90.00, 34.99)")

# Try national CRS systems
tests = {
    # National systems
    5070: "NAD83 / Conus Albers",
    5071: "NAD83 / Conus Albers (m)",
    6350: "NAD83 / Conus LCC",
    102003: "NAD83 / Albers North America (ESRI)",
    102010: "NAD83 / Lambert USA (ESRI)",
    
    # SPCS feet - more states near MS
    2245: "NAD83 / Tennessee (ftUS) [Lat 35-36.5N]",
    2274: "NAD83 / Arkansas North (ftUS)",
    2275: "NAD83 / Arkansas South (ftUS)",
    
    # SPCS meters
    26915: "NAD83 / UTM 15N",
    26916: "NAD83 / UTM 16N", 
    
    # Old projections  
    4269: "NAD83 (geographic 2D)",
    4326: "WGS84 (geographic 2D)",
    
    # State plane - try feet with coord swap
    2251: "NAD83 / MS East (ftUS)",
    2252: "NAD83 / MS West (ftUS)",
    2309: "NAD83 / MS East (US ft)",
    
    # More national
    2163: "US National Atlas Equal Area",
    102001: "USA Contiguous Albers (ESRI)",
}

print(f"\n{'CRS':30s} {'Forward':40s} {'Inverse from SA MS':40s}")
print(f"{'':30s} {'(x→4326)':40s} {'(4326→CRS)':40s}")
print("="*110)

for epsg, desc in tests.items():
    try:
        # Forward: raw coords → lat/lon
        t_fwd = Transformer.from_crs(f'EPSG:{epsg}', 'EPSG:4326', always_xy=True)
        lon, lat = t_fwd.transform(x, y)
        
        # Inverse: Southaven lat/lon → CRS
        t_inv = Transformer.from_crs('EPSG:4326', f'EPSG:{epsg}', always_xy=True)
        ex, ny = t_inv.transform(-90.0, 34.99)
        
        # Check if forward gives something reasonable near US
        fwd_close = (20 < lat < 50) and (-130 < lon < -60)
        inv_close = abs(ex - x) / x < 0.5 and abs(ny - y) / y < 0.5
        
        fwd_mark = "✓" if fwd_close else " "
        inv_mark = "✓" if inv_close else " "
        
        print(f"EPSG:{epsg:<5d} {desc:<20s} [{fwd_mark}] lon={lon:>8.3f}, lat={lat:>7.3f}  |  [{inv_mark}] x={ex:>12.1f}, y={ny:>10.1f}")
    except Exception as e:
        print(f"EPSG:{epsg:<5d} {desc:<20s} ERROR: {e}")

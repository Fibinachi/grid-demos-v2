"""
Phase 1: Inventory churches missing addresses by country vs available postal codes.
Determine which countries will benefit most from postal code backfill.
"""
import sqlite3, os

DB = r'e:\grid\churches.db'

# Available postal code files
pc_dir = r'e:\grid\data\geonames_postal'
pc_countries = set()
for f in os.listdir(pc_dir):
    if f.endswith('.txt'):
        pc_countries.add(f[:2].upper())

print(f"Postal code data available for {len(pc_countries)} countries:")
print(', '.join(sorted(pc_countries)))

db = sqlite3.connect(DB)

# Check: do churches have a postal_code or zip column?
churches_cols = [r[1] for r in db.execute('PRAGMA table_info(churches)')]
has_zip = 'postal_code' in churches_cols or 'zip' in churches_cols or 'postcode' in churches_cols
print(f"\nPostal/zip column on churches: {[c for c in churches_cols if any(w in c.lower() for w in ['zip','postal','postcode'])]}")

# Country-level address gaps (excluding US, including only countries with postal data)
print("\n=== ADDRESS GAPS BY COUNTRY (with postal data) ===")
print(f"{'Country':<6} {'Total':>8} {'Addr':>8} {'Addr%':>6} {'City':>8} {'City%':>6} {'State':>8} {'State%':>6} {'GPS':>8} {'GPS%':>6}")

for country in sorted(pc_countries - {'US'}):
    total = db.execute("SELECT COUNT(*) FROM churches WHERE country=?", (country,)).fetchone()[0]
    if total < 100:
        continue
    
    addr = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND address IS NOT NULL AND address != ''", (country,)).fetchone()[0]
    city = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND city IS NOT NULL AND city != ''", (country,)).fetchone()[0]
    state = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND state IS NOT NULL AND state != ''", (country,)).fetchone()[0]
    gps = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND latitude IS NOT NULL AND latitude != 0", (country,)).fetchone()[0]
    
    print(f"{country:<6} {total:>8,} {addr:>8,} {100*addr/total:>5.0f}% {city:>8,} {100*city/total:>5.0f}% {state:>8,} {100*state/total:>5.0f}% {gps:>8,} {100*gps/total:>5.0f}%")

# Also check if churches have a 'postal_code' column
# GeoNames postal files have: country, postal_code, place_name, admin1, admin2, admin3, lat, lon, accuracy
print("\n=== GEONAMES POSTAL FORMAT ===")
sample_file = os.path.join(pc_dir, 'GB.txt')
if os.path.exists(sample_file):
    with open(sample_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < 3:
                parts = line.strip().split('\t')
                print(f"  {parts}")
            else:
                break

db.close()

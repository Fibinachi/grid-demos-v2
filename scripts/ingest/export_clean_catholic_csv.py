"""Export clean Catholic directory data from catholic_directory.db to CSV."""
import sqlite3
import csv
from pathlib import Path

OUTPUT_DIR = Path("E:/grid/data/denom")

db = sqlite3.connect('E:/grid/data/catholic_directory.db')

# Get years and counts
years = db.execute('SELECT DISTINCT directory_year FROM dir_entries ORDER BY directory_year').fetchall()
print(f"Years in database: {[y[0] for y in years]}")

# Export all data with church/parish entity types
rows = db.execute('''
    SELECT directory_year, name, city, state, diocese, entity_type, 
           latitude, longitude, source_raw
    FROM dir_entries 
    WHERE directory_year IN (1865, 1868, 2021)
    ORDER BY directory_year, diocese, city
''').fetchall()

csv_path = OUTPUT_DIR / "catholic_directory_parsed_clean.csv"
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['year', 'name', 'city', 'state', 'diocese', 'entity_type', 'latitude', 'longitude', 'source_raw'])
    for row in rows:
        w.writerow(row)

print(f"Exported {len(rows):,} entries to {csv_path}")
db.close()

# Also get the 1938 and 1944 data which has fewer issues
db2 = sqlite3.connect('E:/grid/data/catholic_directory.db')
for year in [1938, 1944]:
    rows = db2.execute(f'''
        SELECT directory_year, name, city, state, diocese, entity_type, latitude, longitude
        FROM dir_entries 
        WHERE directory_year = {year} AND entity_type IN ('parish', 'cathedral', 'mission', 'chapel')
        ORDER BY diocese, city
    ''').fetchall()
    
    csv_path = OUTPUT_DIR / f"catholic_directory_{year}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['year', 'name', 'city', 'state', 'diocese', 'entity_type', 'latitude', 'longitude'])
        for row in rows:
            w.writerow(row)
    
    print(f"Exported {len(rows):,} entries from {year} to {csv_path}")

db2.close()
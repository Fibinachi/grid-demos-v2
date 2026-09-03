"""
import_building_sqft.py — Import church_building_sqft_us CSV into SQLite.
Creates local table with building area, parking estimates, and distance metadata.
"""
import csv, sqlite3, sys, os, time

# Project root is 2 levels up from scripts/db_maintenance/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
from gw_db import connect as get_db

CSV_PATH = r'E:\grid\data\church_building_sqft_us.csv'
CHUNK_SIZE = 500


def main():
    if not os.path.exists(CSV_PATH):
        print(f'ERROR: CSV not found at {CSV_PATH}')
        print('Run run_us_footprint_pipeline.py first to generate it.')
        sys.exit(1)

    file_size = os.path.getsize(CSV_PATH) / (1024 * 1024)
    print(f'CSV: {CSV_PATH} ({file_size:.1f} MB)')

    db = get_db()
    c = db.cursor()

    # Drop old table if exists
    c.execute('DROP TABLE IF EXISTS church_building_sqft_us')
    db.commit()

    # Create table matching CSV schema
    c.execute('''
        CREATE TABLE church_building_sqft_us (
            church_id INTEGER PRIMARY KEY,
            name TEXT,
            city TEXT,
            state TEXT,
            tradition TEXT,
            faith TEXT,
            taxonomy_id INTEGER,
            latitude REAL,
            longitude REAL,
            building_area_m2 REAL,
            building_area_sqft REAL,
            distance_m REAL,
            point_in_building INTEGER,
            building_source TEXT,
            parking_estimate_spots INTEGER
        )
    ''')
    db.commit()

    # Count rows first
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        total = sum(1 for _ in f) - 1  # minus header
    print(f'Importing {total:,} rows...')

    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        batch = []
        t0 = time.time()

        for i, row in enumerate(reader):
            batch.append((
                int(float(row['church_id'])),
                row['name'],
                row['city'],
                row['state'],
                row['tradition'],
                row['faith'],
                int(float(row['taxonomy_id'])) if row.get('taxonomy_id') else None,
                float(row['latitude']) if row['latitude'] else None,
                float(row['longitude']) if row['longitude'] else None,
                float(row['building_area_m2']) if row['building_area_m2'] else None,
                float(row['building_area_sqft']) if row['building_area_sqft'] else None,
                float(row['distance_m']) if row['distance_m'] else None,
                1 if row.get('point_in_building') == 'true' else 0,
                row.get('building_source', 'overture'),
                int(float(row['parking_estimate_spots'])) if row.get('parking_estimate_spots') else None,
            ))

            if len(batch) >= CHUNK_SIZE:
                c.executemany('''
                    INSERT OR REPLACE INTO church_building_sqft_us 
                    (church_id, name, city, state, tradition, faith, taxonomy_id,
                     latitude, longitude, building_area_m2, building_area_sqft,
                     distance_m, point_in_building, building_source, parking_estimate_spots)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', batch)
                db.commit()
                batch = []

                if (i + 1) % 100000 == 0:
                    elapsed = time.time() - t0
                    rate = (i + 1) / elapsed
                    pct = (i + 1) / total * 100
                    print(f'  {i+1:,}/{total:,} ({pct:.1f}%) | {rate:.0f} rows/s')

        # Final batch
        if batch:
            c.executemany('''
                INSERT OR REPLACE INTO church_building_sqft_us 
                (church_id, name, city, state, tradition, faith, taxonomy_id,
                 latitude, longitude, building_area_m2, building_area_sqft,
                 distance_m, point_in_building, building_source, parking_estimate_spots)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', batch)
            db.commit()

    elapsed = time.time() - t0
    print(f'  Done: {total:,} rows in {elapsed:.0f}s ({total/elapsed:.0f} rows/s)')

    # Create indexes
    print('Creating indexes...')
    c.execute('CREATE INDEX IF NOT EXISTS idx_bldg_state ON church_building_sqft_us(state)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_bldg_tradition ON church_building_sqft_us(tradition)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_bldg_sqft ON church_building_sqft_us(building_area_sqft)')
    db.commit()

    # Stats
    print()
    c.execute('SELECT COUNT(*) FROM church_building_sqft_us')
    count = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM church_building_sqft_us WHERE building_area_sqft > 0')
    with_sqft = c.fetchone()[0]
    c.execute('SELECT ROUND(AVG(building_area_sqft),0) FROM church_building_sqft_us WHERE building_area_sqft > 0')
    avg_sqft = c.fetchone()[0]
    c.execute('SELECT ROUND(AVG(parking_estimate_spots),0) FROM church_building_sqft_us WHERE parking_estimate_spots > 0')
    avg_parking = c.fetchone()[0]

    print(f'Total rows: {count:,}')
    print(f'With building sqft: {with_sqft:,} ({with_sqft/count*100:.1f}%)')
    print(f'Avg building sqft: {avg_sqft:,.0f}')
    print(f'Avg parking estimate: {avg_parking:.0f} spots')
    print()
    print('church_building_sqft_us imported successfully!')

    db.close()


if __name__ == '__main__':
    main()

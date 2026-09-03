"""
Phase 1: Import all GeoNames postal code data into SQLite table.
Phase 2: For churches with GPS but missing address/city/state, find nearest postal code.
Phase 3: Backfill.

GeoNames postal format (tab-separated):
country_code, postal_code, place_name, admin1_name, admin1_code, admin2_name, admin2_code,
admin3_name, admin3_code, latitude, longitude, accuracy

Skips US (another agent working on it).
"""
import sqlite3, os, time, math
from collections import defaultdict

DB = r'e:\grid\churches.db'
PC_DIR = r'e:\grid\data\geonames_postal'

def import_postal_codes():
    """Import all GeoNames postal code files into a geonames_postal table."""
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=OFF')
    
    # Check if already imported
    existing = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='geonames_postal'").fetchone()[0]
    if existing:
        cnt = db.execute("SELECT COUNT(*) FROM geonames_postal").fetchone()[0]
        print(f"geonames_postal already exists with {cnt:,} rows. Dropping and re-importing...")
        db.execute("DROP TABLE geonames_postal")
    
    db.execute("""
        CREATE TABLE geonames_postal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_code TEXT NOT NULL,
            postal_code TEXT NOT NULL,
            place_name TEXT,
            admin1_name TEXT,
            admin1_code TEXT,
            admin2_name TEXT,
            admin2_code TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy INTEGER
        )
    """)
    
    total_imported = 0
    CHUNK = 2000
    
    for fname in sorted(os.listdir(PC_DIR)):
        if not fname.endswith('.txt') or fname == 'readme.txt':
            continue
        
        country = fname[:2].upper()
        if country == 'US':
            continue
        
        fpath = os.path.join(PC_DIR, fname)
        fsize = os.path.getsize(fpath)
        if fsize == 0:
            continue
        
        print(f"  {country}: reading {fname} ({fsize/1024:.0f} KB)...", end=' ', flush=True)
        
        batch = []
        count = 0
        skipped = 0
        
        with open(fpath, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 11:
                    skipped += 1
                    continue
                
                try:
                    lat = float(parts[9])
                    lon = float(parts[10])
                    if lat == 0 and lon == 0:
                        skipped += 1
                        continue
                    
                    accuracy = int(parts[11]) if len(parts) > 11 and parts[11] else 0
                    
                    batch.append((
                        parts[0],      # country_code
                        parts[1],      # postal_code
                        parts[2],      # place_name
                        parts[3] if len(parts) > 3 else '',  # admin1_name
                        parts[4] if len(parts) > 4 else '',  # admin1_code
                        parts[5] if len(parts) > 5 else '',  # admin2_name
                        parts[6] if len(parts) > 6 else '',  # admin2_code
                        lat, lon, accuracy
                    ))
                    
                    if len(batch) >= CHUNK:
                        db.executemany(
                            "INSERT INTO geonames_postal (country_code,postal_code,place_name,admin1_name,admin1_code,admin2_name,admin2_code,latitude,longitude,accuracy) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            batch
                        )
                        count += len(batch)
                        batch = []
                except (ValueError, IndexError):
                    skipped += 1
        
        if batch:
            db.executemany(
                "INSERT INTO geonames_postal (country_code,postal_code,place_name,admin1_name,admin1_code,admin2_name,admin2_code,latitude,longitude,accuracy) VALUES (?,?,?,?,?,?,?,?,?,?)",
                batch
            )
            count += len(batch)
        
        db.commit()
        total_imported += count
        print(f"{count:,} rows (skipped {skipped})")
    
    # Create indexes
    print("\nCreating indexes...")
    db.execute("CREATE INDEX IF NOT EXISTS idx_gp_latlon ON geonames_postal(latitude, longitude)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_gp_country ON geonames_postal(country_code)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_gp_postal ON geonames_postal(country_code, postal_code)")
    db.commit()
    
    print(f"Total imported: {total_imported:,} postal codes")
    
    # Country stats
    print("\nPostal codes by country (top 20):")
    for r in db.execute("""
        SELECT country_code, COUNT(*) as cnt 
        FROM geonames_postal 
        GROUP BY country_code 
        ORDER BY cnt DESC 
        LIMIT 20
    """).fetchall():
        print(f"  {r[0]}: {r[1]:,}")
    
    db.close()
    return total_imported

if __name__ == '__main__':
    import_postal_codes()

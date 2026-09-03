#!/usr/bin/env python3
"""
Import German postal codes from GeoNames and join to churches.

GeoNames DE postal data format (tab-separated):
country | postal_code | place_name | admin1 | admin1_code | admin2 | admin2_code | admin3 | admin3_code | lat | lon

Creates: postal_codes_de table and joins to churches via spatial matching.
"""
import sqlite3
from pathlib import Path
from datetime import datetime

DB = Path(r'E:\grid\churches.db')
POSTAL_FILE = Path(r'E:\grid\data\geonames_de_postal\DE.txt')

def main():
    db = sqlite3.connect(str(DB))
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()

    # Create postal codes table
    c.execute("DROP TABLE IF EXISTS postal_codes_de")
    c.execute("""
        CREATE TABLE postal_codes_de (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            postal_code TEXT NOT NULL,
            place_name TEXT,
            admin1_name TEXT,
            admin1_code TEXT,
            admin2_name TEXT,
            admin2_code TEXT,
            admin3_name TEXT,
            admin3_code TEXT,
            latitude REAL,
            longitude REAL,
            UNIQUE(postal_code, place_name)
        )
    """)

    # Import postal codes
    print("Importing DE postal codes from GeoNames...")
    inserted = 0
    with open(POSTAL_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 10:
                continue
            c.execute("""
                INSERT OR IGNORE INTO postal_codes_de 
                (postal_code, place_name, admin1_name, admin1_code, admin2_name, admin2_code, admin3_name, admin3_code, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7], parts[8], parts[9], parts[10]))
            inserted += 1
            if inserted % 5000 == 0:
                print(f"  {inserted:,} rows...")

    db.commit()
    print(f"  {inserted:,} postal codes imported")

    # Create spatial index
    c.execute("CREATE INDEX IF NOT EXISTS idx_postal_codes_de_ll ON postal_codes_de(latitude, longitude)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_postal_codes_de_code ON postal_codes_de(postal_code)")

    # Join to churches: find nearest postal code for each DE church without a zip
    print("\nJoining postal codes to DE churches without zip...")
    c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE country='DE' AND (zip IS NULL OR zip = '')
    """)
    need_zip = c.fetchone()[0]
    print(f"  DE churches missing zip: {need_zip:,}")

    # Use a simple approach: find churches whose lat/lon is within 0.5 degrees of a postal code
    # and join by admin1_name match
    updated = 0
    c.execute("""
        SELECT c.id, c.latitude, c.longitude, c.admin1_name
        FROM churches c
        WHERE c.country = 'DE' 
          AND (c.zip IS NULL OR c.zip = '')
          AND c.latitude IS NOT NULL
    """)
    churches = c.fetchall()
    print(f"  Processing {len(churches):,} churches...")

    for i, (ch_id, ch_lat, ch_lon, ch_admin1) in enumerate(churches):
        if i % 5000 == 0:
            print(f"  {i:,}/{len(churches):,}...")
        
        c.execute("""
            SELECT postal_code, place_name FROM postal_codes_de
            WHERE latitude BETWEEN ? AND ?
              AND longitude BETWEEN ? AND ?
              AND (? IS NULL OR admin1_name = ?)
            ORDER BY (ABS(latitude - ?) + ABS(longitude - ?))
            LIMIT 1
        """, (ch_lat - 0.05, ch_lat + 0.05, ch_lon - 0.05, ch_lon + 0.05,
              ch_admin1, ch_admin1, ch_lat, ch_lon))
        
        row = c.fetchone()
        if row:
            c.execute("UPDATE churches SET zip = ?, city = COALESCE(NULLIF(city,''), ?) WHERE id = ?",
                     (row[0], row[1], ch_id))
            updated += 1

    db.commit()
    print(f"  Zips updated: {updated:,}")

    # Summary
    c.execute("SELECT COUNT(*) FROM churches WHERE country='DE' AND zip IS NOT NULL AND zip != ''")
    final = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE country='DE'")
    total_de = c.fetchone()[0]
    print(f"\n  DE churches with zip: {final:,}/{total_de:,} ({final/total_de*100:.1f}%)")

    # Catalog
    c.execute("SELECT COUNT(*) FROM postal_codes_de")
    pc_count = c.fetchone()[0]
    c.execute("""
        INSERT OR REPLACE INTO church_census_catalog (country, table_name, category, description, geo_unit, row_count, source_date)
        VALUES ('DE', 'postal_codes_de', 'geography', 'GeoNames DE postal codes with lat/lon', 'PLZ', ?, '2026-07-08')
    """, (pc_count,))

    db.commit()
    db.close()
    print("Done.")

if __name__ == '__main__':
    main()

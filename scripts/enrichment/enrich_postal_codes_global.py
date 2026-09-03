#!/usr/bin/env python3
"""
Batch enrich all countries with postal codes from GeoNames.

Checks which countries have low ZIP coverage, downloads the corresponding
GeoNames postal code files, and joins them to churches via spatial matching.

Run: python scripts/enrichment/enrich_postal_codes_global.py
"""
import sqlite3, urllib.request, io, zipfile, os, sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DB = Path(r'E:\grid\churches.db')
DATA_DIR = Path(r'E:\grid\data\geonames_postal')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# GeoNames country codes with available postal data
# Source: https://download.geonames.org/export/zip/
GEONAMES_COUNTRIES = {
    'AR', 'AT', 'AU', 'BD', 'BE', 'BG', 'BR', 'CA', 'CH', 'CL', 'CN',
    'CZ', 'DE', 'DK', 'EG', 'ES', 'FI', 'FR', 'GB', 'GR', 'GT', 'HR',
    'HU', 'ID', 'IE', 'IN', 'IT', 'JP', 'KR', 'MX', 'MY', 'NG', 'NL',
    'NO', 'NZ', 'PH', 'PL', 'PT', 'RO', 'RS', 'RU', 'SA', 'SE', 'SG',
    'TH', 'TR', 'TW', 'UA', 'US', 'VN', 'ZA',
}

def progress_bar(i, total, label='', width=30):
    pct = (i + 1) / total if total else 1
    filled = int(width * pct)
    bar = chr(9608) * filled + chr(9617) * (width - filled)
    print(f'\r  {label} [{bar}] {pct*100:.0f}% ({i+1}/{total})', end='', flush=True)

def main():
    db = sqlite3.connect(str(DB))
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()

    print("GLOBAL POSTAL CODE ENRICHMENT")
    print("=" * 60)

    # Step 1: Find countries with churches but low ZIP coverage
    print("\n-- Identifying countries with ZIP gaps --")
    c.execute("""
        SELECT country, COUNT(*) as total,
               SUM(CASE WHEN zip IS NOT NULL AND zip != '' THEN 1 ELSE 0 END) as zipped
        FROM churches
        WHERE country IS NOT NULL AND country != ''
          AND latitude IS NOT NULL AND latitude != 0
        GROUP BY country
        HAVING zipped * 1.0 / total < 0.95
        ORDER BY total DESC
    """)

    needs_enrichment = []
    for country, total, zipped in c.fetchall():
        pct = zipped / total * 100
        if country in GEONAMES_COUNTRIES and total >= 100:
            needs_enrichment.append((country, total, zipped, pct))
            print(f"  {country}: {total:,} churches, only {pct:.0f}% with ZIP")

    if not needs_enrichment:
        print("  All countries at >95% ZIP coverage!")
        db.close()
        return

    # Step 2: Ensure geonames_postal table is populated
    c.execute("SELECT COUNT(*) FROM geonames_postal")
    existing = c.fetchone()[0]
    print(f"\n  geonames_postal table: {existing:,} existing rows")

    # Step 3: For each country, download if not already in geonames_postal
    to_download = []
    for country, total, zipped, pct in needs_enrichment:
        c.execute("SELECT COUNT(*) FROM geonames_postal WHERE country_code=?", (country,))
        if c.fetchone()[0] == 0:
            to_download.append(country)

    if to_download:
        print(f"\n-- Downloading {len(to_download)} country postal files --")
        for i, country in enumerate(to_download):
            progress_bar(i, len(to_download), f'Downloading {country}')
            url = f'https://download.geonames.org/export/zip/{country}.zip'
            zip_path = DATA_DIR / f'{country}.zip'
            
            if not zip_path.exists() or zip_path.stat().st_size < 100:
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        zip_path.write_bytes(resp.read())
                except Exception as e:
                    print(f'\n    FAILED {country}: {e}')
                    continue

            # Import into geonames_postal
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    txt_name = [n for n in zf.namelist() if n.endswith('.txt')][0]
                    with zf.open(txt_name) as f:
                        for line in io.TextIOWrapper(f, encoding='utf-8'):
                            parts = line.strip().split('\t')
                            if len(parts) >= 10:
                                try:
                                    c.execute("""
                                        INSERT OR IGNORE INTO geonames_postal
                                        (country_code, postal_code, place_name, admin1_name, admin1_code,
                                         admin2_name, admin2_code, latitude, longitude)
                                        VALUES (?,?,?,?,?,?,?,?,?)
                                    """, (parts[0], parts[1], parts[2], parts[3], parts[4],
                                          parts[5], parts[6], float(parts[9]) if parts[9] else None,
                                          float(parts[10]) if parts[10] else None))
                                except:
                                    pass
                db.commit()
            except Exception as e:
                print(f'\n    IMPORT FAILED {country}: {e}')

        print(f'\n  Done downloading')

    # Step 4: Join postal codes to churches
    print(f"\n-- Joining postal codes to churches --")
    total_updated = 0
    for i, (country, total, zipped, pct) in enumerate(needs_enrichment):
        progress_bar(i, len(needs_enrichment), f'  {country}')

        # Find churches in this country without zip
        c.execute("""
            SELECT id, latitude, longitude FROM churches
            WHERE country = ? AND (zip IS NULL OR zip = '')
              AND latitude IS NOT NULL AND latitude != 0
        """, (country,))
        churches = c.fetchall()
        if not churches:
            continue

        updated = 0
        for ch_id, lat, lon in churches:
            # Find nearest postal code within ~5km
            c.execute("""
                SELECT postal_code FROM geonames_postal
                WHERE country_code = ? AND latitude IS NOT NULL
                  AND latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
                ORDER BY (ABS(latitude - ?) + ABS(longitude - ?))
                LIMIT 1
            """, (country, lat - 0.05, lat + 0.05, lon - 0.05, lon + 0.05, lat, lon))
            
            row = c.fetchone()
            if row:
                c.execute("UPDATE churches SET zip = ? WHERE id = ?", (row[0], ch_id))
                updated += 1

        if updated:
            db.commit()
            total_updated += updated
            print(f'\n    {country}: {updated:,} zips added')

    print(f'\n  Total zips added: {total_updated:,}')

    # Step 5: Final summary
    print(f"\n{'='*60}")
    print("FINAL ZIP COVERAGE")
    print(f"{'='*60}")
    c.execute("""
        SELECT country, COUNT(*) as total,
               SUM(CASE WHEN zip IS NOT NULL AND zip != '' THEN 1 ELSE 0 END) as zipped
        FROM churches WHERE country IS NOT NULL AND country != ''
        GROUP BY country ORDER BY total DESC LIMIT 20
    """)
    for country, total, zipped in c.fetchall():
        pct = zipped / total * 100
        bar = chr(9608) * int(pct / 5) + chr(9617) * (20 - int(pct / 5))
        print(f"  {country:5s} [{bar}] {pct:5.1f}% ({zipped:,}/{total:,})")

    db.close()
    print("\nDone.")

if __name__ == '__main__':
    main()

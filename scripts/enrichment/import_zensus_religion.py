#!/usr/bin/env python3
"""
Import Zensus 2022 religion data and join to DE churches.

Reads the flat CSV export from ergebnisse.zensus2022.de (table 1000A-1018)
at Bundesland level and creates zensus_religion_de with state-level religion stats.
Joins to churches via admin1_name.

To get Gemeinde-level: In the Zensus portal, change the regional filter from 
"Bundesländer" to "Gemeinden" before downloading. The flat CSV will then have 
GEOG1 codes instead of GEOBL1, giving ~11,000 Gemeinde rows with AGS codes.
"""
import csv, io, zipfile, sqlite3
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DB = Path(r'E:\grid\churches.db')
FLAT_ZIP = Path(r'E:\grid\1000A-1018_de_flat.zip')

def main():
    # Parse flat CSV
    with open(FLAT_ZIP, 'rb') as f:
        zf = zipfile.ZipFile(io.BytesIO(f.read()))
        data = zf.read('1000A-1018_de_flat.csv').decode('utf-8-sig')

    reader = csv.DictReader(io.StringIO(data), delimiter=';')
    rows = list(reader)

    # Determine geo level
    geo_code = rows[0].get('1_variable_code', '')
    geo_label = rows[0].get('1_variable_label', '')
    print(f"Geographic level: {geo_code} ({geo_label})")

    # Parse into structured data
    state_data = defaultdict(dict)
    for r in rows:
        geo_name = r.get('1_variable_attribute_label', '')
        geo_code_val = r.get('1_variable_attribute_code', '')
        if not geo_name or geo_name == 'Deutschland':
            continue
        religion = r.get('2_variable_attribute_label', 'Insgesamt')
        val = int(r.get('value', '0')) if r.get('value', '').isdigit() else 0
        unit = r.get('value_unit', '')

        if unit == 'Anzahl':
            state_data[geo_name][religion] = val
            state_data[geo_name]['_code'] = geo_code_val

    # Import to DB
    db = sqlite3.connect(str(DB))
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()

    c.execute("DROP TABLE IF EXISTS zensus_religion_de")
    c.execute("""
        CREATE TABLE zensus_religion_de (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            geo_level TEXT DEFAULT 'Bundesland',
            geo_code TEXT,
            geo_name TEXT NOT NULL,
            total_population INTEGER,
            protestant_count INTEGER,
            protestant_pct REAL,
            catholic_count INTEGER,
            catholic_pct REAL,
            other_none_count INTEGER,
            other_none_pct REAL,
            source TEXT DEFAULT 'zensus2022_1000A-1018',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(geo_level, geo_code)
        )
    """)

    inserted = 0
    for state_name, d in sorted(state_data.items()):
        total = d.get('Insgesamt', 0)
        prot = d.get('Evangelische Kirche (öffentlich-rechtlich)', 0)
        cath = d.get('Römisch-katholische Kirche (öffentlich-rechtlich)', 0)
        other = d.get('Sonstige, keine, ohne Angabe', 0)

        if total == 0:
            continue

        c.execute("""
            INSERT OR REPLACE INTO zensus_religion_de (geo_level, geo_code, geo_name,
                total_population, protestant_count, protestant_pct,
                catholic_count, catholic_pct, other_none_count, other_none_pct)
            VALUES ('Bundesland', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (d['_code'], state_name, total, prot, round(prot/total*100, 1),
              cath, round(cath/total*100, 1), other, round(other/total*100, 1)))
        inserted += 1

    print(f"Inserted {inserted} states into zensus_religion_de")

    # Show enrichment potential: join to churches
    c.execute("""
        SELECT c.name, c.city, z.geo_name, z.total_population, z.protestant_pct, z.catholic_pct
        FROM churches c
        JOIN zensus_religion_de z ON c.admin1_name = z.geo_name
        WHERE c.country = 'DE'
        LIMIT 10
    """)
    print("\n=== Sample enriched churches ===")
    print(f"{'Church':40s} | {'City':20s} | State Pop | %Prot | %Cath")
    print("-" * 90)
    for r in c.fetchall():
        name = (r[0] or 'N/A')[:40]
        city = (r[1] or 'N/A')[:20]
        print(f"{name:40s} | {city:20s} | {r[3]:>9,d} | {r[4]:4.1f}% | {r[5]:4.1f}%")

    # Count coverage
    c.execute("""
        SELECT COUNT(*) FROM churches WHERE country='DE' 
        AND admin1_name IN (SELECT geo_name FROM zensus_religion_de)
    """)
    matched = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE country='DE'")
    total = c.fetchone()[0]
    print(f"\nCoverage: {matched:,}/{total:,} DE churches enriched ({matched/total*100:.1f}%)")

    # Update catalog
    c.execute("""
        INSERT OR REPLACE INTO church_census_catalog (country, table_name, category, description, geo_unit, row_count, source_date)
        VALUES ('DE', 'zensus_religion_de', 'demographics', 'Zensus 2022 religion by Bundesland', 'Bundesland', ?, '2026-07-08')
    """, (inserted,))

    db.commit()
    db.close()
    print("Done.")

if __name__ == '__main__':
    main()

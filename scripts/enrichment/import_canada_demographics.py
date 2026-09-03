#!/usr/bin/env python3
"""
Import Canada 2021 Census demographics into church_census_ca.

Source: Statistics Canada 2021 Profile (98-401-X2021004)
  Downloaded by download_canada_census.py
  Extracted to data/canada_census/98-401-X2021004_English_CSV_data.csv

Format: EAV (Entity-Attribute-Value) long form
  - DGUID = Dissemination Area
  - CHARACTERISTIC_ID = what stat this is
  - C1_COUNT_TOTAL = value

This imports key demographics and joins them to church_census_ca.

Usage:
    python scripts/enrichment/import_canada_demographics.py
"""
import csv
import sqlite3
import os
from datetime import datetime

DB = r'E:\grid\churches.db'
CSV_PATH = r'E:\grid\data\canada_census\98-401-X2021004_English_CSV_data.csv'

# Key characteristic IDs to extract (top-level profile summaries)
KEY_CHARS = {
    1:   ('total_pop',            'Population, 2021'),
    2:   ('male_pop',             '  Male'),
    3:   ('female_pop',           '  Female'),
    47:  ('median_age',           '  Median age'),
    56:  ('avg_age',              '  Average age'),
    58:  ('pop_0_14',             '  0 to 14 years'),
    63:  ('pop_15_64',            '  15 to 64 years'),
    69:  ('pop_65_plus',          '  65 years and over'),
    74:  ('pop_85_plus',          '  85 years and over'),
    53:  ('married_pop',          '  Married or common-law'),
    60:  ('total_dwellings',      'Total - Occupied private dwellings'),
    66:  ('avg_household_size',   'Average household size'),
    1414: ('median_income_2020',  'Median total income in 2020'),
    1978: ('no_certificate',      '  No certificate, diploma or degree'),
    1991: ('high_school',         '  High school or equivalent'),
    1994: ('postsecondary',       '  Postsecondary certificate, diploma or degree'),
    2010: ('bachelors_plus',      '  University certificate'),
    2143: ('unemployment_rate',   '  Unemployment rate'),
    342:  ('pop_density',         'Population density per sq km'),
    43:   ('total_immigrants',    'Total - Immigrant status'),
    44:   ('non_immigrants',      '  Non-immigrants'),
    45:   ('immigrants',          '  Immigrants'),
    46:   ('recent_immigrants',   '  Recent immigrants (2016-2021)'),
    51:   ('citizens',            'Canadian citizens'),
    655:  ('total_visible_minority', 'Total visible minority population'),
    248:  ('indigenous_pop',      'Indigenous identity'),
    145:  ('mother_tongue_eng',   'English'),
    146:  ('mother_tongue_fr',    'French'),
    147:  ('mother_tongue_other', 'Non-official language'),
    1417: ('income_under_10k',    'Under $10,000'),
    1424: ('income_100k_plus',    '$100,000 and over'),
    355:  ('owner_households',    '  Owner'),
    356:  ('renter_households',   '  Renter'),
    1714: ('employed',            '  Employed'),
    1720: ('unemployed',          '  Unemployed'),
    1740: ('labor_participation', 'Total - Labour force aged 15+'),
}


def main():
    # ═══ Step 1: Read CSV and pivot by DGUID ═══════════════════════════
    if not os.path.exists(CSV_PATH):
        print(f'FATAL: Census CSV not found at {CSV_PATH}')
        print('Run download_canada_census.py first and extract the ZIP')
        return

    file_mb = os.path.getsize(CSV_PATH) / 1024 / 1024
    print(f'Reading census CSV ({file_mb:.0f} MB)...')

    dao_data = {}  # dguid → {col_name: value}
    char_ids = set(str(c) for c in KEY_CHARS)
    processed = 0

    with open(CSV_PATH, encoding='latin-1') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get('CHARACTERISTIC_ID', '').strip()
            if cid not in char_ids:
                continue
            dguid = row.get('DGUID', '').strip()
            if not dguid:
                continue
            glevel = row.get('GEO_LEVEL', '').strip()
            if glevel != '4':  # DA level only
                continue

            col_name = KEY_CHARS[int(cid)][0]
            try:
                val = float(row.get('C1_COUNT_TOTAL', '0') or '0')
            except ValueError:
                val = None

            if dguid not in dao_data:
                dao_data[dguid] = {}
            dao_data[dguid][col_name] = val
            processed += 1

    print(f'  Processed {processed:,} rows → {len(dao_data):,} DAs')

    # ═══ Step 2: Join to church_census_ca via DAUID ═══════════════════
    db = sqlite3.connect(DB, timeout=60)
    db.execute('PRAGMA journal_mode=WAL')

    # Build DAUID → DGUID mapping from church_census_ca
    da_map = dict(db.execute(
        "SELECT da_dguid, church_rowid FROM church_census_ca WHERE da_dguid IS NOT NULL"
    ).fetchall())
    print(f'  DA mappings in church_census_ca: {len(da_map):,}')

    # ═══ Step 3: Add columns to church_census_ca ════════════════════
    existing = db.execute("PRAGMA table_info(church_census_ca)").fetchall()
    existing_cols = {c[1] for c in existing}
    for cid, (col_name, desc) in KEY_CHARS.items():
        if col_name not in existing_cols:
            db.execute(f"ALTER TABLE church_census_ca ADD COLUMN {col_name} REAL")

    # ═══ Step 4: Update church_census_ca with demographics ═══════════
    updates = {}
    for dguid, data in dao_data.items():
        for col_name, val in data.items():
            if val is not None:
                if dguid not in updates:
                    updates[dguid] = {}
                updates[dguid][col_name] = val

    # Batch update by column
    updated = 0
    for col_name, _ in KEY_CHARS.values():
        # Collect DGUID→value for this column
        pairs = []
        for dguid, data in updates.items():
            if col_name in data:
                pairs.append((data[col_name], dguid))
        if not pairs:
            continue

        # Create temp table
        db.execute("CREATE TEMP TABLE IF NOT EXISTS _ca_demo (val REAL, dguid TEXT)")
        db.execute("DELETE FROM _ca_demo")
        db.executemany("INSERT INTO _ca_demo VALUES (?, ?)", pairs)

        # Update via join
        result = db.execute(f'''
            UPDATE church_census_ca
            SET {col_name} = (SELECT val FROM _ca_demo WHERE dguid = church_census_ca.da_dguid)
            WHERE da_dguid IN (SELECT dguid FROM _ca_demo)
        ''')
        db.commit()
        cnt = result.rowcount
        updated += cnt
        print(f'  {col_name}: {cnt:,} churches updated')

    # ═══ Step 5: Summary stats ════════════════════════════════════════
    coverage = db.execute(
        "SELECT COUNT(*) FROM church_census_ca WHERE total_pop IS NOT NULL"
    ).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM church_census_ca").fetchone()[0]
    print(f'\n  Total churches with demographics: {coverage:,} / {total:,} ({100*coverage/total:.1f}%)')

    # Sample row
    print('\n  Sample church demographics:')
    sample = db.execute('''
        SELECT dauid, province_code, total_pop, median_age, median_income_2020,
               pop_0_14, pop_15_64, pop_65_plus, bachelors_plus, owner_households, renter_households
        FROM church_census_ca
        WHERE total_pop IS NOT NULL
        LIMIT 5
    ''').fetchall()
    for s in sample:
        print(f'    DA:{s[0]} ({s[1]}) Pop:{int(s[2]):,} Age:{s[3]:.0f} Income:${int(s[4]):,} '
              f'0-14:{int(s[5]):,} 15-64:{int(s[6]):,} 65+:{int(s[7]):,} '
              f'Bach+:{int(s[8]):,} Own:{int(s[9]):,} Rent:{int(s[10]):,}')

    # ═══ Step 6: Provenance ══════════════════════════════════════════
    now = datetime.now().isoformat()
    fields = ','.join(name for name, _ in KEY_CHARS.values())
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'census_2021_ca_demographics',
        'import_canada_demographics.py',
        now, now, coverage, 0, fields,
        len(dao_data), coverage,
        'completed',
        f'2021 Census demographics: {coverage}/{total} CA churches enriched'
    ))
    db.commit()
    db.close()

    print(f'\n{"="*60}')
    print(f'DONE: {coverage:,} churches enriched with census demographics')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Create/update the church_census_catalog metadata table.

Tracks all census/election enrichment tables and their schemas
so downstream tools (and the user) can discover what's available.
"""
import sqlite3
from datetime import datetime

DB = r'E:\grid\churches.db'

CATALOG_ENTRIES = [
    # (country, table_name, category, geo_unit, description, variables)
    ('US', 'church_census_us',       'census',   'tract',    'ACS 2020 5-year demographics at census tract level', 20),
    ('US', 'county_census_us',       'census',   'county',   'ACS 2020 5-year demographics at county level', 19),
    ('US', 'tract_lookup_us',        'lookup',   'tract',    'Tract FIPS → county FIPS + basic pop/household lookup', 7),
    ('US', 'election_results',       'election', 'county',   'County-level presidential returns 2000-2024 (MEDSL)', 12),
    ('US', 'eac_eavs',               'election', 'county',   'EAC voter registration and turnout by county', 16),

    ('CA', 'church_census_ca',       'census',   'DA/CT',    '2021 Census geography IDs (DA + CT) per church', 8),
    ('CA', 'church_fed',             'boundary', 'riding',   'Federal Electoral District (343 ridings)', 5),
    ('CA', 'election_canada_fed_results', 'election', 'riding', '2021 election results transposed to 2023 FEDs', 21),

    ('MX', 'church_census_mx',       'census',   'AGEB',     'INEGI 2020 census at AGEB level (50 variables)', 50),
    ('MX', 'municipio_census_mx',    'census',   'municipio','INEGI 2020 census at municipio level', 37),
]


def main():
    db = sqlite3.connect(DB)

    db.executescript('''
        CREATE TABLE IF NOT EXISTS church_census_catalog (
            country         TEXT NOT NULL,      -- ISO 3166-1 alpha-2
            table_name      TEXT NOT NULL,      -- SQLite table name
            category        TEXT NOT NULL,      -- 'census', 'election', 'boundary', 'lookup'
            geo_unit        TEXT,               -- 'tract', 'county', 'DA', 'AGEB', 'riding', etc.
            description     TEXT,               -- Human-readable
            variable_count  INTEGER,            -- Approximate number of data columns
            row_count       INTEGER,            -- Current row count (refreshed)
            source_date     TEXT DEFAULT (date('now')),
            refresh_date    TEXT,
            PRIMARY KEY (country, table_name)
        );
        CREATE INDEX IF NOT EXISTS idx_catalog_country ON church_census_catalog(country);
        CREATE INDEX IF NOT EXISTS idx_catalog_category ON church_census_catalog(category);
    ''')

    for country, table, category, geo_unit, desc, var_count in CATALOG_ENTRIES:
        # Get current row count
        exists = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        row_count = None
        if exists:
            row_count = db.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]

        db.execute('''
            INSERT OR REPLACE INTO church_census_catalog
                (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
        ''', (country, table, category, geo_unit, desc, var_count, row_count))
    db.commit()

    # Print catalog
    print('=== church_census_catalog ===')
    for r in db.execute('''
        SELECT country, category, geo_unit, table_name, row_count, description
        FROM church_census_catalog
        ORDER BY country, category
    ''').fetchall():
        rc = f'{r[4]:,}' if r[4] else 'N/A'
        print(f'  {r[0]:3s} [{r[1]:9s}] {r[2]:10s}  {r[3]:35s}  {rc:>10s} rows  | {r[5]}')

    db.close()
    print(f'\nDONE. Use: SELECT * FROM church_census_catalog;')

if __name__ == '__main__':
    main()

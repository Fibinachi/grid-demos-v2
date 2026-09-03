"""
Migration: Extract address fields into normalized church_addresses table.

Rationale:
- churches table has 14 address/geo columns baked in
- 77% of records have NULL id (can't FK to churches.id)
- Normalized table supports multiple addresses per church, per-address
  provenance, address history, and cleaner schema

Design:
- FK via church_rowid (SQLite rowid — works for ALL records)
- One 'primary' address per church initially (migrated from existing data)
- Old columns stay in churches for backward compatibility
- Future enrichment writes to church_addresses instead

Usage:
    python scripts/db_maintenance/migrate_addresses.py [--dry-run] [--batch 50000]
"""

import sqlite3
import sys
import time
from datetime import datetime, timezone

DB_PATH = r'E:\grid\churches.db'
DRY_RUN = '--dry-run' in sys.argv
BATCH_SIZE = 50000

# ─── Schema ────────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS church_addresses (
    address_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    church_rowid  INTEGER NOT NULL,
    address_type  TEXT NOT NULL DEFAULT 'primary',
    address       TEXT,
    city          TEXT,
    state         TEXT,
    zip           TEXT,
    zip5          TEXT,
    county        TEXT,
    county_fips_5 TEXT,
    country       TEXT,
    latitude      REAL,
    longitude     REAL,
    geocode_source TEXT,
    address_source TEXT,
    source        TEXT,
    valid_from    TEXT,
    valid_until   TEXT,
    is_current    INTEGER DEFAULT 1
)
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_church_addresses_rowid ON church_addresses(church_rowid)",
    "CREATE INDEX IF NOT EXISTS idx_church_addresses_current ON church_addresses(church_rowid, is_current)",
    "CREATE INDEX IF NOT EXISTS idx_church_addresses_city ON church_addresses(city)",
    "CREATE INDEX IF NOT EXISTS idx_church_addresses_country ON church_addresses(country)",
    "CREATE INDEX IF NOT EXISTS idx_church_addresses_county_fips ON church_addresses(county_fips_5)",
]

# Only rows that have at least one non-empty address or geo field
MIGRATE_SQL = """
INSERT INTO church_addresses
    (church_rowid, address_type, address, city, state, zip, zip5,
     county, county_fips_5, country,
     latitude, longitude, geocode_source, address_source,
     source, valid_from, is_current)
SELECT
    rowid, 'primary',
    address, city, state, zip, zip5,
    county, county_fips_5, country,
    latitude, longitude, geocode_source, address_source,
    source,
    datetime('now'), NULL, 1
FROM churches
WHERE (address IS NOT NULL AND address != '')
   OR (city IS NOT NULL AND city != '')
   OR (state IS NOT NULL AND state != '')
   OR (country IS NOT NULL AND country != '')
   OR latitude IS NOT NULL
"""


def run():
    print('Church Addresses Migration')
    print('=' * 40)
    print('Mode: {}\n'.format('DRY RUN' if DRY_RUN else 'LIVE'))

    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')

    total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    eligible = conn.execute("""
        SELECT COUNT(*) FROM churches
        WHERE (address IS NOT NULL AND address != '')
           OR (city IS NOT NULL AND city != '')
           OR (state IS NOT NULL AND state != '')
           OR (country IS NOT NULL AND country != '')
           OR latitude IS NOT NULL
    """).fetchone()[0]
    print('Total churches:     {:,}'.format(total))
    print('Eligible for migration: {:,} ({:.1f}%)'.format(eligible, eligible/total*100))

    # ── Step 1: Create table ──────────────────────────────────────────
    print('\n[1/4] Creating church_addresses table...')
    if not DRY_RUN:
        conn.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEXES_SQL:
            conn.execute(idx_sql)
        conn.commit()
    print('  Done.')

    # ── Step 2: Migrate data in batches ──────────────────────────────
    print('\n[2/4] Migrating data...')

    # Use rowid-based pagination for efficient batching
    # First get min/max rowid for eligible records
    cursor = conn.execute("""
        SELECT MIN(rowid), MAX(rowid) FROM churches
        WHERE (address IS NOT NULL AND address != '')
           OR (city IS NOT NULL AND city != '')
           OR (state IS NOT NULL AND state != '')
           OR (country IS NOT NULL AND country != '')
           OR latitude IS NOT NULL
    """)
    min_rid, max_rid = cursor.fetchone()
    print('  rowid range: {} to {}'.format(min_rid, max_rid))

    total_migrated = 0
    t0 = time.time()
    current_min = min_rid

    while current_min <= max_rid:
        current_max = min(current_min + BATCH_SIZE - 1, max_rid)
        batch_t0 = time.time()

        if DRY_RUN:
            # Count eligible in this range
            cnt = conn.execute("""
                SELECT COUNT(*) FROM churches
                WHERE rowid BETWEEN ? AND ?
                  AND ((address IS NOT NULL AND address != '')
                    OR (city IS NOT NULL AND city != '')
                    OR (state IS NOT NULL AND state != '')
                    OR (country IS NOT NULL AND country != '')
                    OR latitude IS NOT NULL)
            """, (current_min, current_max)).fetchone()[0]
        else:
            conn.execute("""
                INSERT INTO church_addresses
                    (church_rowid, address_type, address, city, state, zip, zip5,
                     county, county_fips_5, country,
                     latitude, longitude, geocode_source, address_source,
                     source, valid_from, is_current)
                SELECT
                    rowid, 'primary',
                    address, city, state, zip, zip5,
                    county, county_fips_5, country,
                    latitude, longitude, geocode_source, address_source,
                    source,
                    datetime('now'), 1
                FROM churches
                WHERE rowid BETWEEN ? AND ?
                  AND ((address IS NOT NULL AND address != '')
                    OR (city IS NOT NULL AND city != '')
                    OR (state IS NOT NULL AND state != '')
                    OR (country IS NOT NULL AND country != '')
                    OR latitude IS NOT NULL)
            """, (current_min, current_max))
            conn.commit()
            cnt = conn.execute(
                'SELECT changes()'
            ).fetchone()[0]

        total_migrated += cnt
        elapsed = time.time() - batch_t0
        pct = total_migrated / eligible * 100 if eligible > 0 else 100
        rate = total_migrated / (time.time() - t0) if (time.time() - t0) > 0 else 0
        remaining = eligible - total_migrated
        eta = remaining / rate if rate > 0 else 0

        print('  batch rowid {:>7,}–{:<7,}: {:>6,} rows ({:4.1f}%) [{:.1f}s, {:,.0f}/s, ETA {:.0f}s]'.format(
            current_min, current_max, cnt, pct, elapsed, rate, eta
        ))

        current_min = current_max + 1

    print('\n  Total migrated: {:,}'.format(total_migrated))

    # ── Step 3: Verify ────────────────────────────────────────────────
    print('\n[3/4] Verifying...')
    if not DRY_RUN:
        addr_count = conn.execute('SELECT COUNT(*) FROM church_addresses').fetchone()[0]
        distinct_churches = conn.execute('SELECT COUNT(DISTINCT church_rowid) FROM church_addresses').fetchone()[0]
        null_fk = conn.execute("""
            SELECT COUNT(*) FROM church_addresses ca
            LEFT JOIN churches c ON ca.church_rowid = c.rowid
            WHERE c.rowid IS NULL
        """).fetchone()[0]
        print('  church_addresses rows:    {:,}'.format(addr_count))
        print('  Distinct churches:        {:,}'.format(distinct_churches))
        print('  Orphan records:           {:,}'.format(null_fk))
    else:
        print('  Skipped (dry run).')

    # ── Step 4: Summary ───────────────────────────────────────────────
    print('\n[4/4] Summary')
    print('  Migrated: {:,} address records'.format(total_migrated))
    print('  Time:     {:.0f}s'.format(time.time() - t0))
    print('  Rate:     {:,.0f} rows/s'.format(total_migrated / (time.time() - t0) if (time.time() - t0) > 0 else 0))

    if DRY_RUN:
        print('\nRun without --dry-run to execute migration.')

    conn.close()


if __name__ == '__main__':
    run()

"""
Migration v2: Two-layer normalized address schema.

Design:
  church_addresses     — universal fields (lat/lon, country, type, provenance)
  address_components   — flexible key-value per address (street, city, state,
                         postcode, district, neighborhood, etc.)

Supports any country's address format via component types + sort_order.

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

# ─── New Schema ────────────────────────────────────────────────────────────

DROP_TABLE_SQL = "DROP TABLE IF EXISTS church_addresses"

CREATE_ADDRESSES_SQL = """
CREATE TABLE IF NOT EXISTS church_addresses (
    address_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    church_rowid  INTEGER NOT NULL,
    address_type  TEXT NOT NULL DEFAULT 'primary',
    latitude      REAL,
    longitude     REAL,
    country       TEXT,
    geocode_source TEXT,
    source        TEXT,
    is_current    INTEGER DEFAULT 1,
    valid_from    TEXT,
    valid_until   TEXT
)
"""

CREATE_COMPONENTS_SQL = """
CREATE TABLE IF NOT EXISTS address_components (
    component_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    address_id      INTEGER NOT NULL REFERENCES church_addresses(address_id) ON DELETE CASCADE,
    component_type  TEXT NOT NULL,
    component_value TEXT NOT NULL,
    sort_order      INTEGER DEFAULT 0
)
"""

# ─── Country address format templates ─────────────────────────────────────

CREATE_FORMAT_SQL = """
CREATE TABLE IF NOT EXISTS country_address_formats (
    country_code    TEXT PRIMARY KEY,
    country_name    TEXT,
    format_order    TEXT NOT NULL,  -- JSON array of component types in display order
    component_sep   TEXT DEFAULT ', '
)
"""

COUNTRY_FORMATS = [
    # Basic template for every country — individual records can override
    ('US', 'United States', '["street","city","state","postcode"]', ', '),
    ('CA', 'Canada', '["street","city","state","postcode"]', ', '),
    ('GB', 'United Kingdom', '["street","city","state","postcode"]', ', '),
    ('AU', 'Australia', '["street","city","state","postcode"]', ', '),
    ('DE', 'Germany', '["street","postcode","city"]', ', '),
    ('FR', 'France', '["street","postcode","city"]', ', '),
    ('IT', 'Italy', '["street","postcode","city"]', ', '),
    ('ES', 'Spain', '["street","postcode","city"]', ', '),
    ('PT', 'Portugal', '["street","postcode","city"]', ', '),
    ('NL', 'Netherlands', '["street","postcode","city"]', ', '),
    ('BE', 'Belgium', '["street","postcode","city"]', ', '),
    ('CH', 'Switzerland', '["street","postcode","city"]', ', '),
    ('AT', 'Austria', '["street","postcode","city"]', ', '),
    ('PL', 'Poland', '["street","postcode","city"]', ', '),
    ('RU', 'Russia', '["street","city","state","postcode"]', ', '),
    ('JP', 'Japan', '["postcode","state","city","district","street"]', ', '),
    ('CN', 'China', '["street","city","state","postcode"]', ', '),
    ('IN', 'India', '["street","city","state","postcode"]', ', '),
    ('BR', 'Brazil', '["street","neighborhood","city","state","postcode"]', ', '),
    ('MX', 'Mexico', '["street","city","state","postcode"]', ', '),
    ('KR', 'South Korea', '["street","city","state","postcode"]', ', '),
    ('TR', 'Turkey', '["street","city","state","postcode"]', ', '),
    ('ID', 'Indonesia', '["street","city","state","postcode"]', ', '),
    ('TH', 'Thailand', '["street","district","city","state","postcode"]', ', '),
    ('VN', 'Vietnam', '["street","city","state","postcode"]', ', '),
    ('PH', 'Philippines', '["street","city","state","postcode"]', ', '),
    ('MY', 'Malaysia', '["street","city","state","postcode"]', ', '),
    ('SG', 'Singapore', '["street","city","postcode"]', ', '),
    ('HK', 'Hong Kong', '["street","district","city"]', ', '),
    ('TW', 'Taiwan', '["street","city","state","postcode"]', ', '),
    ('ZA', 'South Africa', '["street","city","state","postcode"]', ', '),
    ('NG', 'Nigeria', '["street","city","state","postcode"]', ', '),
    ('EG', 'Egypt', '["street","city","state","postcode"]', ', '),
    ('SA', 'Saudi Arabia', '["street","city","state","postcode"]', ', '),
    ('AE', 'UAE', '["street","city","state","postcode"]', ', '),
    ('IL', 'Israel', '["street","city","state","postcode"]', ', '),
    ('AR', 'Argentina', '["street","city","state","postcode"]', ', '),
    ('CL', 'Chile', '["street","city","state","postcode"]', ', '),
    ('CO', 'Colombia', '["street","city","state","postcode"]', ', '),
    ('PE', 'Peru', '["street","city","state","postcode"]', ', '),
    ('SE', 'Sweden', '["street","postcode","city"]', ', '),
    ('NO', 'Norway', '["street","postcode","city"]', ', '),
    ('DK', 'Denmark', '["street","postcode","city"]', ', '),
    ('FI', 'Finland', '["street","postcode","city"]', ', '),
    ('GR', 'Greece', '["street","postcode","city"]', ', '),
    ('UA', 'Ukraine', '["street","city","state","postcode"]', ', '),
    ('RO', 'Romania', '["street","city","state","postcode"]', ', '),
    ('CZ', 'Czech Republic', '["street","postcode","city"]', ', '),
    ('HU', 'Hungary', '["street","city","state","postcode"]', ', '),
    ('IE', 'Ireland', '["street","city","state","postcode"]', ', '),
    ('NZ', 'New Zealand', '["street","city","state","postcode"]', ', '),
    ('PK', 'Pakistan', '["street","city","state","postcode"]', ', '),
    ('BD', 'Bangladesh', '["street","city","state","postcode"]', ', '),
    ('KE', 'Kenya', '["street","city","state","postcode"]', ', '),
    ('MM', 'Myanmar', '["street","city","state","postcode"]', ', '),
]


def build_components(church_row):
    """
    Given a row from churches, return a list of (component_type, value, sort_order)
    tuples appropriate for the record's country.
    """
    country = church_row['country'] or ''
    components = []
    sort = 0

    # Map existing columns to component types
    # street address
    addr = (church_row['address'] or '').strip()
    if addr:
        components.append(('street', addr, sort))
        sort += 1

    # city
    city = (church_row['city'] or '').strip()
    if city:
        components.append(('city', city, sort))
        sort += 1

    # county (US-specific intermediate admin)
    county = (church_row['county'] or '').strip()
    if county:
        components.append(('county', county, sort))
        sort += 1

    # state / province / prefecture (admin level 1)
    state = (church_row['state'] or '').strip()
    if state:
        # Only US and CA actually have meaningful state values
        components.append(('state', state, sort))
        sort += 1

    # postal code
    zip_val = (church_row['zip'] or church_row['zip5'] or '').strip()
    if zip_val:
        components.append(('postcode', zip_val, sort))
        sort += 1

    return components


def run():
    print('Church Addresses Migration v2 — Two-Layer Normalized Schema')
    print('=' * 55)
    print('Mode: {}\n'.format('DRY RUN' if DRY_RUN else 'LIVE'))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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

    # ── Step 1: Drop old, create new tables ──────────────────────────
    print('\n[1/5] Creating church_addresses + address_components...')
    if not DRY_RUN:
        conn.execute(DROP_TABLE_SQL)
        conn.execute(CREATE_ADDRESSES_SQL)
        conn.execute(CREATE_COMPONENTS_SQL)
        conn.execute(CREATE_FORMAT_SQL)

        # Insert country format templates
        for cc, cname, fmt_order, sep in COUNTRY_FORMATS:
            conn.execute(
                'INSERT OR IGNORE INTO country_address_formats VALUES (?, ?, ?, ?)',
                (cc, cname, fmt_order, sep)
            )

        # Indexes
        conn.execute('CREATE INDEX IF NOT EXISTS idx_addresses_rowid ON church_addresses(church_rowid)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_addresses_current ON church_addresses(church_rowid, is_current)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_components_addr ON address_components(address_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_components_type ON address_components(component_type, component_value)')
        conn.commit()
    print('  Done.')

    # ── Step 2: Get rowid range for batching ─────────────────────────
    print('\n[2/5] Migrating data...')
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

    total_addresses = 0
    total_components = 0
    t0 = time.time()
    current_min = min_rid

    while current_min <= max_rid:
        current_max = min(current_min + BATCH_SIZE - 1, max_rid)
        batch_t0 = time.time()

        # Fetch batch
        rows = conn.execute("""
            SELECT rowid, id, address, city, state, county, zip, zip5,
                   country, latitude, longitude, geocode_source, source
            FROM churches
            WHERE rowid BETWEEN ? AND ?
              AND ((address IS NOT NULL AND address != '')
                OR (city IS NOT NULL AND city != '')
                OR (state IS NOT NULL AND state != '')
                OR (country IS NOT NULL AND country != '')
                OR latitude IS NOT NULL)
            ORDER BY rowid
        """, (current_min, current_max)).fetchall()

        n_addr = 0
        n_comp = 0

        if not DRY_RUN:
            for row in rows:
                components = build_components(row)
                if not components and not row['latitude'] and not row['country']:
                    continue  # skip truly empty

                # Insert address record
                conn.execute("""
                    INSERT INTO church_addresses
                        (church_rowid, address_type, latitude, longitude,
                         country, geocode_source, source, is_current, valid_from)
                    VALUES (?, 'primary', ?, ?, ?, ?, ?, 1, datetime('now'))
                """, (
                    row['rowid'],
                    row['latitude'],
                    row['longitude'],
                    row['country'],
                    row['geocode_source'],
                    row['source'],
                ))
                addr_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                n_addr += 1

                # Insert components
                for ctype, cval, sort in components:
                    conn.execute("""
                        INSERT INTO address_components
                            (address_id, component_type, component_value, sort_order)
                        VALUES (?, ?, ?, ?)
                    """, (addr_id, ctype, cval, sort))
                    n_comp += 1

            conn.commit()

            # Also log provenance
            if n_addr > 0:
                conn.execute("""
                    INSERT INTO provenance_log
                        (source, script_name, started_at, completed_at,
                         churches_inserted, fields_populated,
                         records_attempted, status)
                    VALUES ('schema_migration', 'migrate_addresses.py',
                            datetime('now'), datetime('now'),
                            ?, 'address_components',
                            ?, 'completed')
                """, (n_addr, n_addr))

        else:
            # Dry-run: count eligible
            n_addr = len(rows)
            n_comp = sum(len(build_components(r)) for r in rows)

        total_addresses += n_addr
        total_components += n_comp
        elapsed = time.time() - batch_t0
        pct = total_addresses / eligible * 100 if eligible > 0 else 100
        rate = total_addresses / (time.time() - t0) if (time.time() - t0) > 0 else 0
        remaining = eligible - total_addresses
        eta = remaining / rate if rate > 0 else 0

        print('  batch {:>7,}–{:<7,}: {:>6,} addr, {:>7,} comp ({:4.1f}%) [{:.1f}s, {:,.0f}/s, ETA {:.0f}s]'.format(
            current_min, current_max, n_addr, n_comp, pct, elapsed, rate, eta
        ))

        current_min = current_max + 1

    # ── Step 3: Verify ────────────────────────────────────────────────
    print('\n[3/5] Verifying...')
    if not DRY_RUN:
        addr_count = conn.execute('SELECT COUNT(*) FROM church_addresses').fetchone()[0]
        comp_count = conn.execute('SELECT COUNT(*) FROM address_components').fetchone()[0]
        distinct_churches = conn.execute('SELECT COUNT(DISTINCT church_rowid) FROM church_addresses').fetchone()[0]
        orphans = conn.execute("""
            SELECT COUNT(*) FROM church_addresses ca
            LEFT JOIN churches c ON ca.church_rowid = c.rowid
            WHERE c.rowid IS NULL
        """).fetchone()[0]

        # Component distribution
        comp_dist = conn.execute("""
            SELECT component_type, COUNT(*) as cnt
            FROM address_components
            GROUP BY component_type
            ORDER BY cnt DESC
        """).fetchall()

        print('  church_addresses rows:     {:,}'.format(addr_count))
        print('  address_components rows:   {:,}'.format(comp_count))
        print('  Distinct churches:         {:,}'.format(distinct_churches))
        print('  Orphan records:            {:,}'.format(orphans))
        print('  Component distribution:')
        for ctype, cnt in comp_dist:
            print('    {:<20s} {:>10,}'.format(ctype, cnt))
    else:
        print('  Skipped (dry run).')

    # ── Step 4: Summary ───────────────────────────────────────────────
    print('\n[4/5] Summary')
    print('  Addresses migrated: {:,}'.format(total_addresses))
    print('  Components created: {:,}'.format(total_components))
    print('  Avg components/addr: {:.1f}'.format(
        total_components / total_addresses if total_addresses > 0 else 0
    ))
    print('  Time: {:.0f}s'.format(time.time() - t0))
    print('  Rate: {:,.0f} addr/s'.format(total_addresses / (time.time() - t0) if (time.time() - t0) > 0 else 0))

    if DRY_RUN:
        print('\nRun without --dry-run to execute migration.')

    conn.close()


if __name__ == '__main__':
    run()

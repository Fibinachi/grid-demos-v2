"""
SCRIPT: decompose_enrichment_dead.py
PURPOSE:
  Create target tables for the 47 dead (all-NULL) columns in church_enrichment.
  These columns represent forward-looking schema anchors for data that was
  planned but never imported. This script creates the normalized destination
  tables so future imports have a proper home.

  47 dead columns → 11 target tables:

    Table                    Columns absorbed               Purpose
    ──────────────────────────────────────────────────────────────────────
    county_census_us               county_total_pop … (19 cols)  County-level ACS demographics
    church_fcc               fcc_facility_id +3            FCC broadcast stations
    church_metro_area        cbsa_code +4                  CBSA/DMA metro area assignments
    church_nrhp              nrhp_ref +5                   National Register of Historic Places
    church_gnis              gnis_feature_id +3            Geographic Names Info System
    rucc_codes               (lookup table)                Rural-Urban Continuum Code defs
    church_rucc              rucc_code +1                  RUCC per church
    church_broadband         broadband_pct                 Broadband access
    church_classification_meta scrape_confidence +5       ML confidence + versioning
    church_postal_admin      mx_admin_level +4             Postal admin hierarchy (MX etc.)

  The old columns stay in church_enrichment — no destructive operations.
  Future import scripts should write to these new tables instead.

USAGE:
    python scripts/db_maintenance/decompose_enrichment_dead.py
    python scripts/db_maintenance/decompose_enrichment_dead.py --dry-run
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from gw_db import connect, Provenance

DB_PATH = "churches.db"

# ─── RUCC code reference (USDA 2013) ──────────────────────────────────────
# See: https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/
RUCC_SEED = [
    (1, "Metro - 1 million population or more", 1),
    (2, "Metro - 250,000 to 1 million population", 1),
    (3, "Metro - fewer than 250,000 population", 1),
    (4, "Nonmetro - urban 20,000+, adjacent to metro area", 0),
    (5, "Nonmetro - urban 20,000+, not adjacent to metro area", 0),
    (6, "Nonmetro - urban 2,500-19,999, adjacent to metro area", 0),
    (7, "Nonmetro - urban 2,500-19,999, not adjacent to metro area", 0),
    (8, "Nonmetro - completely rural, adjacent to metro area", 0),
    (9, "Nonmetro - completely rural, not adjacent to metro area", 0),
]

# ─── Schema SQL ────────────────────────────────────────────────────────────

DROP_TABLES = [
    "DROP TABLE IF EXISTS church_classification_meta",
    "DROP TABLE IF EXISTS church_postal_admin",
    "DROP TABLE IF EXISTS church_broadband",
    "DROP TABLE IF EXISTS church_rucc",
    "DROP TABLE IF EXISTS rucc_codes",
    "DROP TABLE IF EXISTS church_gnis",
    "DROP TABLE IF EXISTS church_nrhp",
    "DROP TABLE IF EXISTS church_metro_area",
    "DROP TABLE IF EXISTS church_fcc",
    "DROP TABLE IF EXISTS county_census_us",
]

CREATE_TABLES = """

-- 1. County-level ACS demographics
CREATE TABLE IF NOT EXISTS county_census_us (
    county_fips         TEXT PRIMARY KEY,
    total_pop           REAL,
    median_hh_income    REAL,
    poverty_rate        REAL,
    unemployment_rate   REAL,
    bachelors_25_64     REAL,
    graduate_degree     REAL,
    white_pct           REAL,
    black_pct           REAL,
    asian_pct           REAL,
    hispanic_pct        REAL,
    median_home_value   REAL,
    median_gross_rent   REAL,
    owner_pct           REAL,
    mean_commute_min    REAL,
    drove_alone_pct     REAL,
    wfh_pct             REAL,
    gini_index          REAL,
    median_age          REAL,
    income_per_capita   REAL,
    tract_count_in_county REAL,
    source              TEXT,
    updated_at          TEXT
);

-- 2. FCC broadcast stations linked to churches
CREATE TABLE IF NOT EXISTS church_fcc (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id       INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    facility_id     TEXT,
    call_sign       TEXT,
    service_type    TEXT,
    source          TEXT,
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_church_fcc_church ON church_fcc(church_id);
CREATE INDEX IF NOT EXISTS idx_church_fcc_facility ON church_fcc(facility_id);

-- 3. Metro area (CBSA/DMA) assignments per church
CREATE TABLE IF NOT EXISTS church_metro_area (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id       INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    cbsa_code       TEXT,
    cbsa_name       TEXT,
    cbsa_type       TEXT,
    dma_name        TEXT,
    source          TEXT,
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_church_metro_area_church ON church_metro_area(church_id);
CREATE INDEX IF NOT EXISTS idx_church_metro_area_cbsa ON church_metro_area(cbsa_code);

-- 4. National Register of Historic Places per church
CREATE TABLE IF NOT EXISTS church_nrhp (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id           INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    nrhp_ref            TEXT,
    listed_date         TEXT,
    category            TEXT,
    significance        TEXT,
    area_of_significance TEXT,
    source              TEXT,
    created_at          TEXT
);
CREATE INDEX IF NOT EXISTS idx_church_nrhp_church ON church_nrhp(church_id);

-- 5. Geographic Names Information System per church
CREATE TABLE IF NOT EXISTS church_gnis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id       INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    feature_id      TEXT,
    latitude        REAL,
    longitude       REAL,
    source          TEXT,
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_church_gnis_church ON church_gnis(church_id);
CREATE INDEX IF NOT EXISTS idx_church_gnis_feature ON church_gnis(feature_id);

-- 6. RUCC code lookup (USDA 2013 definition)
CREATE TABLE IF NOT EXISTS rucc_codes (
    code            INTEGER PRIMARY KEY,
    description     TEXT NOT NULL,
    is_metro        INTEGER NOT NULL DEFAULT 0
);

-- 7. Rural-Urban Continuum Code per church
CREATE TABLE IF NOT EXISTS church_rucc (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id       INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    rucc_code       INTEGER REFERENCES rucc_codes(code),
    source          TEXT,
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_church_rucc_church ON church_rucc(church_id);

-- 8. Broadband access per church
CREATE TABLE IF NOT EXISTS church_broadband (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id       INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    broadband_pct   REAL,
    source          TEXT,
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_church_broadband_church ON church_broadband(church_id);

-- 9. ML classification metadata per church
CREATE TABLE IF NOT EXISTS church_classification_meta (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id               INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    scrape_confidence       REAL,
    kg_confidence           REAL,
    liturgical_tradition    TEXT,
    classification_version  TEXT,
    classification_timestamp TEXT,
    source                  TEXT,
    created_at              TEXT
);
CREATE INDEX IF NOT EXISTS idx_church_class_meta_church ON church_classification_meta(church_id);

-- 10. Postal administrative hierarchy per church (country-generic)
CREATE TABLE IF NOT EXISTS church_postal_admin (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id       INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    admin_level     INTEGER,
    division_id     TEXT,
    division_name   TEXT,
    admin_subtype   TEXT,
    country         TEXT,
    source          TEXT,
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_church_postal_admin_church ON church_postal_admin(church_id);
CREATE INDEX IF NOT EXISTS idx_church_postal_admin_country ON church_postal_admin(country);

"""

# ─── Column-to-table mapping (for summary) ────────────────────────────────

TABLE_MAP = {
    "county_census_us": [
        "county_total_pop", "county_median_hh_income", "county_poverty_rate",
        "county_unemployment_rate", "county_bachelors_25_64", "county_graduate_degree",
        "county_white_pct", "county_black_pct", "county_asian_pct", "county_hispanic_pct",
        "county_median_home_value", "county_median_gross_rent", "county_owner_pct",
        "county_mean_commute_min", "county_drove_alone_pct", "county_wfh_pct",
        "county_gini_index", "county_median_age", "county_income_per_capita",
        "tract_count_in_county",
    ],
    "church_fcc": ["fcc_facility_id", "fcc_call_sign", "fcc_service_type"],
    "church_metro_area": ["cbsa_code", "cbsa_name", "cbsa_type", "dma_name"],
    "church_nrhp": [
        "nrhp_ref", "nrhp_listed_date", "nrhp_category",
        "nrhp_significance", "nrhp_area_of_significance",
    ],
    "church_gnis": ["gnis_feature_id", "gnis_lat", "gnis_lon"],
    "rucc_codes": ["rucc_code", "rucc_description"],
    "church_broadband": ["broadband_pct"],
    "church_classification_meta": [
        "scrape_confidence", "kg_confidence", "liturgical_tradition",
        "classification_timestamp", "classification_version",
    ],
    "church_postal_admin": [
        "mx_admin_level", "mx_division_id", "mx_division_name", "mx_admin_subtype",
    ],
}


def create_tables(conn, dry_run=False):
    """Create all target tables. Returns list of created table names."""
    created = []
    c = conn.cursor()

    for stmt in CREATE_TABLES.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        table_name = None
        for line in stmt.splitlines():
            line = line.strip()
            if line.upper().startswith("CREATE TABLE"):
                # Extract table name
                parts = line.replace("IF NOT EXISTS", "").split()
                for i, p in enumerate(parts):
                    if p.upper() in ("TABLE",):
                        table_name = parts[i + 1].strip()
                        # Handle IF NOT EXISTS name fragments
                        if table_name.upper() in ("IF", "NOT", "EXISTS"):
                            continue
                        break

        if dry_run:
            if table_name:
                print(f"  [DRY RUN] Would create: {table_name}")
            continue

        try:
            c.execute(stmt)
            if table_name:
                print(f"  Created: {table_name}")
                created.append(table_name)
            conn.commit()
        except Exception as e:
            print(f"  ERROR creating {table_name or 'unknown'}: {e}")

    return created


def seed_rucc(conn, dry_run=False):
    """Insert the 9 standard USDA RUCC codes."""
    if dry_run:
        print(f"  [DRY RUN] Would seed {len(RUCC_SEED)} RUCC codes")
        return 0

    c = conn.cursor()
    # Check if rucc_codes table exists and has data
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='rucc_codes'"
    ).fetchall()]
    if tables:
        existing = c.execute("SELECT COUNT(*) FROM rucc_codes").fetchone()[0]
        if existing >= 9:
            print(f"  RUCC codes already seeded ({existing} rows)")
            return 0

    count = 0
    for code, desc, metro in RUCC_SEED:
        c.execute(
            "INSERT OR IGNORE INTO rucc_codes (code, description, is_metro) VALUES (?, ?, ?)",
            (code, desc, metro),
        )
        count += 1
    conn.commit()
    print(f"  Seeded {count} RUCC codes")
    return count


def print_summary(created_tables, dry_run=False):
    """Print a summary of what was done."""
    if dry_run:
        print("\n=== DRY RUN SUMMARY ===")
        print("No changes made. The following tables would be created:")
        for table, cols in TABLE_MAP.items():
            print(f"  {table:30s} ({len(cols)} columns)")
        print(f"\n  rucc_codes: lookup table (9 USDA codes)")
        print(f"  church_rucc: link table (rucc_code per church)")
        return

    print("\n=== CREATED TABLES ===")
    for t in sorted(created_tables):
        if t in TABLE_MAP:
            print(f"  {t:30s} ({len(TABLE_MAP[t])} columns)")
        elif t == "rucc_codes":
            print(f"  rucc_codes: lookup table (9 USDA RUCC codes)")
        elif t == "church_rucc":
            print(f"  church_rucc: link table (rucc_code per church)")

    print(f"\n  Total: {len(created_tables)} tables")
    print("  Dead columns in church_enrichment: unchanged (47 cols, all-NULL)")
    print("  Next step: write import scripts to populate these tables")


def main():
    parser = argparse.ArgumentParser(
        description="Create target tables for 47 dead church_enrichment columns"
    )
    parser.add_argument("--dry-run", action="store_true",
                       help="Print what would be done without making changes")
    args = parser.parse_args()

    dry_run = args.dry_run

    print(f"=== Decompose church_enrichment dead columns ===")
    print(f"  Dry run: {dry_run}")
    print(f"  DB: {DB_PATH}")
    print()

    if not dry_run:
        conn = connect(DB_PATH)
    else:
        conn = connect(DB_PATH)

    start = time.time()

    # ── Create tables ──
    print("Creating target tables...")
    created = create_tables(conn, dry_run=dry_run)

    # ── Seed RUCC lookup ──
    if "rucc_codes" in created or dry_run:
        print("\nSeeding RUCC codes...")
        seed_rucc(conn, dry_run=dry_run)

    # ── Provenance ──
    if not dry_run and created:
        c2 = conn.cursor()
        c2.execute("""
            INSERT INTO provenance_log
                (source, script_name, status, fields_populated, started_at, completed_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            "schema_migration",
            "scripts/db_maintenance/decompose_enrichment_dead.py",
            "completed",
            ", ".join(sorted(created)),
        ))
        conn.commit()

    elapsed = time.time() - start

    # ── Summary ──
    print_summary(created, dry_run=dry_run)
    print(f"\nElapsed: {elapsed:.1f}s")

    if not dry_run:
        conn.close()

    return 0 if created or dry_run else 1


if __name__ == "__main__":
    sys.exit(main())

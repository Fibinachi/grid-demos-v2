#!/usr/bin/env python3
"""
Build the Catholic Directory storage database (catholic_directory.db).

This is a standalone SQLite database separate from churches.db.
It stores fully-parsed entries from Catholic directories (parishes, cathedrals,
deaneries, missions, chapels, schools, cemeteries, hospitals, convents, etc.)
along with clergy assignments and bishop/hierarchy records.

Usage:
    python scripts/ingest/_build_catholic_dir_db.py              # Create/verify DB
    python scripts/ingest/_build_catholic_dir_db.py --rebuild    # Drop & recreate
"""

import sqlite3
import os
import sys
from pathlib import Path

DB_PATH = Path("E:/grid/data/catholic_directory.db")

SCHEMA = """
-- ======================================================================
-- Directory metadata — one row per directory year imported
-- ======================================================================
CREATE TABLE IF NOT EXISTS directory_metadata (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    year            INTEGER NOT NULL,
    title           TEXT,
    source_file     TEXT,
    total_entries   INTEGER,
    total_clergy    INTEGER,
    total_bishops   INTEGER,
    imported_at     TEXT DEFAULT (datetime('now')),
    notes           TEXT
);

-- ======================================================================
-- Main entries — every entity from the directory
-- parishes, cathedrals, deaneries, missions, chapels, schools,
-- cemeteries, hospitals, orphanages, friaries, convents, shrines,
-- seminaries, and any other listed institution
-- ======================================================================
CREATE TABLE IF NOT EXISTS dir_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    directory_year  INTEGER NOT NULL,
    source_entry_id TEXT,             -- stable key from source (e.g. row index)
    name            TEXT NOT NULL,
    city            TEXT,
    state           TEXT,
    diocese         TEXT,             -- diocese / archdiocese name
    entity_type     TEXT,             -- parish, cathedral, deanery, mission, chapel,
                                      --   school, cemetery, hospital, orphanage,
                                      --   friary, convent, shrine, seminary,
                                      --   college, chancery, other
    address         TEXT,
    zip             TEXT,
    phone           TEXT,
    website         TEXT,
    email           TEXT,
    year_founded    INTEGER,
    landmark_type   TEXT,             -- mapped to GRID landmark_type taxonomy
    grid_church_id  INTEGER,          -- matched GRID churches.id (or rowid)
    notes           TEXT,
    source_raw      TEXT,             -- original JSON blob from source
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ======================================================================
-- Clergy assignments — pastors, vicars, deacons, administrators, etc.
-- ======================================================================
CREATE TABLE IF NOT EXISTS dir_clergy (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id        INTEGER REFERENCES dir_entries(id) ON DELETE CASCADE,
    directory_year  INTEGER NOT NULL,
    name            TEXT NOT NULL,
    role            TEXT,             -- PASTOR, PAROCHIAL_VICAR, DEACON,
                                      --   ADMINISTRATOR, DIRECTOR, CHAPLAIN,
                                      --   SUPERIOR, VICAR, RECTOR, etc.
    prefix          TEXT,             -- Rev., Msgr., Fr., Sr., Dr., etc.
    suffix          TEXT,             -- C.M., O.F.M.Cap., S.J., O.P., etc.
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ======================================================================
-- Bishops / hierarchy — archbishops, bishops, cardinals, auxiliaries
-- ======================================================================
CREATE TABLE IF NOT EXISTS dir_bishops (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    directory_year  INTEGER NOT NULL,
    name            TEXT NOT NULL,
    title           TEXT,             -- "Archbishop of Los Angeles", "Bishop of X"
    diocese         TEXT,
    bishop_type     TEXT,             -- ARCHBISHOP, BISHOP, CARDINAL,
                                      --   AUXILIARY_BISHOP, COADJUTOR
    status          TEXT,             -- active, retired, deceased
    appointed_year  INTEGER,
    consecrated_year INTEGER,
    birth_year      INTEGER,
    ordained_year   INTEGER,
    cathedral       TEXT,             -- cathedral church name
    previous_role   TEXT,
    notes           TEXT,
    source_raw      TEXT,             -- original JSON blob
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ======================================================================
-- Contacts — normalized phone/email/website per entry
-- ======================================================================
CREATE TABLE IF NOT EXISTS dir_contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id        INTEGER REFERENCES dir_entries(id) ON DELETE CASCADE,
    contact_type    TEXT NOT NULL,     -- phone, email, website, fax
    value           TEXT NOT NULL,
    is_primary      INTEGER DEFAULT 0,
    source          TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ======================================================================
-- Provenance log
-- ======================================================================
CREATE TABLE IF NOT EXISTS dir_provenance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    description     TEXT,
    entry_count     INTEGER,
    clergy_count    INTEGER,
    bishop_count    INTEGER,
    created_at      TEXT DEFAULT (datetime('now'))
);


-- ======================================================================
-- Indexes
-- ======================================================================
CREATE INDEX IF NOT EXISTS idx_dir_entries_year ON dir_entries(directory_year);
CREATE INDEX IF NOT EXISTS idx_dir_entries_diocese ON dir_entries(diocese);
CREATE INDEX IF NOT EXISTS idx_dir_entries_type ON dir_entries(entity_type);
CREATE INDEX IF NOT EXISTS idx_dir_entries_city_state ON dir_entries(city, state);
CREATE INDEX IF NOT EXISTS idx_dir_entries_name ON dir_entries(name);
CREATE INDEX IF NOT EXISTS idx_dir_clergy_entry ON dir_clergy(entry_id);
CREATE INDEX IF NOT EXISTS idx_dir_clergy_name ON dir_clergy(name);
CREATE INDEX IF NOT EXISTS idx_dir_clergy_role ON dir_clergy(role);
CREATE INDEX IF NOT EXISTS idx_dir_bishops_year ON dir_bishops(directory_year);
CREATE INDEX IF NOT EXISTS idx_dir_bishops_diocese ON dir_bishops(diocese);
CREATE INDEX IF NOT EXISTS idx_dir_contacts_entry ON dir_contacts(entry_id);
CREATE INDEX IF NOT EXISTS idx_dir_contacts_type ON dir_contacts(contact_type);

-- ======================================================================
-- Views
-- ======================================================================

-- Parish-only view (most common query)
CREATE VIEW IF NOT EXISTS vw_parishes AS
SELECT * FROM dir_entries WHERE entity_type = 'parish';

-- Entries with clergy counts
CREATE VIEW IF NOT EXISTS vw_entries_with_clergy_count AS
SELECT
    e.*,
    (SELECT COUNT(*) FROM dir_clergy c WHERE c.entry_id = e.id) AS clergy_count
FROM dir_entries e;

-- Diocese summary per year
CREATE VIEW IF NOT EXISTS vw_diocese_summary AS
SELECT
    directory_year,
    diocese,
    COUNT(*) AS total_entries,
    SUM(CASE WHEN entity_type = 'parish' THEN 1 ELSE 0 END) AS parishes,
    SUM(CASE WHEN entity_type = 'cathedral' THEN 1 ELSE 0 END) AS cathedrals,
    SUM(CASE WHEN entity_type = 'school' THEN 1 ELSE 0 END) AS schools,
    SUM(CASE WHEN entity_type NOT IN ('parish','cathedral','school') THEN 1 ELSE 0 END) AS other
FROM dir_entries
GROUP BY directory_year, diocese
ORDER BY directory_year, total_entries DESC;

-- Year-over-year comparison (when both years loaded)
CREATE VIEW IF NOT EXISTS vw_year_comparison AS
SELECT
    COALESCE(d1.diocese, d2.diocese) AS diocese,
    d1.total_entries AS entries_1865,
    d2.total_entries AS entries_2021,
    d1.parishes AS parishes_1865,
    d2.parishes AS parishes_2021,
    d1.cathedrals AS cathedrals_1865,
    d2.cathedrals AS cathedrals_2021
FROM
    (SELECT * FROM vw_diocese_summary WHERE directory_year = 1865) d1
FULL OUTER JOIN
    (SELECT * FROM vw_diocese_summary WHERE directory_year = 2021) d2
ON d1.diocese = d2.diocese
ORDER BY COALESCE(d2.total_entries, d1.total_entries) DESC;
"""


def build_db(rebuild=False):
    """Create or verify the Catholic directory database."""
    if rebuild and DB_PATH.exists():
        print(f"Dropping existing database: {DB_PATH}")
        DB_PATH.unlink()

    db_exists = DB_PATH.exists()
    print(f"Database: {DB_PATH}  ({'exists' if db_exists else 'new'})")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    if rebuild or not db_exists:
        print("Executing schema...")
        conn.executescript(SCHEMA)
        conn.commit()
        print("✅ Schema created successfully.")
    else:
        print("Database already exists — schema not modified (use --rebuild to recreate).")

    # Verify tables
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    views = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()

    print(f"\nTables ({len(tables)}):")
    for (name,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        print(f"  {name:30s} {count:>8,} rows")

    print(f"\nViews ({len(views)}):")
    for (name,) in views:
        print(f"  {name}")

    conn.close()
    print("\nDone.")
    return DB_PATH


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Build Catholic Directory storage DB")
    p.add_argument("--rebuild", action="store_true", help="Drop & recreate DB")
    args = p.parse_args()
    build_db(rebuild=args.rebuild)

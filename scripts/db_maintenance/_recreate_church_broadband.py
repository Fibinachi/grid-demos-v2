#!/usr/bin/env python3
"""
Recreate church_broadband table with combined schema:
  - decompose columns (id, church_id, broadband_pct, source, created_at)
  - FCC Form 477 columns (tract_fips, has_fiber, has_cable, has_dsl,
    has_fixed_wireless, max_download_mbps, max_upload_mbps,
    provider_count, fiber_providers, cable_providers, data_vintage)

Run this FIRST, before running download_fcc_broadband.py.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect

SQL = """
DROP TABLE IF EXISTS church_broadband;

CREATE TABLE church_broadband (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    church_id           INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
    tract_fips          TEXT,
    broadband_pct       REAL,
    has_fiber           INTEGER DEFAULT 0,
    has_cable           INTEGER DEFAULT 0,
    has_dsl             INTEGER DEFAULT 0,
    has_fixed_wireless  INTEGER DEFAULT 0,
    max_download_mbps   REAL,
    max_upload_mbps     REAL,
    provider_count      INTEGER DEFAULT 0,
    fiber_providers     INTEGER DEFAULT 0,
    cable_providers     INTEGER DEFAULT 0,
    data_vintage        TEXT DEFAULT '2024-06',
    source              TEXT,
    created_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_church_broadband_church ON church_broadband(church_id);
"""

def main():
    db = connect()
    for statement in SQL.strip().split(';'):
        stmt = statement.strip()
        if stmt:
            db.execute(stmt)
    db.commit()
    # Verify
    cur = db.cursor()
    cur.execute("PRAGMA table_info(church_broadband)")
    cols = [(r[1], r[2]) for r in cur.fetchall()]
    print(f"church_broadband recreated: {len(cols)} columns")
    for name, dtype in cols:
        print(f"  {name:20s} {dtype}")
    db.close()

if __name__ == "__main__":
    main()

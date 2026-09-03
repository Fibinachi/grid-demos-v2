#!/usr/bin/env python3
"""
compute_relative_elevation.py — Local relief from church elevations
====================================================================
Uses the church elevation_m values (from elevate_churches.py) and computes
local relative elevation by gridding the world into cells and comparing
each church's elevation against the mean elevation of its cell.

Negative values = church is in a local low spot (higher flood risk)
Positive values = church is on local high ground (safer)

Columns added:
  - cell_elev_avg_m     — mean elevation of all churches in same 0.1° cell
  - rel_elev_m          — church elevation minus cell average (positive = high ground)
  - rel_elev_pctl       — percentile within its cell (0-100, higher = safer)

Usage:
    python scripts/enrichment/compute_relative_elevation.py [--grid-size 0.1]
"""

import sys, sqlite3, math, argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / 'churches.db'


def add_columns(db):
    """Add relative elevation columns."""
    for col, typ in [('cell_elev_avg_m', 'REAL'),
                     ('rel_elev_m', 'REAL'),
                     ('rel_elev_pctl', 'REAL')]:
        try:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} {typ}")
            print(f'  Added column: {col}')
        except Exception:
            pass


def compute_relative(db, grid_size=0.1):
    """
    Compute relative elevation within grid cells.
    
    Uses a two-pass approach:
      Pass 1: For each grid cell, compute mean elevation
      Pass 2: For each church, compute difference and percentile
    """
    c = db.cursor()
    
    # Get all churches with elevation
    rows = c.execute("""
        SELECT rowid, latitude, longitude, elevation_m
        FROM churches
        WHERE elevation_m IS NOT NULL
    """).fetchall()
    
    if not rows:
        print('No churches with elevation data. Run elevate_churches.py first.')
        return
    
    total = len(rows)
    print(f'Processing {total:,} churches with elevation data...')
    
    # Pass 1: Sum elevations per grid cell
    cell_sums = {}   # (lat_idx, lon_idx) -> [sum, count]
    for rowid, lat, lon, elev in rows:
        li = int(math.floor(float(lat) / grid_size))
        lni = int(math.floor(float(lon) / grid_size))
        key = (li, lni)
        if key not in cell_sums:
            cell_sums[key] = [0.0, 0]
        cell_sums[key][0] += float(elev)
        cell_sums[key][1] += 1
    
    # Compute cell means
    cell_means = {k: v[0]/v[1] for k, v in cell_sums.items()}
    print(f'  Grid cells populated: {len(cell_means):,}')
    
    # Pass 2: Compute relative elevation per church
    updates_rel = []   # (rel_elev_m, cell_elev_avg_m, rowid)
    
    for rowid, lat, lon, elev in rows:
        li = int(math.floor(float(lat) / grid_size))
        lni = int(math.floor(float(lon) / grid_size))
        key = (li, lni)
        cell_avg = cell_means.get(key)
        if cell_avg is not None:
            rel = round(float(elev) - cell_avg, 1)
            updates_rel.append((rel, round(cell_avg, 1), rowid))
    
    print(f'  Computing relative elevations for {len(updates_rel):,} churches...')
    db.execute("BEGIN TRANSACTION")
    db.executemany(
        "UPDATE churches SET rel_elev_m=?, cell_elev_avg_m=? WHERE rowid=?",
        updates_rel
    )
    db.commit()
    
    # Pass 3: Compute percentiles per cell
    # For each cell, sort churches by rel_elev_m and assign percentile
    cells = {}
    for rowid, lat, lon, elev in rows:
        li = int(math.floor(float(lat) / grid_size))
        lni = int(math.floor(float(lon) / grid_size))
        key = (li, lni)
        if key not in cells:
            cells[key] = []
        cells[key].append((rowid, float(elev)))
    
    updates_pctl = []
    for key, church_list in cells.items():
        if len(church_list) < 3:
            continue  # Skip cells with too few churches
        cell_avg = cell_means[key]
        # Sort by relative elevation
        sorted_churches = sorted(church_list, key=lambda x: x[1] - cell_avg)
        n = len(sorted_churches)
        for rank, (rowid, _) in enumerate(sorted_churches):
            pctl = round((rank / (n - 1)) * 100, 1) if n > 1 else 50.0
            updates_pctl.append((pctl, rowid))
    
    print(f'  Computing percentiles for {len(updates_pctl):,} churches...')
    db.execute("BEGIN TRANSACTION")
    db.executemany(
        "UPDATE churches SET rel_elev_pctl=? WHERE rowid=?",
        updates_pctl
    )
    db.commit()
    
    # Stats
    stats = c.execute("""
        SELECT
            COUNT(*) as total,
            ROUND(AVG(rel_elev_m), 1) as avg_rel,
            ROUND(AVG(cell_elev_avg_m), 1) as avg_cell,
            ROUND(AVG(elevation_m), 1) as avg_elev
        FROM churches WHERE rel_elev_m IS NOT NULL
    """).fetchone()
    
    print(f'\n=== Results ===')
    print(f'  Churches with rel_elev: {stats[0]:,}')
    print(f'  Avg relative elevation: {stats[1]} m')
    print(f'  Avg cell elevation: {stats[2]} m')
    print(f'  Avg absolute elevation: {stats[3]} m')
    
    # Distribution
    dist = c.execute("""
        SELECT
            SUM(CASE WHEN rel_elev_m < -10 THEN 1 ELSE 0 END) as very_low,
            SUM(CASE WHEN rel_elev_m BETWEEN -10 AND -3 THEN 1 ELSE 0 END) as low,
            SUM(CASE WHEN rel_elev_m BETWEEN -3 AND 3 THEN 1 ELSE 0 END) as flat,
            SUM(CASE WHEN rel_elev_m BETWEEN 3 AND 10 THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN rel_elev_m > 10 THEN 1 ELSE 0 END) as very_high
        FROM churches WHERE rel_elev_m IS NOT NULL
    """).fetchone()
    print(f'\n  Very low (<-10m): {dist[0]:,}')
    print(f'  Low (-10 to -3m): {dist[1]:,}')
    print(f'  Flat (-3 to 3m): {dist[2]:,}')
    print(f'  High (3 to 10m): {dist[3]:,}')
    print(f'  Very high (>10m): {dist[4]:,}')


def main():
    p = argparse.ArgumentParser(description='Compute relative elevation')
    p.add_argument('--grid-size', type=float, default=0.1,
                   help='Grid cell size in degrees (default: 0.1 ≈ 11km)')
    args = p.parse_args()
    
    db = sqlite3.connect(str(DB_PATH))
    add_columns(db)
    compute_relative(db, args.grid_size)
    
    db.commit()
    db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    db.close()


if __name__ == '__main__':
    main()

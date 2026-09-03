#!/usr/bin/env python3
"""
build_interfaith_layer.py — Interfaith Proximity & Faith Density Enrichment
============================================================================
Pure cKDTree self-join — zero external data. For every church with GPS,
computes:

  Interfaith Proximity (nearest of each major faith):
    - nearest_mosque_km        distance to nearest Islam entry
    - nearest_synagogue_km     distance to nearest Judaism entry
    - nearest_hindu_temple_km  distance to nearest Hindu entry
    - nearest_buddhist_temple_km  distance to nearest Buddhist entry
    - nearest_sikh_gurdwara_km    distance to nearest Sikh entry
    - nearest_other_faith_km   distance to nearest different-faith entry

  Same-Faith Density (radius counts on own faith tree):
    - same_faith_count_1km     churches of same faith within 1 km
    - same_faith_count_5km     churches of same faith within 5 km
    - same_faith_count_10km    churches of same faith within 10 km

  Same-Tradition (for major traditions with >500 entries):
    - nearest_same_tradition_km  distance to nearest same-tradition entry
    - same_tradition_count_5km   same-tradition entries within 5 km

  - interfaith_updated         timestamp

Usage:
    python scripts/enrichment/build_interfaith_layer.py

Re-run after any import of 1,000+ churches. ~15 min for all 3.5M records.
"""

import sys
import time
import sqlite3
import numpy as np
from scipy.spatial import cKDTree
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / 'churches.db'

# ── Progress bar ───────────────────────────────────────────────────────
def progress_bar(current, total, label='', width=40):
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = chr(0x2588) * filled + chr(0x2591) * (width - filled)
    sys.stderr.write(f'\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)')
    sys.stderr.flush()
    if current >= total:
        sys.stderr.write('\n')


# ── Coordinate helpers ─────────────────────────────────────────────────
def latlon_to_xyz(coords):
    """Convert (lat, lon) in degrees to 3D unit sphere coordinates."""
    lat_rad = np.radians(coords[:, 0])
    lon_rad = np.radians(coords[:, 1])
    x = np.cos(lat_rad) * np.cos(lon_rad)
    y = np.cos(lat_rad) * np.sin(lon_rad)
    z = np.sin(lat_rad)
    return np.column_stack([x, y, z])

def chord_to_km(chord_dist):
    """Convert chord distance on unit sphere to km."""
    return 2 * 6371.0 * np.arcsin(np.clip(chord_dist / 2.0, -1.0, 1.0))

def km_to_chord(km):
    """Convert km to chord distance on unit sphere."""
    return 2.0 * np.sin(km / (2.0 * 6371.0))


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*60}")
    print(f"  Interfaith Proximity & Faith Density Layer")
    print(f"{'='*60}")

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=60000")
    db.execute("PRAGMA cache_size=-64000")  # 64MB cache

    # ── Step 1: Load all churches with GPS ─────────────────────────────
    print(f"\n[1/5] Loading churches from database...")
    t0 = time.time()

    rows = db.execute("""
        SELECT id, latitude, longitude, faith, tradition_id
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude != '' AND longitude != ''
    """).fetchall()

    churches = []
    for r in rows:
        try:
            lat, lon = float(r[1]), float(r[2])
            churches.append({
                'id': r[0],
                'lat': lat,
                'lon': lon,
                'faith': (r[3] or '').strip(),
                'tradition_id': r[4],
            })
        except (ValueError, TypeError):
            continue

    total = len(churches)
    print(f"  Loaded {total:,} churches with GPS in {time.time()-t0:.1f}s")

    # ── Step 2: Group by faith, build per-faith KD-trees ───────────────
    print(f"\n[2/5] Building per-faith KD-trees...")
    t0 = time.time()

    # Map faith names to canonical groups
    faith_groups = defaultdict(list)
    for i, ch in enumerate(churches):
        faith_groups[ch['faith']].append(i)

    # Also group by tradition_id for major traditions
    tradition_groups = defaultdict(list)
    for i, ch in enumerate(churches):
        if ch['tradition_id']:
            tradition_groups[ch['tradition_id']].append(i)

    # Build per-faith trees
    faith_trees = {}
    faith_indices = {}  # maps faith -> list of indices into churches array

    FAITHS_OF_INTEREST = ['Christian', 'Islam', 'Judaism', 'Hindu',
                          'Buddhist', 'Sikh', 'Shinto', 'Other']

    for faith in FAITHS_OF_INTEREST:
        indices = faith_groups.get(faith, [])
        if len(indices) < 2:
            faith_indices[faith] = indices
            faith_trees[faith] = None
            continue
        coords = np.array([(churches[i]['lat'], churches[i]['lon']) for i in indices])
        xyz = latlon_to_xyz(coords)
        faith_trees[faith] = cKDTree(xyz)
        faith_indices[faith] = indices
        print(f"  {faith:15s}: {len(indices):>10,} entries -> KD-tree built")

    # Build per-tradition trees (traditions with >500 entries)
    tradition_trees = {}
    tradition_indices = {}
    MIN_TRADITION = 500
    trad_count = 0
    for tid, indices in sorted(tradition_groups.items(), key=lambda x: -len(x[1])):
        if len(indices) < MIN_TRADITION:
            break
        coords = np.array([(churches[i]['lat'], churches[i]['lon']) for i in indices])
        xyz = latlon_to_xyz(coords)
        tradition_trees[tid] = cKDTree(xyz)
        tradition_indices[tid] = indices
        trad_count += 1

    print(f"  Built {trad_count} tradition KD-trees (>{MIN_TRADITION} entries each)")
    print(f"  KD-trees built in {time.time()-t0:.1f}s")

    # ── Step 3: Add columns ────────────────────────────────────────────
    print(f"\n[3/5] Adding columns to churches table...")
    columns = [
        ('nearest_mosque_km', 'REAL'),
        ('nearest_synagogue_km', 'REAL'),
        ('nearest_hindu_temple_km', 'REAL'),
        ('nearest_buddhist_temple_km', 'REAL'),
        ('nearest_sikh_gurdwara_km', 'REAL'),
        ('nearest_other_faith_km', 'REAL'),
        ('same_faith_count_1km', 'INTEGER'),
        ('same_faith_count_5km', 'INTEGER'),
        ('same_faith_count_10km', 'INTEGER'),
        ('nearest_same_tradition_km', 'REAL'),
        ('same_tradition_count_5km', 'INTEGER'),
        ('interfaith_updated', 'TEXT'),
    ]
    for col_name, col_type in columns:
        try:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col_name} {col_type}')
            print(f'  Added: {col_name}')
        except sqlite3.OperationalError:
            pass  # column already exists

    db.commit()

    # ── Step 4: Compute all distances ──────────────────────────────────
    print(f"\n[4/5] Computing interfaith proximity + density...")
    t0 = time.time()

    CHUNK = 5000
    all_coords = np.array([(ch['lat'], ch['lon']) for ch in churches])
    all_xyz = latlon_to_xyz(all_coords)

    # Pre-compute chord radii
    chord_1km = km_to_chord(1.0)
    chord_5km = km_to_chord(5.0)
    chord_10km = km_to_chord(10.0)

    # Faith-to-faith mapping for interfaith queries
    FAITH_TREE_MAP = {
        'Islam': 'nearest_mosque_km',
        'Judaism': 'nearest_synagogue_km',
        'Hindu': 'nearest_hindu_temple_km',
        'Buddhist': 'nearest_buddhist_temple_km',
        'Sikh': 'nearest_sikh_gurdwara_km',
    }

    for chunk_start in range(0, total, CHUNK):
        chunk_end = min(chunk_start + CHUNK, total)
        chunk_xyz = all_xyz[chunk_start:chunk_end]
        chunk_churches = churches[chunk_start:chunk_end]

        results = []  # list of (col_values_dict, church_id)

        for i_local, ch in enumerate(chunk_churches):
            xyz_pt = chunk_xyz[i_local:i_local+1]  # shape (1,3) for query
            my_faith = ch['faith']
            my_tid = ch['tradition_id']
            vals = {}

            # ── Interfaith proximity ───────────────────────────────────
            other_faith_dists = []

            for target_faith, col_name in FAITH_TREE_MAP.items():
                tree = faith_trees.get(target_faith)
                if tree is not None and target_faith != my_faith:
                    chord_dist, _ = tree.query(xyz_pt, k=1)
                    km_dist = round(float(chord_to_km(chord_dist[0])), 4)
                    vals[col_name] = km_dist
                    other_faith_dists.append(km_dist)
                else:
                    vals[col_name] = None

            # nearest_other_faith_km = min of all interfaith distances
            if other_faith_dists:
                vals['nearest_other_faith_km'] = round(min(other_faith_dists), 4)
            else:
                vals['nearest_other_faith_km'] = None

            # ── Same-faith density ─────────────────────────────────────
            own_tree = faith_trees.get(my_faith)
            if own_tree is not None:
                # query_ball_point returns indices of neighbors within radius
                within_1km = own_tree.query_ball_point(xyz_pt[0], chord_1km)
                within_5km = own_tree.query_ball_point(xyz_pt[0], chord_5km)
                within_10km = own_tree.query_ball_point(xyz_pt[0], chord_10km)

                # Subtract 1 for self (the church itself at distance 0)
                vals['same_faith_count_1km'] = max(0, len(within_1km) - 1)
                vals['same_faith_count_5km'] = max(0, len(within_5km) - 1)
                vals['same_faith_count_10km'] = max(0, len(within_10km) - 1)
            else:
                vals['same_faith_count_1km'] = 0
                vals['same_faith_count_5km'] = 0
                vals['same_faith_count_10km'] = 0

            # ── Same-tradition proximity ───────────────────────────────
            if my_tid and my_tid in tradition_trees:
                trad_tree = tradition_trees[my_tid]
                if trad_tree.n >= 2:
                    # k=2: skip self (always at distance 0), take second-nearest
                    chord_dists, _ = trad_tree.query(xyz_pt, k=2)
                    # chord_dists shape is (1, 2) — take [0, 1] for second-nearest
                    if chord_dists.shape[1] >= 2:
                        vals['nearest_same_tradition_km'] = round(float(chord_to_km(chord_dists[0, 1])), 4)
                    else:
                        vals['nearest_same_tradition_km'] = None
                else:
                    vals['nearest_same_tradition_km'] = None

                within_trad_5km = trad_tree.query_ball_point(xyz_pt[0], chord_5km)
                vals['same_tradition_count_5km'] = max(0, len(within_trad_5km) - 1)
            else:
                vals['nearest_same_tradition_km'] = None
                vals['same_tradition_count_5km'] = None

            results.append((vals, ch['id']))

        # ── Batch UPDATE ───────────────────────────────────────────────
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        # Group results by column for efficient batch updates
        col_batches = defaultdict(list)
        for vals, cid in results:
            for col_name, value in vals.items():
                if value is not None:
                    col_batches[col_name].append((value, cid))

        for col_name, batch in col_batches.items():
            db.executemany(
                f'UPDATE churches SET {col_name}=? WHERE id=?',
                batch
            )

        # Set timestamp for all in chunk
        chunk_ids = [(now, ch['id']) for ch in chunk_churches]
        db.executemany(
            "UPDATE churches SET interfaith_updated=? WHERE id=?",
            chunk_ids
        )

        db.commit()

        elapsed = time.time() - t0
        rate = chunk_end / elapsed if elapsed > 0 else 0
        progress_bar(chunk_end, total, f'Computing ({rate:.0f}/s)')

    elapsed = time.time() - t0
    print(f'\n  Computed in {elapsed:.0f}s ({total/elapsed:.0f} churches/s)')

    # ── Step 5: Summary stats ──────────────────────────────────────────
    print(f"\n[5/5] Summary statistics:")

    stats_queries = [
        ("Mosque proximity", "nearest_mosque_km"),
        ("Synagogue proximity", "nearest_synagogue_km"),
        ("Hindu temple proximity", "nearest_hindu_temple_km"),
        ("Buddhist temple proximity", "nearest_buddhist_temple_km"),
        ("Sikh gurdwara proximity", "nearest_sikh_gurdwara_km"),
        ("Other faith proximity", "nearest_other_faith_km"),
        ("Same-tradition proximity", "nearest_same_tradition_km"),
    ]

    for label, col in stats_queries:
        row = db.execute(f"""
            SELECT COUNT(*), ROUND(AVG({col}),2), ROUND(MIN({col}),4), ROUND(MAX({col}),1)
            FROM churches WHERE {col} IS NOT NULL
        """).fetchone()
        if row and row[0] > 0:
            print(f"  {label:30s}: avg={row[1]} km, min={row[2]} km, max={row[3]} km  ({row[0]:,} filled)")

    # Density stats
    for col in ['same_faith_count_1km', 'same_faith_count_5km', 'same_faith_count_10km']:
        row = db.execute(f"""
            SELECT ROUND(AVG({col}),1), MAX({col})
            FROM churches WHERE {col} IS NOT NULL
        """).fetchone()
        if row:
            print(f"  {col:30s}: avg={row[0]}, max={row[1]}")

    # Trad density
    row = db.execute("""
        SELECT ROUND(AVG(same_tradition_count_5km),1), MAX(same_tradition_count_5km)
        FROM churches WHERE same_tradition_count_5km IS NOT NULL
    """).fetchone()
    if row:
        print(f"  {'same_tradition_count_5km':30s}: avg={row[0]}, max={row[1]}")

    # ── Provenance ─────────────────────────────────────────────────────
    enriched = db.execute(
        "SELECT COUNT(*) FROM churches WHERE interfaith_updated IS NOT NULL"
    ).fetchone()[0]

    db.execute(
        "INSERT INTO provenance_log (source, script_name, started_at, completed_at, "
        "churches_updated, fields_populated, status, notes) VALUES (?,?,?,?,?,?,?,?)",
        (
            "interfaith_cKDTree",
            "build_interfaith_layer.py",
            datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            enriched,
            "nearest_mosque_km,nearest_synagogue_km,nearest_hindu_temple_km,"
            "nearest_buddhist_temple_km,nearest_sikh_gurdwara_km,nearest_other_faith_km,"
            "same_faith_count_1km,same_faith_count_5km,same_faith_count_10km,"
            "nearest_same_tradition_km,same_tradition_count_5km,interfaith_updated",
            "completed",
            f"Pure cKDTree self-join. {enriched:,} churches enriched. "
            f"7 faith trees + {trad_count} tradition trees. {elapsed:.0f}s runtime."
        )
    )
    db.commit()

    db.close()
    print(f"\n{'='*60}")
    print(f"  Interfaith layer complete. {enriched:,} churches enriched.")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

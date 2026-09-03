"""
Euclidean catchment: population within fixed-radius buffers around US churches.

Uses Census 2020 tract centroids (mean center of population) + tract_lookup_us
population. Computes per-church population counts at 5/10/15/20/30 km radii.
All computation in-memory; results saved to parquet.

Output: data/catchment_euclidean.parquet with columns:
  church_rowid, pop_05km, pop_10km, pop_15km, pop_20km, pop_30km

To apply to DB: run with --apply
"""

import sqlite3
import numpy as np
from scipy.spatial import cKDTree
import pandas as pd
import sys, os, time

DB_PATH = r"E:\grid\churches.db"
OUT_PATH = r"E:\grid\data\catchment_euclidean.parquet"
RADII_KM = [5, 10, 15, 20, 30]
R_EARTH_KM = 6371.0

def latlon_to_xyz(lat, lon):
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)
    return np.column_stack([
        np.cos(lat_r) * np.cos(lon_r),
        np.cos(lat_r) * np.sin(lon_r),
        np.sin(lat_r)
    ])

def xyz_dist_to_km(church_xyz, tract_xyz_batch):
    chord = np.sqrt(np.sum((tract_xyz_batch - church_xyz) ** 2, axis=1))
    chord = np.clip(chord, 0, 2.0)
    return 2 * R_EARTH_KM * np.arcsin(chord / 2)

def progress_bar(i, n, label="", width=40):
    pct = i / n
    filled = int(width * pct)
    bar = '#' * filled + '-' * (width - filled)
    return f"[{bar}] {i:,d}/{n:,d} {100*pct:.1f}% {label}"

def compute():
    """Phase 1: Compute catchments in-memory, save to parquet."""
    t0 = time.time()
    
    print("Loading Census tract centroids...")
    df = pd.read_csv(
        'E:/grid/data/CenPop2020_Mean_TR.txt',
        dtype={'STATEFP': str, 'COUNTYFP': str, 'TRACTCE': str}
    )
    df['tract_fips'] = df['STATEFP'].str.zfill(2) + df['COUNTYFP'].str.zfill(3) + df['TRACTCE'].str.zfill(6)
    print(f"  {len(df):,d} tract centroids loaded")
    
    print("Joining with tract_lookup_us population...")
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.execute("PRAGMA busy_timeout=10000")
    tract_data = {}
    for row in db.execute("SELECT tract_fips, total_pop, households FROM tract_lookup_us"):
        tract_data[row[0]] = (row[1] or 0, row[2] or 0)
    print(f"  {len(tract_data):,d} tracts with ACS population in DB")
    
    df['acs_pop'] = df['tract_fips'].map(lambda x: tract_data.get(x, (0, 0))[0])
    df['effective_pop'] = np.where(df['acs_pop'] > 0, df['acs_pop'].astype(float), df['POPULATION'].astype(float))
    
    matched = (df['acs_pop'] > 0).sum()
    print(f"  {matched:,d} tracts matched to ACS ({100*matched/len(df):.1f}%)")
    print(f"  Total population (ACS+Census fallback): {df['effective_pop'].sum():,.0f}")
    
    print("Building cKDTree...")
    tract_coords = latlon_to_xyz(df['LATITUDE'].values, df['LONGITUDE'].values)
    tree = cKDTree(tract_coords)
    tract_pops = df['effective_pop'].values
    
    print("Loading US churches...")
    church_rows = db.execute("""
        SELECT rowid, latitude, longitude
        FROM churches
        WHERE country = 'US' AND latitude IS NOT NULL AND longitude IS NOT NULL
    """).fetchall()
    db.close()
    print(f"  {len(church_rows):,d} US churches with GPS")
    
    church_rowids = np.array([r[0] for r in church_rows], dtype=np.int64)
    church_coords = latlon_to_xyz(
        np.array([r[1] for r in church_rows]),
        np.array([r[2] for r in church_rows])
    )
    
    max_radius = max(RADII_KM)
    max_chord = 2 * np.sin(max_radius / (2 * R_EARTH_KM))
    
    print(f"\nComputing Euclidean catchments for {len(church_rowids):,d} churches...")
    print(f"  Radii: {RADII_KM} km  |  Max query radius: {max_radius} km (chord={max_chord:.4f})")
    
    n_churches = len(church_rowids)
    results = {f'pop_{r:02d}km': np.zeros(n_churches, dtype=np.int32) for r in RADII_KM}
    results['church_rowid'] = church_rowids
    
    chunk = 5000
    n_chunks = (n_churches + chunk - 1) // chunk
    
    for c in range(n_chunks):
        start = c * chunk
        end = min(start + chunk, n_churches)
        
        chunk_coords = church_coords[start:end]
        ball_results = tree.query_ball_point(chunk_coords, max_chord, workers=1)
        
        for i_local, tract_idxs in enumerate(ball_results):
            i_global = start + i_local
            if not tract_idxs:
                continue
            
            tract_xyz = tract_coords[tract_idxs]
            church_xyz = chunk_coords[i_local]
            dists = xyz_dist_to_km(church_xyz, tract_xyz)
            
            for radius_km in RADII_KM:
                mask = dists <= radius_km
                results[f'pop_{radius_km:02d}km'][i_global] = int(tract_pops[tract_idxs][mask].sum())
        
        if c % 20 == 0 or c == n_chunks - 1:
            elapsed = time.time() - t0
            rate = end / elapsed if elapsed > 0 else 0
            eta = (n_churches - end) / rate if rate > 0 else 0
            print(f"  {progress_bar(end, n_churches)}  {rate:,.0f} ch/s  ETA {eta:.0f}s")
    
    elapsed_compute = time.time() - t0
    print(f"\n[DONE] {n_churches:,d} churches computed in {elapsed_compute:.0f}s ({n_churches/elapsed_compute:,.0f} ch/s)")
    
    out_df = pd.DataFrame(results)
    out_df.to_parquet(OUT_PATH, index=False)
    print(f"[OK] Saved to {OUT_PATH} ({os.path.getsize(OUT_PATH)/1024/1024:.1f} MB)")
    
    # Summary stats
    print("\n=== Summary Statistics ===")
    for r in RADII_KM:
        col = f'pop_{r:02d}km'
        vals = results[col]
        nonzero = vals[vals > 0]
        print(f"  {r:2d}km:  mean={vals.mean():,.0f}  median={np.median(vals):,.0f}  "
              f"max={vals.max():,d}  zero={len(vals)-len(nonzero):,d} ({100*(len(vals)-len(nonzero))/len(vals):.1f}%)")
    
    # Sample
    print("\n=== Sample (first 20 churches) ===")
    for i in range(min(20, n_churches)):
        pops = ', '.join(f'{r}km={results[f"pop_{r:02d}km"][i]:,d}' for r in RADII_KM)
        print(f"  rowid={church_rowids[i]:>8d}  {pops}")
    
    print(f"\n[READY] To apply to DB, run: python {__file__} --apply")


def apply_to_db():
    """Phase 2: Apply computed catchments to churches table."""
    print(f"Loading {OUT_PATH}...")
    df = pd.read_parquet(OUT_PATH)
    print(f"  {len(df):,d} rows loaded")
    
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.execute("PRAGMA busy_timeout=30000")
    
    # Ensure columns exist
    existing = [r[1] for r in db.execute("PRAGMA table_info(churches)")]
    for r in RADII_KM:
        col = f'pop_{r:02d}km'
        if col not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} INTEGER")
            print(f"  Added column: {col}")
    if 'catchment_updated' not in existing:
        db.execute("ALTER TABLE churches ADD COLUMN catchment_updated TEXT")
        print("  Added column: catchment_updated")
    db.commit()
    
    print("Applying catchments to DB...")
    t0 = time.time()
    chunk = 500
    for start in range(0, len(df), chunk):
        end = min(start + chunk, len(df))
        batch = df.iloc[start:end]
        
        for _, row in batch.iterrows():
            sets = ', '.join(f'pop_{r:02d}km={int(row[f"pop_{r:02d}km"])}' for r in RADII_KM)
            db.execute(
                f"UPDATE churches SET {sets}, catchment_updated=datetime('now') WHERE rowid=?",
                (int(row['church_rowid']),)
            )
        
        if start % 10000 == 0:
            db.commit()
            pct = 100 * end / len(df)
            elapsed = time.time() - t0
            rate = end / elapsed if elapsed > 0 else 0
            print(f"  {progress_bar(end, len(df))}  {rate:,.0f} ch/s")
    
    db.commit()
    elapsed = time.time() - t0
    print(f"\n[DONE] Applied to DB in {elapsed:.0f}s ({len(df)/elapsed:,.0f} ch/s)")
    
    # Provenance
    import gw_db
    gw_db.ensure_provenance_tables()
    pdb = gw_db.connect()
    pdb.execute(
        "INSERT INTO provenance_log (source, description, row_count, created_at) VALUES (?,?,?,datetime('now'))",
        ("euclidean_catchment",
         f"Euclidean population catchment at radii {RADII_KM} km for {len(df):,d} US churches",
         len(df))
    )
    pdb.commit()
    pdb.close()
    
    # WAL checkpoint
    db.commit()
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    print("[OK] Provenance logged, WAL checkpointed.")


if __name__ == '__main__':
    if '--apply' in sys.argv:
        apply_to_db()
    else:
        compute()

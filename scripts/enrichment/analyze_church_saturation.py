"""
Church Market Saturation Analysis
=================================
Identifies over-churched and under-churched areas using:
  - 300 people per house of worship (HOW) standard
  - 5km Euclidean catchment (neighborhood scale, ~5-8 min drive)

Core metric (per church):
  demand  = pop_05km                     (people living within 5km)
  supply  = n_churches_5km * 300         (capacity of ALL churches sharing that catchment)
  saturation_ratio = demand / supply
    ratio > 1.0  -> UNDER-churched (population could support more churches)
    ratio < 1.0  -> OVER-churched  (more church capacity than population)

Outputs:
  1. Per-church saturation ratio (supply-adjusted)
  2. County-level aggregation: population, church count, county-level ratio
  3. Church clusters (DBSCAN): cluster-level over/under-churched analysis
  4. Top-N most over/under-churched areas

Data sources:
  - data/catchment_euclidean.parquet (940K US churches, pop_05km..pop_30km)
  - churches.db (metadata, county_fips, denomination)
  - rucc_codes (rural/urban classification)
  - county_census_us (county population)
"""

import sqlite3
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.cluster import DBSCAN
import sys, os, time

DB_PATH = r"E:\grid\churches.db"
PARQUET = r"E:\grid\data\catchment_euclidean.parquet"
HOW_STANDARD = 300   # people per house of worship
CATCHMENT_KM = 5.0   # neighborhood scale (matches pop_05km)
CLUSTER_EPS_KM = 2.0 # DBSCAN proximity for church clusters
R_EARTH_KM = 6371.0

def latlon_to_xyz(lat, lon):
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)
    return np.column_stack([
        np.cos(lat_r) * np.cos(lon_r),
        np.cos(lat_r) * np.sin(lon_r),
        np.sin(lat_r)
    ])

def load_data():
    """Load catchment data + church metadata."""
    print("Loading catchment data...")
    cat = pd.read_parquet(PARQUET)
    print(f"  {len(cat):,d} churches with catchment data")
    
    print("Loading church metadata from DB...")
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.execute("PRAGMA busy_timeout=10000")
    
    rows = db.execute("""
        SELECT rowid, name, city, state, latitude, longitude, 
               county_fips_5, county, taxonomy_id, faith, tradition
        FROM churches
        WHERE country='US' AND latitude IS NOT NULL AND longitude IS NOT NULL
    """).fetchall()
    db.close()
    
    ch = pd.DataFrame(rows, columns=[
        'church_rowid', 'name', 'city', 'state', 'lat', 'lon',
        'county_fips', 'county_name', 'taxonomy_id', 'faith', 'tradition'
    ])
    print(f"  {len(ch):,d} churches with metadata")
    
    # Merge
    df = ch.merge(cat, on='church_rowid', how='inner')
    print(f"  {len(df):,d} churches merged\n")
    
    return df

def per_church_score(df):
    """Compute per-church saturation ratio: demand (pop) / supply (church capacity).

    supply side: count ALL churches within 5km of each church (including itself),
    multiply by HOW_STANDARD to get servable population. A church in a dense
    church cluster shares its catchment population with every neighbor.
    """
    print("=== Per-Church Saturation (5km neighborhood catchment) ===")
    print(f"  Counting churches within {CATCHMENT_KM:.0f}km of each church...")
    t0 = time.time()
    
    coords = latlon_to_xyz(df['lat'].values, df['lon'].values)
    tree = cKDTree(coords)
    max_chord = 2 * np.sin(CATCHMENT_KM / (2 * R_EARTH_KM))
    
    # return_length=True -> just the neighbor count (fast, low memory)
    n_churches_5km = tree.query_ball_point(coords, max_chord, return_length=True, workers=-1)
    df['n_churches_5km'] = n_churches_5km  # includes self, so always >= 1
    print(f"  {time.time()-t0:.1f}s — median churches within 5km: {np.median(n_churches_5km):.0f}, max: {n_churches_5km.max():,d}")
    
    # demand / supply
    df['supply_capacity'] = df['n_churches_5km'] * HOW_STANDARD
    df['saturation_ratio'] = df['pop_05km'] / df['supply_capacity']
    df['status'] = np.where(df['saturation_ratio'] > 2.0, 'UNDER-churched',
                   np.where(df['saturation_ratio'] < 0.5, 'OVER-churched', 'balanced'))
    
    print(f"  Ratio = pop_05km / (n_churches_5km x {HOW_STANDARD})")
    print(f"  UNDER-churched (ratio > 2.0): {(df['status']=='UNDER-churched').sum():,d} ({(df['status']=='UNDER-churched').mean()*100:.1f}%)")
    print(f"  OVER-churched (ratio < 0.5): {(df['status']=='OVER-churched').sum():,d} ({(df['status']=='OVER-churched').mean()*100:.1f}%)")
    print(f"  Balanced: {(df['status']=='balanced').sum():,d} ({(df['status']=='balanced').mean()*100:.1f}%)")
    print(f"  Median ratio: {df['saturation_ratio'].median():.2f}")
    print(f"  P10 ratio: {df['saturation_ratio'].quantile(0.1):.2f}")
    print(f"  P90 ratio: {df['saturation_ratio'].quantile(0.9):.2f}")
    
    # Zero-pop churches (truly rural)
    zero_pop = (df['pop_05km'] == 0).sum()
    print(f"  Zero pop within 5km: {zero_pop:,d} ({zero_pop/len(df)*100:.1f}%)\n")
    
    return df

def county_aggregation(df):
    """Aggregate to county level."""
    print("Loading county population & RUCC...")
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.execute("PRAGMA busy_timeout=10000")
    
    # County pop
    county_pop = {}
    for row in db.execute("SELECT county_fips, total_pop FROM county_census_us"):
        county_pop[row[0]] = row[1] or 0
    
    # RUCC codes
    print("  Loading RUCC codes...")
    rucc_cols = [r[1] for r in db.execute("PRAGMA table_info(rucc_codes)")]
    rucc = {}
    # Try common column names
    fips_col = next((c for c in rucc_cols if 'fips' in c.lower()), rucc_cols[0])
    code_col = next((c for c in rucc_cols if 'code' in c.lower() or 'rucc' in c.lower()), rucc_cols[1] if len(rucc_cols) > 1 else rucc_cols[0])
    desc_col = next((c for c in rucc_cols if 'desc' in c.lower()), rucc_cols[-1] if len(rucc_cols) > 2 else None)
    
    for row in db.execute(f"SELECT {fips_col}, {code_col}, {desc_col or 'NULL'} FROM rucc_codes"):
        rucc[row[0]] = (row[1], row[2] if desc_col else '')
    db.close()
    
    # Aggregate
    agg = df.groupby('county_fips').agg(
        n_churches=('church_rowid', 'count'),
        median_ratio=('saturation_ratio', 'median'),
        mean_ratio=('saturation_ratio', 'mean'),
        pct_underchurched=('status', lambda x: (x == 'UNDER-churched').mean()),
        pct_overchurched=('status', lambda x: (x == 'OVER-churched').mean()),
        median_pop05km=('pop_05km', 'median'),
        total_pop05km_sum=('pop_05km', 'sum'),
    ).reset_index()
    
    agg['county_pop'] = agg['county_fips'].map(lambda x: county_pop.get(x, 0))
    agg['rucc_code'] = agg['county_fips'].map(lambda x: rucc.get(x, (None, ''))[0])
    agg['rucc_desc'] = agg['county_fips'].map(lambda x: rucc.get(x, (None, ''))[1])
    
    # County-level underserved metric: county_pop / (n_churches * HOW_STANDARD)
    agg['county_score'] = np.where(
        agg['n_churches'] > 0,
        agg['county_pop'] / (agg['n_churches'] * HOW_STANDARD),
        np.nan
    )
    
    # Per-capita churches
    agg['churches_per_100k'] = np.where(
        agg['county_pop'] > 0,
        100_000 * agg['n_churches'] / agg['county_pop'],
        0
    )
    
    # Exclude tiny counties
    agg = agg[agg['n_churches'] >= 3].copy()
    
    print("=== County-Level Analysis (>=3 churches) ===")
    print(f"  Counties: {len(agg):,d}")
    
    # Most over-churched
    print("\n  TOP 15 OVER-CHURCHED COUNTIES (few people per church):")
    over = agg.nsmallest(15, 'county_score')
    for _, r in over.iterrows():
        pop_k = r['county_pop'] / 1000
        print(f"    {r['county_fips']} | {r['n_churches']:4d} churches | pop={pop_k:5.0f}K | "
              f"ratio={r['county_score']:.2f} | {r['rucc_desc'][:30] if pd.notna(r['rucc_desc']) else ''}")
    
    # Most under-churched
    print("\n  TOP 15 UNDER-CHURCHED COUNTIES (lots of people, few churches):")
    under = agg.nlargest(15, 'county_score')
    for _, r in under.iterrows():
        pop_k = r['county_pop'] / 1000
        print(f"    {r['county_fips']} | {r['n_churches']:4d} churches | pop={pop_k:5.0f}K | "
              f"ratio={r['county_score']:.2f} | {r['rucc_desc'][:30] if pd.notna(r['rucc_desc']) else ''}")
    
    return agg

def cluster_analysis(df):
    """DBSCAN cluster churches, analyze cluster-level saturation."""
    print("\n=== Church Cluster Analysis (DBSCAN, eps=2km) ===")
    
    # Convert lat/lon to km-based coordinates for DBSCAN
    lat_r = np.radians(df['lat'].values)
    lon_r = np.radians(df['lon'].values)
    
    # Approximate: 1 degree lat = 111.32 km, 1 degree lon = 111.32 * cos(lat) km
    x_km = lon_r * 111.32 * np.cos(lat_r)
    y_km = lat_r * 111.32
    coords_km = np.column_stack([x_km, y_km])
    
    print(f"  Clustering {len(df):,d} churches...")
    t0 = time.time()
    clustering = DBSCAN(eps=CLUSTER_EPS_KM, min_samples=3, n_jobs=-1).fit(coords_km)
    elapsed = time.time() - t0
    print(f"  {elapsed:.1f}s — {clustering.labels_.max() + 1:,d} clusters found")
    
    df['cluster_id'] = clustering.labels_
    
    # Cluster stats
    clustered = df[df['cluster_id'] >= 0]
    cluster_stats = clustered.groupby('cluster_id').agg(
        n_churches=('church_rowid', 'count'),
        median_ratio=('saturation_ratio', 'median'),
        mean_ratio=('saturation_ratio', 'mean'),
        median_pop05km=('pop_05km', 'median'),
        mean_lat=('lat', 'mean'),
        mean_lon=('lon', 'mean'),
        sample_names=('name', lambda x: ' | '.join(x.head(3).str[:30])),
        sample_city=('city', lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]),
        sample_state=('state', lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]),
    ).reset_index()
    
    # Cluster score: median of per-church saturation ratios (already supply-adjusted)
    cluster_stats['cluster_score'] = cluster_stats['median_ratio']
    
    # Only show clusters with meaningful church counts
    sig = cluster_stats[cluster_stats['n_churches'] >= 5]
    
    print(f"  Significant clusters (>=5 churches): {len(sig):,d}")
    
    print("\n  TOP 10 OVER-CHURCHED CLUSTERS (more church capacity than population):")
    for _, r in sig.nsmallest(10, 'cluster_score').iterrows():
        print(f"    cluster={r['cluster_id']:5d} | {r['n_churches']:3d} churches | "
              f"median pop05km={r['median_pop05km']:>7,.0f} | "
              f"ratio={r['cluster_score']:.2f} | "
              f"{r['sample_city']}, {r['sample_state']} | {r['sample_names'][:80]}")
    
    print("\n  TOP 10 UNDER-CHURCHED CLUSTERS (population could support more churches):")
    for _, r in sig.nlargest(10, 'cluster_score').iterrows():
        print(f"    cluster={r['cluster_id']:5d} | {r['n_churches']:3d} churches | "
              f"median pop05km={r['median_pop05km']:>7,.0f} | "
              f"ratio={r['cluster_score']:.2f} | "
              f"{r['sample_city']}, {r['sample_state']} | {r['sample_names'][:80]}")
    
    return df, cluster_stats

def save_outputs(df, county_agg, cluster_stats):
    """Save results for mapping."""
    out_dir = 'E:/grid/outputs/church_saturation'
    os.makedirs(out_dir, exist_ok=True)
    
    # Per-church (sample: top over/under among populated areas)
    populated = df[df['pop_05km'] > 0]
    sample = pd.concat([
        populated.nsmallest(1000, 'saturation_ratio'),
        populated.nlargest(1000, 'saturation_ratio'),
    ]).drop_duplicates()
    sample[['church_rowid', 'name', 'city', 'state', 'lat', 'lon', 
            'pop_05km', 'n_churches_5km', 'saturation_ratio', 'status', 'cluster_id']].to_csv(
        f'{out_dir}/church_scores_sample.csv', index=False)
    
    # County aggregation
    county_agg.to_csv(f'{out_dir}/county_saturation.csv', index=False)
    
    # Cluster stats
    cluster_stats.to_csv(f'{out_dir}/cluster_saturation.csv', index=False)
    
    # Full church scores (compressed)
    df[['church_rowid', 'name', 'city', 'state', 'lat', 'lon',
        'pop_05km', 'n_churches_5km', 'saturation_ratio', 'status', 'cluster_id']].to_parquet(
        f'{out_dir}/church_scores_full.parquet', index=False)
    
    print(f"\n[OK] Outputs saved to {out_dir}/")
    print(f"  church_scores_full.parquet — all {len(df):,d} churches")
    print(f"  church_scores_sample.csv — top/bottom 1,000")
    print(f"  county_saturation.csv — {len(county_agg):,d} counties")
    print(f"  cluster_saturation.csv — {len(cluster_stats):,d} clusters")

def main():
    t0 = time.time()
    df = load_data()
    
    df = per_church_score(df)
    county_agg = county_aggregation(df)
    df, cluster_stats = cluster_analysis(df)
    
    save_outputs(df, county_agg, cluster_stats)
    
    elapsed = time.time() - t0
    print(f"\n[DONE] Total time: {elapsed:.0f}s")

if __name__ == '__main__':
    main()

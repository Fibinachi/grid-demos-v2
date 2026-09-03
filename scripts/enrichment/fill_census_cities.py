"""
Fill US city names via Census Places spatial join + download ZCTA shapefile.

Step 1: Download Census Places shapefile, spatial-join churches to nearest place
Step 2: Download ZCTA shapefile for future ZIP-based lookups

Uses geopandas + STRtree for fast point-in-polygon matching.
Target: 151K US null-city records from Amchitka fix.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import sqlite3
import urllib.request
import tempfile
import zipfile
import io
import os
import time

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely import STRtree
from tqdm import tqdm

DB_PATH = Path(__file__).resolve().parents[2] / "churches.db"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "census"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Census shapefile URLs (2023 vintage, 500k resolution)
PLACES_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_place_500k.zip"
ZCTA_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_zcta520_500k.zip"

CHUNK_SIZE = 500

def download_and_load(url, name):
    """Download a Census shapefile ZIP and return GeoDataFrame."""
    zip_path = DATA_DIR / f"{name}.zip"
    if not zip_path.exists():
        print(f"  Downloading {name} from Census...")
        urllib.request.urlretrieve(url, zip_path)
        print(f"  Saved: {zip_path}")
    else:
        print(f"  Using cached: {zip_path}")
    
    print(f"  Loading {name} shapefile...")
    gdf = gpd.read_file(zip_path)
    print(f"  Loaded: {len(gdf):,} features")
    return gdf

def spatial_join_cities(db_path, places_gdf, target_ids):
    """Spatial-join target churches to Census Places. Returns dict of church_id -> city_name."""
    print(f"\n=== Spatial Join: {len(target_ids):,} churches → {len(places_gdf):,} places ===")
    
    # Build point geometries for target churches
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA journal_mode=WAL")
    
    placeholders = ','.join(['?' for _ in target_ids])
    rows = db.execute(
        f"SELECT id, latitude, longitude, name FROM churches WHERE id IN ({placeholders}) AND latitude IS NOT NULL",
        target_ids
    ).fetchall()
    db.close()
    
    if not rows:
        print("  No churches to process!")
        return {}
    
    print(f"  {len(rows):,} churches with coordinates")
    
    # Build points GeoDataFrame
    pts_gdf = gpd.GeoDataFrame({
        'church_id': [r[0] for r in rows],
        'name': [r[3] or '' for r in rows],
        'geometry': [Point(r[2], r[1]) for r in rows]  # lon, lat for Point
    }, crs="EPSG:4326")
    
    # Reproject both to match CRS
    places_gdf = places_gdf.to_crs("EPSG:4326")
    
    # Build spatial index and do point-in-polygon join
    print("  Building STRtree index...")
    tree = STRtree(places_gdf.geometry.values)
    geom_arr = places_gdf.geometry.values
    
    # Get place name column
    name_col = 'NAME' if 'NAME' in places_gdf.columns else 'NAMELSAD'
    
    results = {}
    for _, row in tqdm(pts_gdf.iterrows(), total=len(pts_gdf), desc="  Matching", unit='rec'):
        pt = row.geometry
        idxs = tree.query(pt, predicate='intersects')
        if len(idxs) > 0:
            # Take the first (smallest area typically)
            place_name = places_gdf.iloc[idxs[0]][name_col]
            results[row['church_id']] = place_name
    
    print(f"  Matched: {len(results):,} / {len(pts_gdf):,} ({len(results)/len(pts_gdf)*100:.1f}%)")
    return results


def main():
    start = time.time()
    
    # ── Step 1: Download places shapefile ──
    print("=" * 60)
    print("Step 1: Download Census Places shapefile")
    print("=" * 60)
    places_gdf = download_and_load(PLACES_URL, "cb_2023_us_place_500k")
    
    # ── Step 2: Download ZCTA shapefile ──
    print("\n" + "=" * 60)
    print("Step 2: Download ZCTA shapefile")
    print("=" * 60)
    zcta_gdf = download_and_load(ZCTA_URL, "cb_2023_us_zcta520_500k")
    print(f"  ZCTA columns: {list(zcta_gdf.columns)}")
    print(f"  ZCTA sample names: {zcta_gdf.iloc[:5]['ZCTA5CE20'].tolist() if 'ZCTA5CE20' in zcta_gdf.columns else 'N/A'}")
    
    # ── Step 3: Get target churches ──
    print("\n" + "=" * 60)
    print("Step 3: Get null-city US churches")
    print("=" * 60)
    db = sqlite3.connect(DB_PATH)
    target_ids = [r[0] for r in db.execute(
        "SELECT id FROM churches WHERE country='US' AND city IS NULL AND latitude IS NOT NULL"
    ).fetchall()]
    db.close()
    print(f"  Null-city US churches: {len(target_ids):,}")
    
    # ── Step 4: Spatial join ──
    print("\n" + "=" * 60)
    print("Step 4: Spatial join churches → Cities")
    print("=" * 60)
    matches = spatial_join_cities(DB_PATH, places_gdf, target_ids)
    
    # ── Step 5: Write results ──
    print("\n" + "=" * 60)
    print("Step 5: Write city names to DB")
    print("=" * 60)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    
    updated = 0
    batch = []
    for chid, city in tqdm(matches.items(), desc="  Writing", unit='rec'):
        batch.append((city, chid))
        if len(batch) >= CHUNK_SIZE:
            db.executemany("UPDATE churches SET city=? WHERE id=?", batch)
            db.commit()
            updated += len(batch)
            batch = []
    if batch:
        db.executemany("UPDATE churches SET city=? WHERE id=?", batch)
        db.commit()
        updated += len(batch)
    
    # Provenance
    elapsed = time.time() - start
    db.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, notes)
                  VALUES ('census_places_spatial_join','fill_census_cities.py',datetime('now'),datetime('now'),'completed',?)""",
               (f"Filled {updated:,} US city names via Census Places spatial join in {elapsed:.0f}s. "
                f"ZCTA shapefile cached at data/census/"))
    db.commit()
    
    remaining = db.execute(
        "SELECT COUNT(*) FROM churches WHERE country='US' AND city IS NULL AND latitude IS NOT NULL"
    ).fetchone()[0]
    db.close()
    
    print(f"\n=== DONE in {elapsed:.0f}s ===")
    print(f"  Cities filled: {updated:,}")
    print(f"  Remaining null: {remaining:,}")
    print(f"  ZCTA shapefile: {DATA_DIR / 'cb_2023_us_zcta520_500k.zip'}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Geocode TN religious parcels via Census single-address API (threaded), then match to GRID churches."""
import sqlite3, json, time, requests, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

STAGING_DB = Path("E:/grid/data/tn_parcels/tn_religious_parcels.db")
CHURCHES_DB = Path("E:/grid/churches.db")
MAX_WORKERS = 3  # Census API throttles at high concurrency
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

write_lock = threading.Lock()

def geocode_single(row_id, address_str):
    """Geocode a single address. Returns (id, lat, lon) or (id, None, None)."""
    try:
        r = requests.get(CENSUS_URL, params={
            "address": address_str,
            "benchmark": "Public_AR_Current",
            "format": "json",
        }, timeout=20)
        if r.status_code == 200:
            data = r.json()
            matches = data.get("result", {}).get("addressMatches", [])
            if matches:
                coords = matches[0].get("coordinates", {})
                return (row_id, coords.get("y"), coords.get("x"))
        elif r.status_code == 429:
            time.sleep(1)  # Rate limited
    except Exception:
        pass
    return (row_id, None, None)


def geocode_parcels():
    """Geocode all un-geocoded eligible parcels using threaded Census API."""
    conn = sqlite3.connect(str(STAGING_DB))
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT id, address, city, state, zip
        FROM tn_religious_parcels 
        WHERE tn_filter IN ('church','parsonage','religious_cemetery')
        AND latitude IS NULL
        AND address IS NOT NULL
    """).fetchall()
    conn.close()
    
    total = len(rows)
    print(f"Parcels to geocode: {total:,}")
    
    if not rows:
        return 0
    
    # Build address strings
    tasks = []
    for r in rows:
        addr = r["address"].strip()
        city = (r["city"] or "").strip()
        zipcode = (r["zip"] or "").strip()[:5] if r["zip"] else ""
        
        # Build clean address
        parts = [addr]
        if city:
            parts.append(city)
        parts.append("TN")
        if zipcode:
            parts.append(zipcode)
        address_str = ", ".join(parts)
        
        tasks.append((r["id"], address_str))
    
    # Threaded geocoding
    geocoded = 0
    failed = 0
    batch = []
    completed = 0
    
    print(f"  Using {MAX_WORKERS} threads...")
    t0 = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(geocode_single, tid, addr): tid for tid, addr in tasks}
        
        for future in as_completed(futures):
            rid, lat, lon = future.result()
            completed += 1
            
            if lat is not None:
                batch.append((lat, lon, rid))
                geocoded += 1
            else:
                failed += 1
            
            # Commit every 500
            if len(batch) >= 500:
                with write_lock:
                    conn = sqlite3.connect(str(STAGING_DB))
                    conn.executemany(
                        "UPDATE tn_religious_parcels SET latitude=?, longitude=?, geocode_source='census_2026' WHERE id=?",
                        batch,
                    )
                    conn.commit()
                    conn.close()
                batch = []
            
            if completed % 500 == 0 or (completed < 500 and completed % 50 == 0):
                elapsed = time.time() - t0
                rate = completed / elapsed
                pct = completed / total * 100
                eta = (total - completed) / rate
                print(f"  {completed:>7,}/{total:,} ({pct:.0f}%) | {rate:.0f}/s | match: {geocoded/completed*100:.0f}% | ETA: {eta:.0f}s")
    
    # Final commit
    if batch:
        conn = sqlite3.connect(str(STAGING_DB))
        conn.executemany(
            "UPDATE tn_religious_parcels SET latitude=?, longitude=?, geocode_source='census_2026' WHERE id=?",
            batch,
        )
        conn.commit()
        conn.close()
    
    elapsed = time.time() - t0
    print(f"\n{'=' * 50}")
    print(f"Geocoded: {geocoded:,}  |  Failed: {failed:,}  |  Rate: {geocoded/total*100:.1f}%")
    print(f"Time: {elapsed:.0f}s ({total/elapsed:.0f} addr/s)")
    return geocoded


def match_to_grid():
    """Match geocoded TN parcels to churches.db by name + proximity."""
    print(f"\n{'=' * 60}")
    print("MATCHING TO GRID CHURCHES")
    print(f"{'=' * 60}")
    
    tn = sqlite3.connect(str(STAGING_DB))
    tn.row_factory = sqlite3.Row
    
    # Get geocoded parcels
    parcels = tn.execute("""
        SELECT id, name, address, city, latitude, longitude, tn_county, tn_parcel_id,
               tn_appraisal_value, tn_landuse
        FROM tn_religious_parcels 
        WHERE tn_filter IN ('church','parsonage','religious_cemetery')
        AND latitude IS NOT NULL
    """).fetchall()
    
    print(f"Geocoded parcels to match: {len(parcels):,}")
    
    # Load TN churches from GRID
    grid = sqlite3.connect(str(CHURCHES_DB))
    tn_churches = grid.execute("""
        SELECT id, name, address, city, latitude, longitude, landmark_type, tradition
        FROM churches 
        WHERE state = 'TN' AND country = 'US'
        AND latitude IS NOT NULL
    """).fetchall()
    
    print(f"TN churches in GRID: {len(tn_churches):,}")
    
    # Build spatial index with scipy
    import numpy as np
    from scipy.spatial import cKDTree
    
    # Convert lat/lon to 3D cartesian for fast Haversine proximity
    def latlon_to_xyz(lat, lon):
        R = 6371.0
        lat_r, lon_r = np.radians(lat), np.radians(lon)
        x = R * np.cos(lat_r) * np.cos(lon_r)
        y = R * np.cos(lat_r) * np.sin(lon_r)
        z = R * np.sin(lat_r)
        return np.array([x, y, z])
    
    grid_coords = []
    grid_data = []
    for c in tn_churches:
        try:
            lat, lon = float(c[4]), float(c[5])
            grid_coords.append(latlon_to_xyz(lat, lon))
            grid_data.append({
                "id": c[0], "name": (c[1] or "").lower(),
                "address": (c[2] or "").lower(), "city": (c[3] or "").lower(),
                "lat": lat, "lon": lon,
                "landmark_type": c[6], "tradition": c[7],
            })
        except (ValueError, TypeError):
            continue
    
    tree = cKDTree(grid_coords)
    print(f"  KD-tree built: {len(grid_coords):,} points")
    
    # Match each parcel
    matches = []
    exact_name = 0
    fuzzy_name = 0
    proximity_only = 0
    no_match = 0
    
    from rapidfuzz import fuzz
    
    for p in parcels:
        try:
            p_lat = float(p["latitude"])
            p_lon = float(p["longitude"])
        except (ValueError, TypeError):
            no_match += 1
            continue
        
        p_name = (p["name"] or "").lower()
        p_city = (p["city"] or "").lower()
        p_xyz = latlon_to_xyz(p_lat, p_lon)
        
        # Find nearest 10 churches by distance
        dists, idxs = tree.query(p_xyz, k=min(10, len(grid_coords)))
        if not hasattr(dists, '__iter__'):
            dists = [dists]
            idxs = [idxs]
        
        best_score = 0
        best_match = None
        best_dist = None
        
        for dist_km, idx in zip(dists, idxs):
            gc = grid_data[idx]
            
            # Score: name similarity (70%) + distance proximity (30%)
            name_score = fuzz.token_sort_ratio(p_name, gc["name"]) / 100.0
            
            # Distance score: 1.0 at 0km, 0.0 at 5km+
            dist_score = max(0, 1.0 - dist_km / 5.0)
            
            # City bonus
            city_bonus = 0.15 if p_city and gc["city"] and gc["city"] in p_city else 0
            
            combined = name_score * 0.7 + dist_score * 0.3 + city_bonus
            
            if combined > best_score:
                best_score = combined
                best_match = gc
                best_dist = dist_km
        
        if best_score >= 0.85:
            match_type = "exact_name" if best_score >= 0.95 else "fuzzy_name"
            if best_score >= 0.95:
                exact_name += 1
            else:
                fuzzy_name += 1
        elif best_dist and best_dist < 0.5 and best_score >= 0.5:
            match_type = "proximity"
            proximity_only += 1
        else:
            match_type = None
            best_match = None
            no_match += 1
        
        if best_match and match_type:
            matches.append({
                "tn_id": p["id"],
                "church_id": best_match["id"],
                "match_type": match_type,
                "score": round(best_score, 3),
                "dist_km": round(best_dist, 3) if best_dist else None,
            })
    
    # Write matches to DB
    tn.execute("DROP TABLE IF EXISTS tn_grid_matches")
    tn.execute("""
        CREATE TABLE tn_grid_matches (
            tn_parcel_id INTEGER PRIMARY KEY,
            church_id INTEGER,
            match_type TEXT,
            score REAL,
            dist_km REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    for m in matches:
        tn.execute(
            "INSERT INTO tn_grid_matches (tn_parcel_id, church_id, match_type, score, dist_km) VALUES (?,?,?,?,?)",
            (m["tn_id"], m["church_id"], m["match_type"], m["score"], m["dist_km"]),
        )
    
    tn.commit()
    
    # Also update tn_religious_parcels.grid_church_id
    tn.execute("UPDATE tn_religious_parcels SET grid_church_id = NULL")
    for m in matches:
        tn.execute(
            "UPDATE tn_religious_parcels SET grid_church_id = ? WHERE id = ?",
            (m["church_id"], m["tn_id"]),
        )
    tn.commit()
    
    tn.close()
    grid.close()
    
    print(f"\n{'=' * 50}")
    print(f"MATCH RESULTS")
    print(f"{'=' * 50}")
    print(f"  Exact name match:  {exact_name:>8,}")
    print(f"  Fuzzy name match:  {fuzzy_name:>8,}")
    print(f"  Proximity only:    {proximity_only:>8,}")
    print(f"  No match:          {no_match:>8,}")
    print(f"  Total matched:     {len(matches):>8,} ({len(matches)/len(parcels)*100:.1f}%)")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--geocode", action="store_true", help="Geocode parcels")
    parser.add_argument("--match", action="store_true", help="Match to GRID churches")
    parser.add_argument("--all", action="store_true", help="Geocode + match")
    
    args = parser.parse_args()
    
    if not args.geocode and not args.match:
        args.all = True
    
    if args.geocode or args.all:
        geocode_parcels()
    
    if args.match or args.all:
        match_to_grid()


if __name__ == "__main__":
    main()

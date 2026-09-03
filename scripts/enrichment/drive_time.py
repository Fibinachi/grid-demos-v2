#!/usr/bin/env python3
"""
GrantWizard Drive-Time Engine
==============================
Queries the OSRM server (running on EC2) for drive-time isochrones.

Usage:
    python drive_time.py                      # test single church
    python drive_time.py --batch 10           # process first 10 churches
    python drive_time.py --all                # process all with lat/lng
    python drive_time.py --radius 5,10,20     # set drive-time radii

Requires:
    OSRM server running at OSRM_HOST (set via env or default)
"""

import urllib.request, json, time, os, sqlite3, csv, math

DB_PATH = r"E:\grid\churches.db"
OUT_DIR = r"E:\grid\data\drive_times"
os.makedirs(OUT_DIR, exist_ok=True)

# OSRM server - update this to your EC2 IP
OSRM_HOST = os.environ.get("OSRM_HOST", "3.16.45.190")
OSRM_PORT = 5000

def route_time(src_lat, src_lng, dst_lat, dst_lng):
    """Get drive time (seconds) between two points via OSRM."""
    url = f"http://{OSRM_HOST}:{OSRM_PORT}/route/v1/driving/{src_lng},{src_lat};{dst_lng},{dst_lat}?overview=false"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("code") == "Ok" and data.get("routes"):
                return data["routes"][0]["duration"]  # seconds
    except:
        pass
    return None

def nearest_churches(lat, lng, limit=50, radius_miles=20):
    """Find nearest churches within radius (rough approximation)."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    deg = radius_miles / 69.0
    cur.execute("""
        SELECT id, name, latitude, longitude, city, state
        FROM churches 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND ABS(latitude - ?) < ? AND ABS(longitude - ?) < ?
        LIMIT ?
    """, (lat, deg, lng, deg, limit))
    rows = cur.fetchall()
    db.close()
    return rows

def compute_drive_times(church_id, lat, lng, radii_min=[5, 10, 20]):
    """For a church, count how many other churches are within each drive-time radius."""
    # Get all nearby churches by distance first
    nearby = nearest_churches(lat, lng, limit=100, radius_miles=30)
    
    results = {}
    for radius in radii_min:
        results[f"churches_{radius}min"] = 0
    
    for row in nearby:
        cid2, name2, lat2, lng2 = row[0], row[1], row[2], row[3]
        if cid2 == church_id:
            continue
        seconds = route_time(lat, lng, lat2, lng2)
        if seconds is None:
            continue
        minutes = seconds / 60.0
        for radius in radii_min:
            if minutes <= radius:
                results[f"churches_{radius}min"] += 1
        time.sleep(0.05)  # be nice to OSRM
    
    results["church_id"] = church_id
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=1, help="Number of churches to process")
    parser.add_argument("--all", action="store_true", help="Process all")
    parser.add_argument("--radius", type=str, default="5,10,20", help="Drive time radii in minutes")
    args = parser.parse_args()
    
    radii = [int(r) for r in args.radius.split(",")]
    print(f"Drive-time radii: {radii} min")
    print(f"OSRM server: {OSRM_HOST}:{OSRM_PORT}")
    
    # Test connection
    try:
        test_url = f"http://{OSRM_HOST}:{OSRM_PORT}/route/v1/driving/-71.4,41.8;-71.5,41.9?overview=false"
        r = urllib.request.urlopen(test_url, timeout=5)
        print(f"✅ OSRM server online\n")
    except Exception as e:
        print(f"❌ Cannot reach OSRM server: {e}")
        print(f"   Make sure OSRM is running on {OSRM_HOST}:{OSRM_PORT}")
        return
    
    # Load churches with lat/lng
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    limit = "" if args.all else f" LIMIT {args.batch}"
    cur.execute(f"""
        SELECT id, name, city, state, latitude, longitude 
        FROM churches 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY RANDOM()
        {limit}
    """)
    rows = cur.fetchall()
    db.close()
    print(f"Processing {len(rows):,} churches...\n")
    
    results = []
    for i, (cid, name, city, state, lat, lng) in enumerate(rows):
        print(f"  [{i+1}/{len(rows)}] {name[:40]:40s} {city or '':20s} {state or ''}", end=" ")
        dt = compute_drive_times(cid, lat, lng, radii)
        print(f"→ {dt.get(f'churches_{radii[0]}min', '?'):>3} / {dt.get(f'churches_{radii[1]}min', '?'):>3} / {dt.get(f'churches_{radii[2]}min', '?'):>3} within {radii[0]}/{radii[1]}/{radii[2]}min")
        results.append(dt)
        
        if (i+1) % 5 == 0:
            # Save intermediate results
            out = os.path.join(OUT_DIR, f"drive_times_checkpoint.csv")
            with open(out, "w", newline="") as f:
                if results:
                    w = csv.DictWriter(f, fieldnames=results[0].keys())
                    w.writeheader()
                    w.writerows(results)
    
    # Final save
    out = os.path.join(OUT_DIR, "drive_times.csv")
    with open(out, "w", newline="") as f:
        if results:
            w = csv.DictWriter(f, fieldnames=results[0].keys())
            w.writeheader()
            w.writerows(results)
    print(f"\nSaved {len(results):,} drive-time results to {out}")


if __name__ == "__main__":
    main()

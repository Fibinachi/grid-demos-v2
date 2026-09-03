"""GPS-based PPP-to-church matching via Census Geocoding API.
Replaces fuzzy name matching — geocode the PPP address, find churches within ~50m.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
import requests, time, sys

db = connect()
API = "https://geocoding.geo.census.gov/geocoder/locations/address"
session = requests.Session()
session.headers.update({"User-Agent": "GRID/1.0 (research)"})

# Load unmatched PPP loans with addresses
cur = db.execute("""
    SELECT p.id, p.borrower_name, p.borrower_address, p.borrower_city,
           p.borrower_state, p.borrower_zip
    FROM sba_ppp_loans p
    WHERE p.church_id IS NULL
      AND p.borrower_address IS NOT NULL AND p.borrower_address != ''
      AND p.naics_code LIKE '813%'
""")
unmatched = cur.fetchall()
total = len(unmatched)
print(f"Unmatched PPP loans to geocode: {total:,}")

if total == 0:
    print("All matched. Done.")
    db.close(); sys.exit(0)

# Load US church GPS for proximity matching
cur = db.execute("""
    SELECT id, name, latitude, longitude, address
    FROM churches
    WHERE country='US' AND latitude IS NOT NULL
""")
churches = cur.fetchall()
print(f"Church GPS pool: {len(churches):,}")

# Build spatial hash — 0.001° = ~111m, so we bucket by ~0.01° chunks
from collections import defaultdict
hashmap = defaultdict(list)
for ch_id, ch_name, lat, lon, addr in churches:
    if lat is None or lon is None: continue
    try:
        bucket = (int(float(lat)*100), int(float(lon)*100))
        hashmap[bucket].append((ch_id, ch_name, float(lat), float(lon)))
    except (ValueError, TypeError):
        continue
print(f"Spatial hash: {len(hashmap):,} buckets")

geocoded = 0
matched = 0
failed = 0
t0 = time.time()

for i, (ppp_id, name, addr, city, state, zip5) in enumerate(unmatched):
    # Build search address
    search = f"{addr}, {city}, {state} {zip5}"
    
    # Census geocode (free, no key needed, ~1 req/sec polite)
    try:
        resp = session.get(API, params={
            "street": addr,
            "city": city,
            "state": state,
            "zip": zip5,
            "benchmark": "4",
            "format": "json"
        }, timeout=8)
        
        if resp.status_code != 200:
            failed += 1
            continue
        
        data = resp.json()
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            failed += 1
            continue
        
        coords = matches[0].get("coordinates", {})
        lat = coords.get("y")
        lon = coords.get("x")
        if not lat or not lon:
            failed += 1
            continue
        
        geocoded += 1
        
    except Exception:
        failed += 1
        continue
    
    # Find nearby churches — check 9 adjacent buckets (~1km radius)
    bucket = (int(float(lat)*100), int(float(lon)*100))
    nearby = []
    for db_lat in range(bucket[0]-1, bucket[0]+2):
        for db_lon in range(bucket[1]-1, bucket[1]+2):
            nearby.extend(hashmap.get((db_lat, db_lon), []))
    
    best_dist = 999
    best_church = None
    for ch_id, ch_name, ch_lat, ch_lon in nearby:
        dist = ((float(lat) - ch_lat)**2 + (float(lon) - ch_lon)**2)**0.5
        if dist < 0.001 and dist < best_dist:  # ~111m threshold
            best_dist = dist
            best_church = ch_id
    
    if best_church:
        db.execute(
            "UPDATE sba_ppp_loans SET church_id=?, match_method='gps_proximity', match_confidence=0.95 WHERE id=?",
            (best_church, ppp_id)
        )
        matched += 1
    
    # Throttle to ~1 req/sec
    time.sleep(1.1)
    
    if (i+1) % 50 == 0 or i == total-1:
        db.commit()
        elapsed = time.time()-t0
        pct = (i+1)/total*100
        rate = (i+1)/elapsed if elapsed>0 else 0
        eta = (total-i-1)/rate/60 if rate>0 else 0
        bar = chr(0x2588)*int(30*(i+1)/total) + chr(0x2591)*(30-int(30*(i+1)/total))
        sys.stdout.write(f"\r{bar} {i+1:>5}/{total} ({pct:>4.0f}%) geocoded={geocoded:<5} matched={matched:<5} {rate:>3.0f}/m ETA={eta:>4.0f}m")
        sys.stdout.flush()

db.commit()
elapsed = time.time()-t0
print(f"\n\nDone in {elapsed:.0f}s — geocoded={geocoded:,} matched={matched:,} failed={failed:,}")

cur = db.execute("SELECT match_method, COUNT(*), COUNT(DISTINCT church_id) FROM sba_ppp_loans WHERE church_id IS NOT NULL GROUP BY match_method")
print("\nMatch breakdown:")
for r in cur.fetchall():
    print(f"  {r[0] or 'NULL':30s} {r[1]:6,} loans  {r[2]:,} churches")
db.close()

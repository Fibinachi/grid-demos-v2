"""Geocode TN religious parcels via Census single-address API (threaded), then match to churches."""
import sqlite3, json, requests, time, os, sys, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

STAGING_DB = Path("E:/grid/data/tn_parcels/tn_religious_parcels.db")
CHURCHES_DB = Path("E:/grid/churches.db")
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
WORKERS = 8

def norm_name(n):
    if not n: return ""
    n = n.upper().strip()
    for w in ["CHURCH", "CHAPEL", "TEMPLE", "CATHEDRAL", "PARISH", 
              "MINISTRY", "FELLOWSHIP", "CEMETERY", "OF", "THE"]:
        n = re.sub(rf'\b{w}\b', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n

# ── Step 1: Collect ──
print("=" * 60)
print("STEP 1: Collect addresses")
print("=" * 60)

staging = sqlite3.connect(str(STAGING_DB))
staging.row_factory = sqlite3.Row

rows = staging.execute("""
    SELECT id, address, city, state, zip, name
    FROM tn_religious_parcels
    WHERE tn_filter IN ('church', 'parsonage', 'religious_cemetery')
    AND latitude IS NULL
""").fetchall()

print(f"  {len(rows):,} to geocode")

# ── Step 2: Geocode ──
print(f"\n{'=' * 60}")
print(f"STEP 2: Census geocoding ({WORKERS} threads)")
print(f"{'=' * 60}")

def geocode_one(r):
    addr = (r["address"] or "").strip()
    city = (r["city"] or "").strip()
    state = r["state"] or "TN"
    zipcode = (r["zip"] or "").strip()[:5]
    
    if not addr:
        return (r["id"], None, None)
    
    full = f"{addr}, {city}, {state} {zipcode}".strip()
    
    try:
        resp = requests.get(CENSUS_URL, params={
            "address": full,
            "benchmark": "Public_AR_Current",
            "format": "json"
        }, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            matches = data.get("result", {}).get("addressMatches", [])
            if matches:
                coords = matches[0].get("coordinates", {})
                lat = coords.get("y")
                lon = coords.get("x")
                if lat and lon:
                    return (r["id"], lat, lon)
    except:
        pass
    
    return (r["id"], None, None)

results = {}
done = 0
t0 = time.time()

with ThreadPoolExecutor(max_workers=WORKERS) as executor:
    futures = {executor.submit(geocode_one, r): r for r in rows}
    for f in as_completed(futures):
        pid, lat, lon = f.result()
        if lat and lon:
            results[pid] = (lat, lon)
        done += 1
        if done % 500 == 0 or done == len(rows):
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (len(rows) - done) / rate if rate > 0 else 0
            print(f"\r  {done:,}/{len(rows):,} ({done/len(rows)*100:.0f}%) — {len(results):,} geocoded — {rate:.0f}/s — {remaining:.0f}s left", end="", flush=True)

geo_count = len(results)
print(f"\n  Geocoded: {geo_count:,} / {len(rows):,} ({geo_count/len(rows)*100:.1f}%) in {time.time()-t0:.0f}s")

# ── Step 3: Update DB ──
print("Updating staging DB...")
for pid, (lat, lon) in results.items():
    staging.execute(
        "UPDATE tn_religious_parcels SET latitude=?, longitude=?, geocode_source='census_address' WHERE id=?",
        (lat, lon, pid)
    )
staging.commit()
print(f"  Updated {len(results):,} rows")

# ── Step 4: Match ──
print(f"\n{'=' * 60}")
print("STEP 4: Match to churches.db")
print(f"{'=' * 60}")

parcels = staging.execute("""
    SELECT id, name, address, city, state, zip, latitude, longitude, 
           tn_county, landmark_type
    FROM tn_religious_parcels
    WHERE latitude IS NOT NULL
    AND tn_filter IN ('church', 'parsonage', 'religious_cemetery')
""").fetchall()

print(f"  {len(parcels):,} geocoded parcels")

churches = sqlite3.connect(str(CHURCHES_DB))
churches.row_factory = sqlite3.Row

tn_churches = churches.execute("""
    SELECT rowid, id, name, address, city, state, zip,
           latitude, longitude, faith, tradition, landmark_type
    FROM churches 
    WHERE country='US' AND state='TN'
    AND latitude IS NOT NULL AND longitude IS NOT NULL
""").fetchall()

print(f"  {len(tn_churches):,} TN churches in database")

# Address index
addr_index = defaultdict(list)
for c in tn_churches:
    c_addr = (c["address"] or "").strip().upper()[:40]
    c_city = (c["city"] or "").strip().upper()
    key = f"{c_addr}|{c_city}"
    if key.strip() != "|":
        addr_index[key].append(c)

matched = 0
for p in parcels:
    p_lat = p["latitude"]
    p_lon = p["longitude"]
    p_name = p["name"] or ""
    pn = norm_name(p_name)
    
    best_match = None
    best_score = 0
    
    # 1. Same address
    p_addr = (p["address"] or "").strip().upper()[:40]
    p_city = (p["city"] or "").strip().upper()
    addr_key = f"{p_addr}|{p_city}"
    
    if addr_key in addr_index:
        for c in addr_index[addr_key]:
            score = 50
            cn = norm_name(c["name"] or "")
            if pn and cn and pn == cn:
                score = 100
            elif pn and cn:
                pw = set(pn.split())
                cw = set(cn.split())
                overlap = len(pw & cw)
                if overlap > 0:
                    score = 80 + overlap * 5
            if score > best_score:
                best_match = c
                best_score = score
    
    # 2. Proximity (500m)
    if best_score < 80 and p_lat and p_lon:
        for c in tn_churches:
            if not c["latitude"] or not c["longitude"]:
                continue
            if abs(c["latitude"] - p_lat) > 0.005 or abs(c["longitude"] - p_lon) > 0.006:
                continue
            
            score = 30
            cn = norm_name(c["name"] or "")
            if pn and cn:
                if pn == cn:
                    score = 90
                else:
                    pw = set(pn.split())
                    cw = set(cn.split())
                    overlap = len(pw & cw)
                    if overlap >= 2:
                        score = 70 + overlap * 10
                    elif overlap == 1:
                        score = 60
            if score > best_score:
                best_match = c
                best_score = score
    
    match_id = best_match["rowid"] if best_match and best_score >= 70 else None
    staging.execute(
        "UPDATE tn_religious_parcels SET grid_church_id=? WHERE id=?",
        (match_id, p["id"])
    )
    if match_id:
        matched += 1

staging.commit()
print(f"  Matched to GRID: {matched:,} / {len(parcels):,} ({matched/len(parcels)*100:.1f}%)")

# ── Summary ──
print(f"\n{'=' * 60}")
print("SUMMARY")
print(f"{'=' * 60}")

total = staging.execute(
    "SELECT COUNT(*) FROM tn_religious_parcels WHERE tn_filter IN ('church','parsonage','religious_cemetery')"
).fetchone()[0]
geo = staging.execute("SELECT COUNT(*) FROM tn_religious_parcels WHERE latitude IS NOT NULL").fetchone()[0]
mtch = staging.execute("SELECT COUNT(*) FROM tn_religious_parcels WHERE grid_church_id IS NOT NULL").fetchone()[0]

print(f"  Eligible:  {total:,}")
print(f"  Geocoded:  {geo:,} ({geo/total*100:.1f}%)")
print(f"  Matched:   {mtch:,} ({mtch/total*100:.1f}%)")

print(f"\n  Top counties:")
for r in staging.execute("""
    SELECT tn_county, COUNT(*) as t,
           SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as m
    FROM tn_religious_parcels
    WHERE tn_filter IN ('church','parsonage','religious_cemetery')
    GROUP BY tn_county ORDER BY t DESC LIMIT 10
"""):
    pct = r["m"]/r["t"]*100 if r["t"] else 0
    print(f"    {r['tn_county']:20s} {r['t']:>6,}  matched {r['m']:>6,} ({pct:.0f}%)")

staging.close()
churches.close()
print("\n✅ Done")

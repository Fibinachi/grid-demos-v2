"""Geocode churchunion_scraper — simple sequential with progress every 100."""
import sqlite3, time, urllib.request, json, urllib.parse

DB = "E:/grid/churches.db"
URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

t0 = time.time()
db = sqlite3.connect(DB, timeout=60)
rows = db.execute("SELECT id, address, city, state, zip FROM churches WHERE source='churchunion_scraper' AND (latitude IS NULL OR latitude=0) ORDER BY id").fetchall()
total = len(rows)
print(f"To geocode: {total:,}", flush=True)
print("Starting loop...", flush=True)

ok = 0
for i, (cid, addr, city, state, zip_code) in enumerate(rows):
    if i == 0:
        print(f"  First row: {addr[:60]}...", flush=True)
    full = f"{addr}, {city}, {state} {zip_code or ''}".strip(", ")
    p = urllib.parse.urlencode({"address": full, "benchmark": "Public_AR_Current", "format": "json"})
    try:
        req = urllib.request.Request(URL + "?" + p, headers={"User-Agent": "GW/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.loads(resp.read().decode())
            m = d.get("result", {}).get("addressMatches", [])
            if m:
                c = m[0]["coordinates"]
                g = m[0].get("geographies", {}).get("Census Blocks", [{}])[0]
                lat, lng = float(c["y"]), float(c["x"])
                cfips = f"{g.get('STATE','')}{g.get('COUNTY','')}"
                tfips = f"{g.get('STATE','')}{g.get('COUNTY','')}{g.get('TRACT','')}"
                db.execute("UPDATE churches SET latitude=?, longitude=?, geocode_source='census_street', county_fips=?, tract_fips=? WHERE id=?",
                          (lat, lng, cfips, tfips, cid))
                ok += 1
    except Exception:
        pass

    if i == 0:
        print(f"  First done, ok={ok}", flush=True)

    if (i + 1) % 100 == 0:
        db.commit()
        elapsed = time.time() - t0
        rate = (i + 1) / elapsed
        eta = (total - i - 1) / rate / 60
        pct = (i + 1) / total * 100
        print(f"  {i+1:,}/{total:,} ({pct:.1f}%) {ok:,} ok {rate:.1f}/s ETA {eta:.0f}m", flush=True)

db.commit()
elapsed = time.time() - t0
print(f"\nDone: {ok:,}/{total:,} in {elapsed/60:.1f}m ({ok/total*100:.0f}%)", flush=True)
db.close()

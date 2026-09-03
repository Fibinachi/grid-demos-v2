"""Japan-only OSM scrape — full progress display. Same 0.5° tile, 2-worker engine."""
import sqlite3, json, urllib.request, urllib.parse, time, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from shapely import wkb

VK = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
DB = 'E:/grid/churches.db'
GEO = 'E:/grid/data/natural_earth/world_borders.db'
TILE = 0.5

FAITH = {"christian":"Christian","muslim":"Islam","buddhist":"Buddhist",
    "hindu":"Hindu","jewish":"Jewish","sikh":"Sikh","taoist":"Taoist"}
DENOM = {"catholic":"Roman Catholic","orthodox":"Eastern Orthodox",
    "protestant":"Protestant","baptist":"Baptist","lutheran":"Lutheran",
    "methodist":"Methodist","presbyterian":"Presbyterian","anglican":"Anglican",
    "evangelical":"Evangelical","pentecostal":"Pentecostal",
    "sunni":"Sunni Islam","shia":"Shia Islam",
    "russian_orthodox":"Russian Orthodox","greek_orthodox":"Greek Orthodox"}

def regions_for(code):
    gconn = sqlite3.connect(GEO); gc = gconn.cursor()
    gc.execute("SELECT name, geometry_wkb FROM world_borders WHERE iso_a2=?", (code,))
    name, blob = gc.fetchone()
    poly = wkb.loads(blob)
    mx, my, Mx, My = poly.bounds
    subs = [(my, mx, My, Mx)]
    if My - my > 20 or Mx - mx > 40:
        subs = []
        lat = my
        while lat < My:
            lon = mx
            while lon < Mx:
                subs.append((lat, lon, min(lat + 15, My), min(lon + 30, Mx)))
                lon += 30
            lat += 15
    tiles = []
    for s, w, n, e in subs:
        tlat = s
        while tlat < n:
            tlon = w
            while tlon < e:
                tiles.append((tlat, tlon, min(tlat + TILE, n), min(tlon + TILE, e)))
                tlon += TILE
            tlat += TILE
    gconn.close()
    return name, tiles

def query(bbox):
    s, w, n, e = bbox
    q = f"""[out:json][timeout:30][maxsize:1073741824][bbox:{s},{w},{n},{e}];
(node["amenity"="place_of_worship"];way["amenity"="place_of_worship"];);
out center;"""
    d = urllib.parse.urlencode({"data": q}).encode()
    try:
        r = urllib.request.Request(VK, data=d, headers={"User-Agent":"GRID/1.0"})
        with urllib.request.urlopen(r, timeout=60) as resp:
            return bbox, json.loads(resp.read())
    except:
        return bbox, None

def classify(el):
    t = el.get("tags", {})
    nm = t.get("name", "") or t.get("name:en", "") or t.get("name:ru", "")
    if not nm: return None
    if el["type"] == "node":
        lat, lon = el["lat"], el["lon"]
    else:
        c = el.get("center", {})
        lat, lon = c.get("lat"), c.get("lon")
    if lat is None: return None
    rel = t.get("religion", "").lower()
    den = t.get("denomination", "").lower()
    f = FAITH.get(rel) or FAITH.get(den)
    dm = DENOM.get(den) or DENOM.get(rel)
    b = t.get("building", "")
    lm = b if b in ("cathedral", "church", "chapel", "temple", "mosque", "synagogue") else \
        ("church" if rel == "christian" else "temple" if rel in ("buddhist", "taoist", "hindu") else \
         "mosque" if rel == "muslim" else "synagogue" if rel == "jewish" else "shrine")
    return (nm, lat, lon, f, dm, lm, str(el["id"]), el["type"],
            t.get("addr:street", ""), t.get("addr:city", ""))

# Main
name, tiles = regions_for("JP")
total_tiles = len(tiles)
print(f"Japan ({name}): {total_tiles} tiles, 2 workers")
print()

conn = sqlite3.connect(DB)
conn.execute("PRAGMA busy_timeout=30000")
c = conn.cursor()
ts = datetime.now(timezone.utc).isoformat()

c.execute("SELECT osm_id FROM churches WHERE osm_id IS NOT NULL AND osm_id != ''")
existing = {r[0] for r in c.fetchall()}
print(f"Existing OSM IDs: {len(existing):,}")

c.execute("SELECT COUNT(1) FROM churches WHERE country='JP'")
before = c.fetchone()[0]
print(f"Japan churches before: {before:,}")

new_total = 0
dt = 0
t0 = time.time()
tiles_with_data = 0
tiles_empty = 0
tiles_error = 0

with ThreadPoolExecutor(max_workers=2) as pool:
    futures = {pool.submit(query, bbox): bbox for bbox in tiles}
    for future in as_completed(futures):
        dt += 1
        bbox, result = future.result()
        s, w, n, e = bbox
        
        if result:
            els = result.get("elements", [])
            if els:
                batch = []
                for el in els:
                    rec = classify(el)
                    if rec and rec[6] not in existing:
                        existing.add(rec[6])
                        batch.append(rec)
                if batch:
                    c.executemany("""INSERT INTO churches(name,latitude,longitude,faith,denomination,landmark_type,osm_id,osm_type,address,city,country,source,source_primary)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        [(n, la, lo, f, d, lm, oid, ot, ad, ci, "JP", "osm_import", "openstreetmap")
                         for n, la, lo, f, d, lm, oid, ot, ad, ci in batch])
                    conn.commit()
                    n_added = len(batch)
                    new_total += n_added
                    tiles_with_data += 1
                    print(f"  tile {dt:4d}/{total_tiles} [{s:.1f},{w:.1f} {n:.1f},{e:.1f}] +{n_added:>5d}  (total +{new_total:,})")
                else:
                    tiles_empty += 1
                    print(f"  tile {dt:4d}/{total_tiles} [{s:.1f},{w:.1f} {n:.1f},{e:.1f}] dup     (total +{new_total:,})")
            else:
                tiles_empty += 1
                print(f"  tile {dt:4d}/{total_tiles} [{s:.1f},{w:.1f} {n:.1f},{e:.1f}] empty   (total +{new_total:,})")
        else:
            tiles_error += 1
            print(f"  tile {dt:4d}/{total_tiles} [{s:.1f},{w:.1f} {n:.1f},{e:.1f}] ERROR   (total +{new_total:,})")
        
        if dt % 40 == 0:
            el = (time.time() - t0) / 60
            print(f"  --- {dt}/{total_tiles} tiles ({dt*100//total_tiles}%), {el:.1f}m, +{new_total:,} new ---")

c.execute("SELECT COUNT(1) FROM churches WHERE country='JP'")
after = c.fetchone()[0]
el = (time.time() - t0) / 60
print(f"\n=== DONE ===")
print(f"  Tiles: {total_tiles} ({tiles_with_data} data, {tiles_empty} empty, {tiles_error} errors)")
print(f"  New: +{new_total:,} ({before:,} -> {after:,})")
print(f"  Time: {el:.1f}m")

c.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_inserted,fields_populated,status,notes)
    VALUES(?,?,?,?,?,?,?,?)""",
    ("osm_import", "import_jp_retry.py", ts, datetime.now(timezone.utc).isoformat(),
     new_total, "name,latitude,longitude,faith,denomination,landmark_type,country", "completed",
     f"Japan re-scrape 0.5deg: +{new_total} new in {el:.0f}m, {total_tiles} tiles"))
conn.commit()
conn.close()

# Restore JP to checkpoint
with open('E:/grid/_osm_checkpoint.txt', 'a') as f:
    f.write('JP\n')
print("JP restored to checkpoint.")

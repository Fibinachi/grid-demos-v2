"""Japan Shinto shrine scrape — targets religion=shinto, shinto=*, building=shrine."""
import sqlite3, json, urllib.request, urllib.parse, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from shapely import wkb
from shapely.geometry import box

VK = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
DB = 'E:/grid/churches.db'
GEO = 'E:/grid/data/natural_earth/world_borders.db'
TILE = 0.5

def get_tiles():
    gconn = sqlite3.connect(GEO); gc = gconn.cursor()
    gc.execute("SELECT geometry_wkb FROM world_borders WHERE iso_a2=?", ('JP',))
    poly = wkb.loads(gc.fetchone()[0])
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
                tile_box = box(tlon, tlat, min(tlon + TILE, e), min(tlat + TILE, n))
                if poly.intersects(tile_box):
                    tiles.append((tlat, tlon, min(tlat + TILE, n), min(tlon + TILE, e)))
                tlon += TILE
            tlat += TILE
    gconn.close()
    return tiles

def query(bbox):
    s, w, n, e = bbox
    q = f"""[out:json][timeout:30][maxsize:1073741824][bbox:{s},{w},{n},{e}];
(
  node["amenity"="place_of_worship"]["religion"="shinto"];
  way["amenity"="place_of_worship"]["religion"="shinto"];
  node["shinto"];
  way["shinto"];
  node["building"="shrine"];
  way["building"="shrine"];
);
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
    nm = t.get("name", "") or t.get("name:en", "") or t.get("name:ja", "")
    if not nm: return None
    if el["type"] == "node":
        lat, lon = el["lat"], el["lon"]
    else:
        c = el.get("center", {})
        lat, lon = c.get("lat"), c.get("lon")
    if lat is None: return None
    shinto_tag = t.get("shinto", "").lower()
    building = t.get("building", "").lower()
    lm = "shrine" if (shinto_tag == "shrine" or building == "shrine") else \
         f"shinto_{shinto_tag}" if shinto_tag else "shrine"
    return (nm, lat, lon, "Shinto", None, lm, str(el["id"]), el["type"],
            t.get("addr:street", ""), t.get("addr:city", ""))

tiles = get_tiles()
total_tiles = len(tiles)

conn = sqlite3.connect(DB)
conn.execute("PRAGMA busy_timeout=30000")
c = conn.cursor()
c.execute("SELECT osm_id FROM churches WHERE osm_id IS NOT NULL AND osm_id != ''")
existing = {r[0] for r in c.fetchall()}
c.execute("SELECT COUNT(1) FROM churches WHERE country='JP' AND faith='Shinto'")
before_s = c.fetchone()[0]
c.execute("SELECT COUNT(1) FROM churches WHERE country='JP'")
before_t = c.fetchone()[0]
print(f"JP Shinto before: {before_s:,} / {before_t:,} total")
print(f"Land tiles: {total_tiles} | Existing IDs: {len(existing):,}\n")

new_total = dt = tiles_data = tiles_empty = 0
t0 = time.time()

with ThreadPoolExecutor(max_workers=2) as pool:
    futures = {pool.submit(query, bbox): bbox for bbox in tiles}
    for future in as_completed(futures):
        dt += 1
        bbox, result = future.result()
        s, w, n, e = bbox
        if result and result.get("elements"):
            batch = []
            for el in result["elements"]:
                rec = classify(el)
                if rec and rec[6] not in existing:
                    existing.add(rec[6]); batch.append(rec)
            if batch:
                c.executemany("""INSERT INTO churches(name,latitude,longitude,faith,denomination,landmark_type,osm_id,osm_type,address,city,country,source,source_primary)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [(n, la, lo, f, d, lm, oid, ot, ad, ci, "JP", "osm_import", "openstreetmap")
                     for n, la, lo, f, d, lm, oid, ot, ad, ci in batch])
                conn.commit()
                new_total += len(batch); tiles_data += 1
                print(f"  {dt:4d}/{total_tiles} [{s:.1f},{w:.1f}] +{len(batch):>5d}  ({new_total:,} Shinto)")
            else:
                tiles_empty += 1
        if dt % 50 == 0:
            print(f"  --- {dt}/{total_tiles} ({dt*100//total_tiles}%) {((time.time()-t0)/60):.1f}m +{new_total:,} ---")

conn.commit()
c.execute("SELECT COUNT(1) FROM churches WHERE country='JP' AND faith='Shinto'")
after_s = c.fetchone()[0]
c.execute("SELECT COUNT(1) FROM churches WHERE country='JP'")
after_t = c.fetchone()[0]
el = (time.time() - t0) / 60
print(f"\n=== DONE ===")
print(f"  Shinto: +{new_total:,} ({before_s:,} -> {after_s:,})")
print(f"  Total JP: {before_t:,} -> {after_t:,}")
print(f"  Time: {el:.1f}m | Tiles: {tiles_data} hit / {tiles_empty} dup")

ts = datetime.now(timezone.utc).isoformat()
c.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_inserted,fields_populated,status,notes)
    VALUES(?,?,?,?,?,?,?,?)""",
    ("osm_import", "import_jp_shinto.py", ts, datetime.now(timezone.utc).isoformat(),
     new_total, "name,latitude,longitude,faith,landmark_type,country", "completed",
     f"Japan Shinto re-scan: +{new_total} new"))
conn.close()

with open('E:/grid/_osm_checkpoint.txt', 'a') as f:
    f.write('JP\n')
print("JP restored to checkpoint.")

"""Combined JP scraper: 1 Wikidata + 2 VK workers per 0.5° tile.
Queries Wikidata SPARQL (shrines+temples, heritage data) and
VK Maps Overpass (OSM religious sites) for each tile.
Checkpoint-aware, 3 concurrent workers."""
import sqlite3, json, time, os, requests, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from collections import defaultdict
from shapely import wkb

DB = "E:/grid/churches.db"
GEO = "E:/grid/data/natural_earth/world_borders.db"
CHECKPOINT = "E:/grid/_jp_combined_checkpoint.txt"
WD_SPARQL = "https://query.wikidata.org/sparql"
VK = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
HEADERS = {"User-Agent": "GRID/1.0"}
TILE = 0.5

FAITH_COLORS = {
    "Christian": "\033[33m", "Islam": "\033[32m", "Buddhist": "\033[35m",
    "Hindu": "\033[31m", "Jewish": "\033[36m", "Sikh": "\033[34m",
    "Shinto": "\033[91m", "Taoist": "\033[95m", "Bahai": "\033[94m",
    "Pagan": "\033[92m", "Zoroastrian": "\033[93m", "Animist": "\033[97m",
}
C_RESET = "\033[0m"
C_DOT = "\033[90m.\033[0m"
C_ERR = "\033[31mx\033[0m"
C_GOLD = "\033[93m"  # Heritage highlight

# ---- Checkpoint ----
def load_checkpoint():
    if not os.path.exists(CHECKPOINT): return set()
    with open(CHECKPOINT) as f:
        return {line.strip() for line in f if line.strip()}

def save_checkpoint(key):
    with open(CHECKPOINT, 'a') as f:
        f.write(key + '\n')

def dedup_checkpoint():
    if not os.path.exists(CHECKPOINT): return
    with open(CHECKPOINT) as f:
        codes = list(dict.fromkeys(l.strip() for l in f if l.strip()))
    with open(CHECKPOINT, 'w') as f:
        f.write('\n'.join(codes) + '\n')

# ---- Tile Generation ----
def japan_tiles():
    gconn = sqlite3.connect(GEO); gc = gconn.cursor()
    gc.execute("SELECT geometry_wkb FROM world_borders WHERE iso_a2='JP'")
    poly = wkb.loads(gc.fetchone()[0])
    mx, my, Mx, My = poly.bounds; gconn.close()
    
    tiles = []
    lat = my
    while lat < My:
        lon = mx
        while lon < Mx:
            from shapely.geometry import box
            if poly.intersects(box(lon, lat, lon+TILE, lat+TILE)):
                tiles.append((lon, lat, lon+TILE, lat+TILE))
            lon += TILE
        lat += TILE
    tiles.sort(key=lambda t: (t[1], t[0]))
    return tiles

# ---- Wikidata Query (per tile) ----
def query_wikidata(bbox):
    """Query Wikidata for Shinto shrines + Buddhist temples in bbox."""
    w, s, e, n = bbox
    q = f"""
    SELECT ?item ?itemLabel ?coords ?instanceLabel ?heritageLabel ?inception ?dedicatedLabel ?address
    WHERE {{
      {{ ?item wdt:P31 wd:Q845945. }} UNION {{ ?item wdt:P31 wd:Q5393308. }}
      ?item wdt:P17 wd:Q17.
      SERVICE wikibase:box {{
        ?item wdt:P625 ?coords.
        bd:serviceParam wikibase:cornerSouthWest "Point({w} {s})"^^geo:wktLiteral.
        bd:serviceParam wikibase:cornerNorthEast "Point({e} {n})"^^geo:wktLiteral.
      }}
      OPTIONAL {{ ?item wdt:P1435 ?heritage. }}
      OPTIONAL {{ ?item wdt:P571 ?inception. }}
      OPTIONAL {{ ?item wdt:P825 ?dedicated. }}
      OPTIONAL {{ ?item wdt:P6375 ?address. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,ja". }}
    }}
    """
    try:
        r = requests.get(WD_SPARQL, params={"query": q, "format": "json"},
                        headers=HEADERS, timeout=60)
        r.raise_for_status()
    except Exception as e:
        return None, str(e)
    
    bindings = r.json().get("results", {}).get("bindings", [])
    results = []
    for b in bindings:
        coords = b.get("coords", {}).get("value", "")
        lat, lon = None, None
        if coords:
            try:
                s = coords.replace("Point(","").replace(")","")
                lo, la = s.split()
                lat, lon = float(la), float(lo)
            except: pass
        
        uri = b.get("item", {}).get("value", "")
        instance = b.get("instanceLabel", {}).get("value", "")
        faith = "Shinto" if "shinto" in instance.lower() or "shrine" in instance.lower() else "Buddhist"
        lm = "shrine" if faith == "Shinto" else "temple"
        
        inception = b.get("inception", {}).get("value", "")
        yr = None
        if inception:
            try: yr = int(inception[:4])
            except: pass
        
        results.append({
            "name": b.get("itemLabel", {}).get("value", ""),
            "lat": lat, "lon": lon,
            "faith": faith, "landmark_type": lm,
            "qid": uri.split("/")[-1] if uri else "",
            "heritage": b.get("heritageLabel", {}).get("value", ""),
            "year": yr,
            "dedication": b.get("dedicatedLabel", {}).get("value", ""),
            "address": b.get("address", {}).get("value", ""),
            "source": "wikidata",
        })
    return results, None

def parse_coords(s):
    if not s: return None, None
    try:
        s = s.replace("Point(","").replace(")","")
        lon, lat = s.split()
        return float(lat), float(lon)
    except: return None, None

# ---- VK Overpass Query (per tile) ----
VMAP = """[out:json][timeout:45];
(
  node[amenity=place_of_worship];
  way[amenity=place_of_worship];
  node[building=church]; way[building=church];
  node[building=cathedral]; way[building=cathedral];
  node[building=chapel]; way[building=chapel];
  node[building=temple]; way[building=temple];
  node[building=mosque]; way[building=mosque];
  node[building=synagogue]; way[building=synagogue];
  node[building=shrine]; way[building=shrine];
  node[building=wayside_shrine]; way[building=wayside_shrine];
  node[historic=wayside_shrine]; way[historic=wayside_shrine];
  node[building=pagoda]; way[building=pagoda];
  node[building=stupa]; way[building=stupa];
  node[building=gurdwara]; way[building=gurdwara];
  node[building=kingdom_hall]; way[building=kingdom_hall];
  node[building=madrassa]; way[building=madrassa];
  node[amenity=madrassa]; way[amenity=madrassa];
  node[building=basilica]; way[building=basilica];
  node[building=oratory]; way[building=oratory];
  node[building=baptistery]; way[building=baptistery];
  node[building=monastery]; way[building=monastery];
  node[building=convent]; way[building=convent];
  node[building=nunnery]; way[building=nunnery];
  node[building=fire_temple]; way[building=fire_temple];
  node[building=mandir]; way[building=mandir];
  node[building=abbey]; way[building=abbey];
  node[amenity=school][religion~"christian|muslim|jewish|hindu|buddhist"];
  way[amenity=school][religion~"christian|muslim|jewish|hindu|buddhist"];
);
out center 100;"""

def query_vk(bbox):
    """Query VK Maps Overpass for religious sites in bbox."""
    w, s, e, n = bbox
    q = f"""[out:json][timeout:45][bbox:{s},{w},{n},{e}];
(
  node[amenity=place_of_worship];
  way[amenity=place_of_worship];
  node[building=church]; way[building=church];
  node[building=cathedral]; way[building=cathedral];
  node[building=chapel]; way[building=chapel];
  node[building=temple]; way[building=temple];
  node[building=mosque]; way[building=mosque];
  node[building=synagogue]; way[building=synagogue];
  node[building=shrine]; way[building=shrine];
  node[building=wayside_shrine]; way[building=wayside_shrine];
  node[historic=wayside_shrine]; way[historic=wayside_shrine];
  node[building=pagoda]; way[building=pagoda];
  node[building=stupa]; way[building=stupa];
  node[building=gurdwara]; way[building=gurdwara];
  node[building=kingdom_hall]; way[building=kingdom_hall];
  node[building=madrassa]; way[building=madrassa];
  node[amenity=madrassa]; way[amenity=madrassa];
  node[building=basilica]; way[building=basilica];
  node[building=oratory]; way[building=oratory];
  node[building=baptistery]; way[building=baptistery];
  node[building=monastery]; way[building=monastery];
  node[building=convent]; way[building=convent];
  node[building=nunnery]; way[building=nunnery];
  node[building=fire_temple]; way[building=fire_temple];
  node[building=mandir]; way[building=mandir];
  node[building=abbey]; way[building=abbey];
  node[amenity=school][religion~"christian|muslim|jewish|hindu|buddhist"];
  way[amenity=school][religion~"christian|muslim|jewish|hindu|buddhist"];
);
out center 100;"""
    try:
        data = urllib.parse.urlencode({"data": q}).encode()
        req = urllib.request.Request(VK, data=data)
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        return None, str(e)
    
    els = result.get("elements", [])
    results = []
    for el in els:
        rec = classify_osm(el)
        if rec:
            results.append(rec)
    return results, None

# ---- Process One Tile (combined) ----
def process_tile(bbox):
    """Query both Wikidata and VK for one tile, merge results."""
    results = []
    
    # 1. Wikidata
    wd_results, wd_err = query_wikidata(bbox)
    if wd_results:
        results.extend(wd_results)
    
    # 2. VK Overpass
    vk_results, vk_err = query_vk(bbox)
    if vk_results:
        results.extend(vk_results)
    
    return results, wd_err, vk_err

# ---- DB Operations ----
def load_jp_index():
    """Load JP churches into memory for fast matching."""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, name, latitude, longitude, osm_id, wikidata_qid FROM churches WHERE country='JP'")
    rows = c.fetchall()
    conn.close()
    
    by_qid = {}
    by_osm = {}
    by_name = defaultdict(list)
    by_prox = []
    
    for db_id, name, lat, lon, osm_id, qid in rows:
        if qid: by_qid[qid] = db_id
        if osm_id: by_osm[osm_id] = db_id
        if name: by_name[name].append((db_id, lat, lon))
        if lat and lon: by_prox.append((lat, lon, db_id))
    
    return by_qid, by_osm, by_name, by_prox

def apply_results(conn, results, index):
    """Match and insert/update results against DB."""
    by_qid, by_osm, by_name, by_prox = index
    c = conn.cursor()
    new_count = 0
    update_count = 0
    
    for rec in results:
        name = rec.get("name","")
        lat = rec.get("lat")
        lon = rec.get("lon")
        qid = rec.get("qid","")
        osm_id = rec.get("osm_id","")
        if not name or lat is None:
            continue
        
        # Try to match
        db_id = None
        
        # 1. OSM ID match
        if osm_id and osm_id in by_osm:
            db_id = by_osm[osm_id]
        # 2. QID match
        elif qid and qid in by_qid:
            db_id = by_qid[qid]
        # 3. Exact name
        elif name in by_name:
            candidates = by_name[name]
            if candidates:
                db_id = candidates[0][0]
        # 4. Proximity
        elif lat and lon:
            for plat, plon, pid in by_prox:
                if abs(lat-plat) < 0.003 and abs(lon-plon) < 0.003:
                    db_id = pid
                    break
        
        if db_id:
            # Update
            sets = []
            vals = []
            if qid:
                sets.append("wikidata_qid=?"); vals.append(qid)
            if rec.get("heritage"):
                sets.append("heritage_status=?"); vals.append(rec["heritage"])
                sets.append("heritage_source=?"); vals.append("wikidata_bunka")
            if rec.get("year"):
                sets.append("building_year=?"); vals.append(rec["year"])
            if rec.get("dedication"):
                sets.append("dedication=?"); vals.append(rec["dedication"])
            if osm_id:
                sets.append("osm_id=?"); vals.append(osm_id)
                sets.append("osm_type=?"); vals.append(rec.get("osm_type",""))
            if sets:
                vals.append(db_id)
                c.execute(f"UPDATE churches SET {', '.join(sets)} WHERE id=?", vals)
                update_count += 1
        else:
            # Insert
            c.execute("""INSERT INTO churches(name,latitude,longitude,faith,
                         landmark_type,country,source,wikidata_qid,
                         heritage_status,heritage_source,building_year,
                         dedication,osm_id,osm_type,address,city)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (name, lat, lon,
                       rec.get("faith"), rec.get("landmark_type"),
                       "JP", rec.get("source","combined"),
                       qid or None,
                       rec.get("heritage") or None,
                       "wikidata_bunka" if rec.get("heritage") else None,
                       rec.get("year"),
                       rec.get("dedication"),
                       osm_id or None,
                       rec.get("osm_type"),
                       rec.get("address"),
                       rec.get("city")))
            new_count += 1
            # Update index
            rowid = c.lastrowid
            if qid: by_qid[qid] = rowid
            if osm_id: by_osm[osm_id] = rowid
            if name: by_name[name].append((rowid, lat, lon))
            if lat and lon: by_prox.append((lat, lon, rowid))
    
    conn.commit()
    return new_count, update_count

# ---- Main ----
def main():
    # Ensure columns
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA busy_timeout=30000")
    c = conn.cursor()
    for col, ct in [("wikidata_qid","TEXT"),("heritage_source","TEXT"),("dedication","TEXT")]:
        c.execute("PRAGMA table_info(churches)")
        if col not in {r[1] for r in c.fetchall()}:
            c.execute(f"ALTER TABLE churches ADD COLUMN {col} {ct}")
            conn.commit()
    conn.close()
    
    ts = datetime.now(timezone.utc).isoformat()
    tiles = japan_tiles()
    done = load_checkpoint()
    pending = [t for t in tiles if f"{t[0]:.1f},{t[1]:.1f}" not in done]
    
    print(f"Japan: {len(tiles)} tiles, {len(done)} done, {len(pending)} pending")
    print(f"Sources: 1 Wikidata SPARQL + 2 VK Overpass per tile")
    
    if not pending:
        print("All done!"); return
    
    # Load index
    print("Loading JP index...")
    by_qid, by_osm, by_name, by_prox = load_jp_index()
    jp_before = len(by_prox)
    print(f"  {jp_before:,} JP churches indexed")
    
    # Process with 3 workers
    grand_new = 0; grand_upd = 0; t0 = time.time()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA busy_timeout=30000")
    
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(process_tile, b): b for b in pending}
        
        for i, future in enumerate(as_completed(futures)):
            bbox = futures[future]
            try:
                results, wd_err, vk_err = future.result()
                if results:
                    n, u = apply_results(conn, results, 
                                        (by_qid, by_osm, by_name, by_prox))
                    grand_new += n; grand_upd += u
                save_checkpoint(f"{bbox[0]:.1f},{bbox[1]:.1f}")
                
                # Colored per-faith output
                if results:
                    # Count per faith, track heritage
                    fcount = defaultdict(int)
                    her_count = 0
                    for r in results:
                        f = r.get("faith") or "Other"
                        fcount[f] += 1
                        if r.get("heritage"):
                            her_count += 1
                    for faith, cnt in sorted(fcount.items()):
                        clr = FAITH_COLORS.get(faith, "")
                        extra = f"{C_GOLD}h{her_count}{C_RESET}" if her_count and faith == max(fcount, key=fcount.get) else ""
                        print(f"{clr}+{cnt}{extra}{C_RESET}", end="", flush=True)
                elif wd_err or vk_err:
                    print(C_ERR, end="", flush=True)
                else:
                    print(C_DOT, end="", flush=True)
                
                if (i+1) % 40 == 0:
                    el = (time.time()-t0)/60
                print(f" [{i+1}/{len(pending)} | +{grand_new} new, {grand_upd} upd | {el:.0f}m]")
            
            except Exception as e:
                print(C_ERR, end="", flush=True)
                save_checkpoint(f"{bbox[0]:.1f},{bbox[1]:.1f}")
    
    conn.close()
    dedup_checkpoint()
    el = (time.time()-t0)/60
    
    # Summary
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(1) FROM churches WHERE country='JP'")
    jp_after = c.fetchone()[0]
    c.execute("SELECT COUNT(1) FROM churches WHERE wikidata_qid IS NOT NULL AND wikidata_qid != ''")
    wd_after = c.fetchone()[0]
    
    print(f"\n\nCombined Import: {el:.0f}m")
    print(f"  Tiles: {len(pending)}")
    print(f"  New: {grand_new:,}  Updated: {grand_upd:,}")
    print(f"  Wikidata QIDs: {wd_after:,}")
    print(f"  JP: {jp_before:,} → {jp_after:,}")
    
    c.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,
                 churches_inserted,fields_populated,status,notes)
                 VALUES(?,?,?,?,?,?,?,?)""",
              ("wikidata+osm","import_jp_combined.py",ts,
               datetime.now(timezone.utc).isoformat(),
               grand_new, "wikidata_qid,heritage_status,building_year,osm_id",
               "completed", f"1WD+2VK: {len(pending)} tiles, {grand_new} new"))
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()

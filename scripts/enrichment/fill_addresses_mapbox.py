"""
fill_addresses_mapbox.py - Mapbox forward-geocode churches lacking a street address.

Generalized version of _fix_chicago_mapbox.py: takes any boundary .geojson and
fills street-level addresses (and fixes centroid/null GPS) for churches inside
it that lack a street address component.

Writes (in --write):
  churches.latitude / churches.longitude
  church_location.geocode_source = 'mapbox' (+ church_addresses if it has the col)
  address_components.street            (via scripts.grid_address.set_components)
  enrichment_change_log + provenance_log (gw_db)
  staging DB (per-run results)

Usage:
  python scripts/enrichment/fill_addresses_mapbox.py \
      --boundary data/cook_boundary/cook_county.geojson --city "Cook County"
      # audit only (read-only, no API calls)

  python scripts/enrichment/fill_addresses_mapbox.py \
      --boundary data/cook_boundary/cook_county.geojson --city "Cook County" --write

  python scripts/enrichment/fill_addresses_mapbox.py ... --write --limit 100
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, r"E:\grid")

from shapely.geometry import Point, shape
from shapely.validation import make_valid

DB = "E:/grid/churches.db"
MAPBOX_KEY = os.environ.get("MAPBOX_API_KEY", "")
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
MAPBOX_URL = "https://api.mapbox.com/search/geocode/v6/forward"
REQ_DELAY = 0.12
SOURCE = "mapbox_address_fill_2026"


def progress_bar(current, total, start, label=""):
    pct = current / total * 100 if total else 100
    filled = int(40 * current / total) if total else 40
    bar = "#" * filled + "-" * (40 - filled)
    print(f"\r[{bar}] {pct:5.1f}%  {current}/{total}  {time.time()-start:6.1f}s  {label}",
          end="", flush=True)


def token_jaccard(a, b):
    import re
    sa = set(re.sub(r"[^a-z0-9 ]", " ", (a or "").lower()).split())
    sb = set(re.sub(r"[^a-z0-9 ]", " ", (b or "").lower()).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def load_poly(path):
    if path.lower().endswith(".geojson") or path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            gj = json.load(f)
        return make_valid(shape(gj["features"][0]["geometry"]))
    import geopandas as gpd
    gdf = gpd.read_file(path)
    if gdf.crs is not None and gdf.crs.to_epsg() not in (4326, None):
        gdf = gdf.to_crs(4326)
    return make_valid(gdf.geometry.iloc[0])


def load_unknowns(db, poly, city):
    from scripts.grid_address import get_address_components
    minx, miny, maxx, maxy = poly.bounds
    rows = db.execute(
        "SELECT id, rowid AS rid, name, latitude, longitude FROM churches "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL "
        "AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
        (miny, maxy, minx, maxx)).fetchall()
    in_boundary = {}
    for r in rows:
        if Point(r["longitude"], r["latitude"]).within(poly):
            in_boundary[r["id"]] = {"id": r["id"], "rid": r["rid"],
                                    "name": r["name"], "lat": r["latitude"],
                                    "lon": r["longitude"]}
    null_city = {}
    for r in db.execute(
        "SELECT DISTINCT a.church_id AS id, c.rowid AS rid, c.name "
        "FROM church_addresses a "
        "JOIN address_components ac ON ac.address_id = a.address_id "
        "JOIN churches c ON c.id = a.church_id "
        "WHERE a.is_current = 1 AND ac.component_type = 'city' "
        "AND lower(ac.component_value) LIKE ? "
        "AND (c.latitude IS NULL OR c.longitude IS NULL OR c.latitude = 0)",
        (f"%{city.lower()}%",)).fetchall():
        null_city.setdefault(r["id"], {"id": r["id"], "rid": r["rid"],
                                       "name": r["name"], "lat": None, "lon": None})
    merged = dict(in_boundary)
    merged.update(null_city)

    have_street = {r["church_id"] for r in db.execute(
        "SELECT DISTINCT a.church_id FROM church_addresses a "
        "JOIN address_components ac ON ac.address_id = a.address_id "
        "WHERE a.is_current = 1 AND ac.component_type = 'street' "
        "AND trim(coalesce(ac.component_value, '')) != ''").fetchall()}

    unknowns = []
    for cid, rec in merged.items():
        if cid in have_street:
            continue
        comps = get_address_components(db, cid)
        rec["city"] = comps.get("city") or ""
        rec["state"] = comps.get("state") or ""
        rec["zip"] = comps.get("postcode") or comps.get("zip") or ""
        unknowns.append(rec)
    unknowns.sort(key=lambda x: (x["lat"] is None, x["id"]))
    return merged, have_street, unknowns


def mapbox_forward(query, proximity=None):
    url = (f"{MAPBOX_URL}?q={urllib.parse.quote(query)}&access_token={MAPBOX_KEY}"
           f"&limit=1&country=US&language=en")
    if proximity:
        url += f"&proximity={proximity[1]},{proximity[0]}"
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}
    feats = data.get("features") or []
    if not feats:
        return None
    f = feats[0]
    props = f.get("properties") or {}
    coords = (f.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2:
        return None
    context = props.get("context") or {}
    street = None
    ac = context.get("address") or {}
    if ac.get("street_name"):
        street = f"{ac.get('address_number', '')} {ac['street_name']}".strip()
    if not street:
        street = (context.get("street") or {}).get("name")
    if not street and props.get("feature_type") in ("address", "street"):
        street = props.get("name")
    return {"lat": coords[1], "lon": coords[0],
            "feature_type": props.get("feature_type"),
            "matched_name": props.get("name"),
            "full_address": props.get("full_address"), "street": street}


def audit(db, poly, city):
    merged, have_street, unknowns = load_unknowns(db, poly, city)
    n_null = sum(1 for r in merged.values() if r["lat"] is None)
    print(f"churches in boundary (+ null-GPS city-text): {len(merged):,}")
    print(f"  with GPS: {len(merged) - n_null:,}")
    print(f"  null/zero GPS: {n_null:,}")
    print(f"  already have street: {len(have_street & set(merged)):,}")
    print(f"  UNKNOWNS (Mapbox targets): {len(unknowns):,}")
    if unknowns:
        print("\nSample:")
        for r in unknowns[:12]:
            print(f"  [{r['id']}] {str(r['name'])[:50]:50s} ({r['lat']}, {r['lon']}) "
                  f"city={r['city'][:18]}")


def run_write(db, poly, city, staging, limit):
    from gw_db import Provenance, log_change, log_changes_batch
    from scripts.grid_address import set_components

    merged, have_street, unknowns = load_unknowns(db, poly, city)
    if limit:
        unknowns = unknowns[:limit]
    print(f"[..] Mapbox targets: {len(unknowns):,}")

    gs_tables = [t for t in ("church_location", "church_addresses")
                 if "geocode_source" in [c[1] for c in db.execute(f"PRAGMA table_info({t})")]]

    os.makedirs(os.path.dirname(staging), exist_ok=True)
    s = sqlite3.connect(staging)
    s.execute("""CREATE TABLE IF NOT EXISTS results (
        church_id INTEGER PRIMARY KEY, name TEXT, old_lat REAL, old_lon REAL,
        new_lat REAL, new_lon REAL, feature_type TEXT, matched_name TEXT,
        full_address TEXT, street TEXT, status TEXT)""")
    s.commit()

    t0 = time.time()
    n_ok = n_nomatch = n_nofound = n_err = 0
    changes = []
    with Provenance(db, script_name="fill_addresses_mapbox.py", source=SOURCE,
                    action="geocoded", fields="latitude,longitude,street",
                    records_attempted=len(unknowns)) as prov:
        for i, rec in enumerate(unknowns, 1):
            qparts = [rec["name"] or "", rec.get("city") or city]
            if rec.get("zip"):
                qparts.append(rec["zip"])
            query = ", ".join(p for p in qparts if p) + ", IL, USA"
            prox = (rec["lat"], rec["lon"]) if (rec["lat"] and rec["lon"]) else None
            res = mapbox_forward(query, proximity=prox)
            status = "error" if not res else ("ok" if "error" not in res else "error")
            street = res.get("street") if isinstance(res, dict) else None
            matched = res.get("matched_name") if isinstance(res, dict) else None
            full = res.get("full_address") if isinstance(res, dict) else None
            ftype = res.get("feature_type") if isinstance(res, dict) else None
            new_lat = res.get("lat") if isinstance(res, dict) else None
            new_lon = res.get("lon") if isinstance(res, dict) else None

            accepted = (status == "ok" and new_lat is not None and new_lon is not None
                        and ftype == "poi"
                        and token_jaccard(rec["name"], matched or "") >= 0.4)
            if accepted:
                old_lat, old_lon = rec["lat"], rec["lon"]
                db.execute("UPDATE churches SET latitude=?, longitude=? WHERE rowid=?",
                           (new_lat, new_lon, rec["rid"]))
                db.execute("INSERT OR IGNORE INTO church_location (church_id) VALUES (?)",
                           (rec["id"],))
                for t in gs_tables:
                    db.execute(f"UPDATE {t} SET geocode_source='mapbox' WHERE church_id=?",
                               (rec["id"],))
                changes.append((rec["id"], "latitude", old_lat, new_lat))
                changes.append((rec["id"], "longitude", old_lon, new_lon))
                if street:
                    set_components(db, rec["id"], {"street": street}, update_legacy=True)
                    log_change(db, rec["id"], "street", None, street, source=SOURCE)
                n_ok += 1
                marker = "OK"
            elif status == "error":
                n_err += 1
                marker = "ERR"
            elif status == "ok":
                n_nomatch += 1
                marker = "NOMATCH"
                status = "nomatch"
            else:
                n_nofound += 1
                marker = "MISS"

            s.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (rec["id"], rec["name"], rec["lat"], rec["lon"], new_lat, new_lon,
                       ftype, matched, full, street, status))
            print(f"\n[{marker}] {rec['id']} | {str(rec['name'])[:32]:32s} "
                  f"-> {str(matched)[:32]:32s} | {str(street)[:38]}")
            progress_bar(i, len(unknowns), t0)
            if i % 100 == 0:
                db.commit(); s.commit()
            time.sleep(REQ_DELAY)

        log_changes_batch(db, changes, source=SOURCE)
        prov.churches_updated = n_ok
        prov.records_matched = n_ok
        db.commit(); s.commit()
    db.commit()
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print(f"\n[DONE] ok={n_ok} nomatch={n_nomatch} missing={n_nofound} errors={n_err} "
          f"({len(changes)} change-log rows) -> {staging}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boundary", required=True, help=".geojson/.shp boundary")
    ap.add_argument("--city", required=True, help="fallback city name for queries")
    ap.add_argument("--staging", default="E:/grid/data/staging/mapbox_address_fill.db")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from gw_db import connect
    db = connect(DB)
    db._conn.row_factory = sqlite3.Row
    poly = load_poly(args.boundary)
    print(f"[OK] boundary: {poly.geom_type}, valid={poly.is_valid}")

    if args.write:
        run_write(db, poly, args.city, args.staging, args.limit)
    else:
        audit(db, poly, args.city)
    db.close()


if __name__ == "__main__":
    main()

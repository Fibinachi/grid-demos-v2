"""
fill_addresses_reverse.py - Reverse-geocode churches lacking a street address.

For churches inside a boundary that already HAVE GPS but no street address,
Mapbox reverse geocoding (lat/lon -> address) is far more reliable than
forward name-matching. Extracts street / city / state / postcode and writes
them via scripts.grid_address.set_components.

Usage:
  python scripts/enrichment/fill_addresses_reverse.py \
      --boundary data/cook_boundary/cook_county.geojson        # audit (no API)
  python scripts/enrichment/fill_addresses_reverse.py \
      --boundary data/cook_boundary/cook_county.geojson --write
  python scripts/enrichment/fill_addresses_reverse.py \
      --boundary data/cook_boundary/cook_county.geojson --write --limit 200
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
REVERSE_URL = "https://api.mapbox.com/search/geocode/v6/reverse"
REQ_DELAY = 0.12
SOURCE = "mapbox_reverse_fill_2026"


def progress_bar(current, total, start):
    pct = current / total * 100 if total else 100
    filled = int(40 * current / total) if total else 40
    print(f"\r[{'#'*filled}{'-'*(40-filled)}] {pct:5.1f}%  {current}/{total}  "
          f"{time.time()-start:6.1f}s", end="", flush=True)


def load_poly(path):
    if path.lower().endswith((".geojson", ".json")):
        with open(path, encoding="utf-8") as f:
            gj = json.load(f)
        return make_valid(shape(gj["features"][0]["geometry"]))
    import geopandas as gpd
    gdf = gpd.read_file(path)
    if gdf.crs is not None and gdf.crs.to_epsg() not in (4326, None):
        gdf = gdf.to_crs(4326)
    return make_valid(gdf.geometry.iloc[0])


def load_targets(db, poly):
    minx, miny, maxx, maxy = poly.bounds
    rows = db.execute(
        "SELECT c.id, c.rowid AS rid, c.name, c.latitude, c.longitude "
        "FROM churches c "
        "WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL "
        "AND c.latitude BETWEEN ? AND ? AND c.longitude BETWEEN ? AND ?",
        (miny, maxy, minx, maxx)).fetchall()
    in_boundary = [r for r in rows
                   if Point(r["longitude"], r["latitude"]).within(poly)]

    have_street = {r["church_id"] for r in db.execute(
        "SELECT DISTINCT a.church_id FROM church_addresses a "
        "JOIN address_components ac ON ac.address_id = a.address_id "
        "WHERE a.is_current = 1 AND ac.component_type = 'street' "
        "AND trim(coalesce(ac.component_value, '')) != ''").fetchall()}

    return [r for r in in_boundary if r["id"] not in have_street]


def reverse_geocode(lat, lon):
    url = (f"{REVERSE_URL}?longitude={lon}&latitude={lat}"
           f"&access_token={MAPBOX_KEY}&limit=1&types=address")
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}
    feats = data.get("features") or []
    if not feats:
        return None
    props = feats[0].get("properties") or {}
    context = props.get("context") or {}

    def _g(*keys):
        for k in keys:
            d = context.get(k)
            if isinstance(d, dict) and d.get("name"):
                return d["name"]
        return None

    street = None
    ac = context.get("address") or {}
    if ac.get("street_name"):
        street = f"{ac.get('address_number', '')} {ac['street_name']}".strip()
    if not street:
        street = (props.get("full_address") or "").split(",")[0].strip() or None
    region = context.get("region") or {}
    return {"street": street,
            "city": _g("place", "locality", "district"),
            "state": region.get("region_code") or region.get("name"),
            "postcode": _g("postcode"),
            "full_address": props.get("full_address"),
            "matched_name": props.get("name")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boundary", required=True)
    ap.add_argument("--staging", default="E:/grid/data/staging/reverse_address_fill.db")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from gw_db import connect, Provenance, log_change
    from scripts.grid_address import set_components

    db = connect(DB)
    db._conn.row_factory = sqlite3.Row
    poly = load_poly(args.boundary)
    targets = load_targets(db, poly)
    if args.limit:
        targets = targets[:args.limit]
    print(f"[OK] boundary: {poly.geom_type}, valid={poly.is_valid}")
    print(f"[OK] reverse-geocode targets (GPS, no street): {len(targets):,}")

    if not args.write:
        print("\nSample:")
        for r in targets[:12]:
            print(f"  [{r['id']}] {str(r['name'])[:50]:50s} ({r['latitude']:.5f}, {r['longitude']:.5f})")
        print("\nuse --write to apply.")
        db.close()
        return

    gs_tables = [t for t in ("church_location", "church_addresses")
                 if "geocode_source" in [c[1] for c in db.execute(f"PRAGMA table_info({t})")]]
    os.makedirs(os.path.dirname(args.staging), exist_ok=True)
    s = sqlite3.connect(args.staging)
    s.execute("""CREATE TABLE IF NOT EXISTS results (
        church_id INTEGER PRIMARY KEY, name TEXT, lat REAL, lon REAL,
        street TEXT, city TEXT, state TEXT, postcode TEXT, full_address TEXT, status TEXT)""")
    s.commit()

    t0 = time.time()
    n_ok = n_nostreet = n_err = n_nofound = 0
    with Provenance(db, script_name="fill_addresses_reverse.py", source=SOURCE,
                    action="geocoded", fields="street,city,state,postcode",
                    records_attempted=len(targets)) as prov:
        for i, r in enumerate(targets, 1):
            res = reverse_geocode(r["latitude"], r["longitude"])
            status = "error" if not res else ("ok" if "error" not in res else "error")
            street = res.get("street") if isinstance(res, dict) else None
            city_v = res.get("city") if isinstance(res, dict) else None
            state_v = res.get("state") if isinstance(res, dict) else None
            post_v = res.get("postcode") if isinstance(res, dict) else None
            full = res.get("full_address") if isinstance(res, dict) else None

            if status == "ok" and street:
                comps = {"street": street}
                if city_v:
                    comps["city"] = city_v
                if state_v:
                    comps["state"] = state_v
                if post_v:
                    comps["postcode"] = post_v
                set_components(db, r["id"], comps, update_legacy=False)
                for t in gs_tables:
                    db.execute(f"UPDATE {t} SET geocode_source='mapbox' WHERE church_id=?",
                               (r["id"],))
                log_change(db, r["id"], "street", None, street, source=SOURCE)
                n_ok += 1
                marker = "OK"
            elif status == "error":
                n_err += 1
                marker = "ERR"
            elif status == "ok":
                n_nostreet += 1
                marker = "NOSTREET"
                status = "nostreet"
            else:
                n_nofound += 1
                marker = "MISS"

            s.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (r["id"], r["name"], r["latitude"], r["longitude"],
                       street, city_v, state_v, post_v, full, status))
            print(f"\n[{marker}] {r['id']} | {str(r['name'])[:34]:34s} | "
                  f"{str(street)[:42]}")
            progress_bar(i, len(targets), t0)
            if i % 100 == 0:
                db.commit(); s.commit()
            time.sleep(REQ_DELAY)

        prov.churches_updated = n_ok
        prov.records_matched = n_ok
        db.commit(); s.commit()
    db.commit()
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    s.close()
    print(f"\n[DONE] ok={n_ok} nostreet={n_nostreet} missing={n_nofound} errors={n_err} "
          f"-> {args.staging}")
    db.close()


if __name__ == "__main__":
    main()

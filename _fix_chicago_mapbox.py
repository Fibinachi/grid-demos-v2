"""
_fix_chicago_mapbox.py - Mapbox-geocode Chicago churches lacking a street address
=================================================================================
For Chicago churches that are "unknowns" (no street address component), use
Mapbox forward geocoding to:
  1. get street-level coordinates (fixes centroid / null GPS), and
  2. capture the MATCHED NAME + full address from Mapbox.

The matched name is critical for the follow-up step that converts
holding-company records (e.g. "Catholic Bishop of Chicago") into the actual
church they hold (e.g. "St. Mary's Church").

Chicago is identified by point-in-polygon against
data/chicago_boundary/chicago_boundary.geojson. The church_location.in_chicago
column is NOT used (deprecated / unreliable).

Modes:
  .venv\\Scripts\\python.exe _fix_chicago_mapbox.py                    # --audit (read-only)
  .venv\\Scripts\\python.exe _fix_chicago_mapbox.py --write            # Mapbox all unknowns
  .venv\\Scripts\\python.exe _fix_chicago_mapbox.py --write --limit 1000

Writes (in --write):
  churches.latitude / churches.longitude            (core columns)
  church_location.geocode_source = 'mapbox'         (enrichment column)
  address_components.street                         (via scripts.grid_address.set_components)
  enrichment_change_log + provenance_log            (gw_db)
  data/staging/chicago_mapbox_results.db            (results for the rename step)
"""
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

from shapely.geometry import Point, shape
from shapely.validation import make_valid

sys.path.insert(0, r"E:\grid")

DB = r"E:\grid\churches.db"
GEOJSON = r"E:\grid\data\chicago_boundary\chicago_boundary.geojson"
STAGING = r"E:\grid\data\staging\chicago_mapbox_results.db"

MAPBOX_KEY = os.environ.get("MAPBOX_API_KEY", "")
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
MAPBOX_URL = "https://api.mapbox.com/search/geocode/v6/forward"
REQ_DELAY = 0.12          # ~8 req/sec, Mapbox free tier safe
SOURCE = "mapbox_chicago_2026-08-12"


def progress_bar(current, total, start, label=""):
    pct = current / total * 100 if total else 100
    width = 40
    filled = int(width * current / total) if total else width
    bar = "#" * filled + "-" * (width - filled)
    el = time.time() - start
    print(f"\r[{bar}] {pct:5.1f}%  {current}/{total}  {el:6.1f}s  {label}",
          end="", flush=True)


def token_jaccard(a, b):
    import re
    sa = set(re.sub(r"[^a-z0-9 ]", " ", (a or "").lower()).split())
    sb = set(re.sub(r"[^a-z0-9 ]", " ", (b or "").lower()).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def load_boundary():
    with open(GEOJSON) as f:
        gj = json.load(f)
    return make_valid(shape(gj["features"][0]["geometry"]))


def load_chicago_unknowns(db):
    """Return list of dicts for Chicago churches that lack a street address."""
    from scripts.grid_address import get_address_components

    poly = load_boundary()
    minx, miny, maxx, maxy = poly.bounds

    # (A) GPS churches inside the bbox, then exact point-in-polygon
    rows = db.execute("""
        SELECT id, rowid AS rid, name, latitude, longitude
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?
    """, (miny, maxy, minx, maxx)).fetchall()

    in_boundary = {}
    for r in rows:
        if Point(r["longitude"], r["latitude"]).within(poly):
            in_boundary[r["id"]] = {
                "id": r["id"], "rid": r["rid"], "name": r["name"],
                "lat": r["latitude"], "lon": r["longitude"],
            }

    # (B) NULL/zero-GPS churches whose city text says Chicago
    null_chicago = {}
    for r in db.execute("""
        SELECT DISTINCT a.church_id AS id, c.rowid AS rid, c.name
        FROM church_addresses a
        JOIN address_components ac ON ac.address_id = a.address_id
        JOIN churches c ON c.id = a.church_id
        WHERE a.is_current = 1 AND ac.component_type = 'city'
          AND lower(ac.component_value) LIKE '%chicago%'
          AND (c.latitude IS NULL OR c.longitude IS NULL OR c.latitude = 0)
    """).fetchall():
        null_chicago.setdefault(r["id"], {
            "id": r["id"], "rid": r["rid"], "name": r["name"],
            "lat": None, "lon": None,
        })

    merged = dict(in_boundary)
    merged.update(null_chicago)

    # Which already have a street component?
    have_street = {
        r["church_id"] for r in db.execute("""
            SELECT DISTINCT a.church_id
            FROM church_addresses a
            JOIN address_components ac ON ac.address_id = a.address_id
            WHERE a.is_current = 1 AND ac.component_type = 'street'
              AND trim(coalesce(ac.component_value, '')) != ''
        """).fetchall()
    }

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
    """Mapbox v6 forward geocode. Returns dict or None."""
    url = f"{MAPBOX_URL}?q={urllib.parse.quote(query)}&access_token={MAPBOX_KEY}&limit=1&country=US&language=en"
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
    geom = f.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        return None

    context = props.get("context") or {}
    street = None
    addr_ctx = context.get("address") or {}
    if addr_ctx.get("street_name"):
        street = f"{addr_ctx.get('address_number', '')} {addr_ctx['street_name']}".strip()
    if not street:
        sctx = context.get("street") or {}
        street = sctx.get("name") or None
    if not street and props.get("feature_type") in ("address", "street"):
        street = props.get("name") or None

    return {
        "lat": coords[1],
        "lon": coords[0],
        "feature_type": props.get("feature_type"),
        "matched_name": props.get("name"),
        "full_address": props.get("full_address"),
        "street": street,
    }


def audit():
    from gw_db import connect
    db = connect(DB)
    db._conn.row_factory = sqlite3.Row
    merged, have_street, unknowns = load_chicago_unknowns(db)
    n_boundary = len(merged) - 0
    n_null = sum(1 for r in merged.values() if r["lat"] is None)
    n_street = len(have_street & set(merged))
    print(f"Chicago churches (boundary + null-GPS Chicago-city text): {len(merged):,}")
    print(f"  with GPS inside boundary: {len(merged) - n_null:,}")
    print(f"  null/zero GPS (city text = Chicago): {n_null:,}")
    print(f"  already have street address: {n_street:,}")
    print(f"  UNKNOWNS (no street, Mapbox targets): {len(unknowns):,}")
    if unknowns:
        print("\nSample of 10 unknowns:")
        for r in unknowns[:10]:
            print(f"  [{r['id']}] {str(r['name'])[:55]:55s} "
                  f"({r['lat']}, {r['lon']}) city={r['city'][:20]}")
    db.close()


def run_write(limit):
    from gw_db import connect, Provenance, log_change, log_changes_batch
    from scripts.grid_address import set_components

    db = connect(DB)
    db._conn.row_factory = sqlite3.Row
    merged, have_street, unknowns = load_chicago_unknowns(db)
    if limit:
        unknowns = unknowns[:limit]
    print(f"[..] Mapbox targets: {len(unknowns):,}")

    gs_tables = [t for t in ("church_location", "church_addresses")
                 if "geocode_source" in [c[1] for c in db.execute(f"PRAGMA table_info({t})")]]
    print(f"[..] geocode_source tables: {gs_tables}")

    os.makedirs(os.path.dirname(STAGING), exist_ok=True)
    s = sqlite3.connect(STAGING)
    s.execute("""CREATE TABLE IF NOT EXISTS results (
        church_id INTEGER PRIMARY KEY, name TEXT,
        old_lat REAL, old_lon REAL, new_lat REAL, new_lon REAL,
        feature_type TEXT, matched_name TEXT, full_address TEXT,
        street TEXT, status TEXT)""")
    s.commit()

    t0 = time.time()
    n_ok = n_nofound = n_nomatch = n_err = 0
    changes = []

    with Provenance(
        db, script_name="_fix_chicago_mapbox.py", source=SOURCE,
        action="geocoded", fields="latitude,longitude,street",
        records_attempted=len(unknowns),
    ) as prov:
        for i, rec in enumerate(unknowns, 1):
            qparts = [rec["name"] or "", rec.get("city") or "Chicago"]
            if rec.get("zip"):
                qparts.append(rec["zip"])
            query = ", ".join(p for p in qparts if p) + ", IL, USA"

            prox = (rec["lat"], rec["lon"]) if (rec["lat"] is not None and rec["lon"] is not None) else None
            res = mapbox_forward(query, proximity=prox)
            status = "error" if not res else ("ok" if "error" not in res else "error")
            street = res.get("street") if isinstance(res, dict) else None
            matched = res.get("matched_name") if isinstance(res, dict) else None
            full = res.get("full_address") if isinstance(res, dict) else None
            ftype = res.get("feature_type") if isinstance(res, dict) else None
            new_lat = res.get("lat") if isinstance(res, dict) else None
            new_lon = res.get("lon") if isinstance(res, dict) else None

            accepted = (
                status == "ok"
                and new_lat is not None and new_lon is not None
                and ftype == "poi"
                and token_jaccard(rec["name"], matched or "") >= 0.4
            )

            if accepted:
                old_lat, old_lon = rec["lat"], rec["lon"]
                db.execute(
                    "UPDATE churches SET latitude=?, longitude=? WHERE rowid=?",
                    (new_lat, new_lon, rec["rid"]),
                )
                db.execute("INSERT OR IGNORE INTO church_location (church_id) VALUES (?)",
                           (rec["id"],))
                for t in gs_tables:
                    db.execute(f"UPDATE {t} SET geocode_source='mapbox' WHERE church_id=?",
                               (rec["id"],))
                changes.append((rec["id"], "latitude", old_lat, new_lat))
                changes.append((rec["id"], "longitude", old_lon, new_lon))
                if street and rec.get("street") is None:
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

            s.execute("""INSERT OR REPLACE INTO results
                (church_id, name, old_lat, old_lon, new_lat, new_lon,
                 feature_type, matched_name, full_address, street, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (rec["id"], rec["name"], rec["lat"], rec["lon"],
                 new_lat, new_lon, ftype, matched, full, street, status))

            print(f"\n[{marker}] {rec['id']} | {str(rec['name'])[:35]:35s} "
                  f"-> {str(matched)[:35]:35s} | {str(street)[:40]}")
            progress_bar(i, len(unknowns), t0)

            if i % 100 == 0:
                db.commit()
                s.commit()
            time.sleep(REQ_DELAY)

        log_changes_batch(db, changes, source=SOURCE)
        prov.churches_updated = n_ok
        prov.records_matched = n_ok
        db.commit()
        s.commit()

    db.commit()
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    s.close()
    print(f"\n[DONE] ok={n_ok} nomatch={n_nomatch} missing={n_nofound} errors={n_err} "
          f"({len(changes)} change-log rows). Results in {STAGING}")


def main():
    args = sys.argv[1:]
    write = "--write" in args
    limit = 0
    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
    if write:
        run_write(limit)
    else:
        audit()


if __name__ == "__main__":
    main()

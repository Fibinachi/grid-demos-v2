"""Fix country='MX' mislabeling by spatial join vs actual country/state polygons.

Two-phase design to avoid SQLite WAL lock conflicts:

  python fix_mx_country_mislabel.py              # Phase 1: read-only spatial analysis
  python fix_mx_country_mislabel.py --apply       # Phase 2: apply corrections

Phase 1 loads MX and US polygons from world_borders.db, loads all ~80K MX-labeled
churches with GPS coords, runs spatial join, and writes results to a temp JSON.

Phase 2 reads the temp JSON and applies: country='US', state=postal_code,
plus provenance + enrichment logging.
"""

import sqlite3, json, os, sys
from datetime import datetime, timezone
import geopandas as gpd
from shapely import wkb, Point
import pandas as pd

DB = r"E:\grid\churches.db"
GEO_DB = r"E:\grid\data\natural_earth\world_borders.db"
SCRIPT = "fix_mx_country_mislabel.py"
TEMP = r"E:\grid\_mx_fix_temp.json"
NOW = lambda: datetime.now(timezone.utc).isoformat()


# ───────── helpers ─────────

def _load_gdf(geo, table, cols, where_clause="", params=()):
    """Load a GeoDataFrame from world_borders.db via WKB."""
    sql = f"SELECT {','.join(cols)} FROM {table} {where_clause}"
    df = pd.read_sql(sql, geo, params=params)
    if "geometry_wkb" in df.columns:
        df["geometry"] = df["geometry_wkb"].apply(
            lambda w: wkb.loads(w) if w and isinstance(w, bytes) else None
        )
        df.drop(columns=["geometry_wkb"], inplace=True)
    return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")


def _churches_gdf(db):
    """Load MX churches with GPS as a GeoDataFrame (cursor-based, no pd.read_sql on churches.db)."""
    cur = db.cursor()
    cur.execute("""
        SELECT rowid, name, city, state, country, latitude, longitude, source, faith
        FROM churches
        WHERE country='MX' AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude != 0 AND longitude != 0
    """)
    rows = cur.fetchall()
    if not rows:
        return gpd.GeoDataFrame()
    df = pd.DataFrame(rows, columns=[
        "rowid", "name", "city", "state", "country",
        "latitude", "longitude", "source", "faith"
    ])
    df["geometry"] = df.apply(lambda r: Point(r["longitude"], r["latitude"]), axis=1)
    return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")


# ───────── Phase 1 — analysis (read-only) ─────────

def phase1():
    print("=" * 60)
    print("PHASE 1: Spatial analysis (read-only — safe to run alongside classifiers)")
    print("=" * 60)

    geo = sqlite3.connect(GEO_DB)
    db = sqlite3.connect(DB, timeout=5)

    # Country polygons
    print("Loading country polygons…")
    countries = _load_gdf(geo, "world_borders",
                          ["id", "name", "iso_a2", "geometry_wkb"],
                          "WHERE iso_a2 IN (?,?)", ("US", "MX"))
    print(f"  US: {countries[countries.iso_a2=='US'].shape[0]:,}  MX: {countries[countries.iso_a2=='MX'].shape[0]:,}")

    # State polygons
    print("Loading US state polygons…")
    states = _load_gdf(geo, "state_borders",
                       ["id", "name", "postal", "geometry_wkb"],
                       "WHERE iso_a2=?", ("US",))
    print(f"  {states.shape[0]:,} state/territory polygons")

    # MX churches
    print("Loading MX-labeled churches with GPS…")
    churches = _churches_gdf(db)
    total = len(churches)
    print(f"  {total:,} records loaded")

    # Country spatial join
    print("Running country spatial join…")
    joined = gpd.sjoin(churches, countries[["iso_a2", "geometry"]],
                       how="left", predicate="within")

    in_us   = joined[joined.iso_a2 == "US"].rowid.tolist()
    in_mx   = joined[joined.iso_a2 == "MX"].rowid.tolist()
    neither = joined[joined.iso_a2.isna()].rowid.tolist()
    print(f"  In US polygon: {len(in_us):>8,}")
    print(f"  In MX polygon: {len(in_mx):>8,}")
    print(f"  Neither:       {len(neither):>8,}")

    # State spatial join
    print(f"Running US state spatial join on {len(in_us):,} records…")
    us_churches = churches[churches.rowid.isin(in_us)].copy()
    state_join = gpd.sjoin(us_churches, states[["postal", "geometry"]],
                           how="left", predicate="within")

    state_map = {}
    for _, r in state_join.iterrows():
        rid = int(r.rowid)
        if pd.notna(r.postal) and rid not in state_map:
            state_map[rid] = r.postal
    print(f"  States assigned: {len(state_map):,}")

    # No-state sample
    no_state = [rid for rid in in_us if rid not in state_map]
    if no_state:
        cur = db.cursor()
        cur.execute(f"SELECT city, latitude, longitude FROM churches WHERE rowid IN ({','.join('?'*5)})",
                    no_state[:5])
        print(f"  No-state samples (first 5 of {len(no_state):,}): {cur.fetchall()}")

    # Close read connections
    geo.close()
    db.close()

    # Write temp file
    out = {
        "started": NOW(),
        "total_attempted": total,
        "to_fix": in_us,
        "state_map": {str(k): v for k, v in state_map.items()},
        "counts": {"in_us": len(in_us), "in_mx": len(in_mx),
                   "in_neither": len(neither), "states_assigned": len(state_map)}
    }
    with open(TEMP, "w") as f:
        json.dump(out, f)

    print(f"\n→ Results saved to {TEMP}")
    print(f"  {len(in_us):,} records to fix, {len(state_map):,} state assignments")
    print("  Run with --apply when the other agent is done.")


# ───────── Phase 2 — apply corrections ─────────

def phase2():
    print("=" * 60)
    print("PHASE 2: Applying corrections")
    print("=" * 60)

    if not os.path.exists(TEMP):
        print(f"ERROR: {TEMP} not found — run without --apply first.")
        return

    with open(TEMP) as f:
        data = json.load(f)

    us_ids = data["to_fix"]
    state_map = {int(k): v for k, v in data["state_map"].items()}
    started = data["started"]
    cnt = data["counts"]
    total_attempted = data["total_attempted"]

    print(f"  Records to fix: {len(us_ids):,}")
    print(f"  States to assign: {len(state_map):,}")

    db = sqlite3.connect(DB, timeout=60)
    c = db.cursor()

    # 1. country = 'US'
    print("Updating country…")
    for i in range(0, len(us_ids), 500):
        batch = us_ids[i:i+500]
        c.execute(f"UPDATE churches SET country='US' WHERE rowid IN ({','.join('?'*len(batch))})", batch)

    # 2. state
    state_updates = [(s, rid) for rid, s in state_map.items() if s]
    if state_updates:
        print(f"Updating state ({len(state_updates):,} records)…")
        c.executemany("UPDATE churches SET state=? WHERE rowid=?", state_updates)

    # 3. enrichment_change_log
    print("Logging changes…")
    rows = [(rid, "country", "MX", "US", SCRIPT) for rid in us_ids]
    rows += [(rid, "state", "NULL/blank", s, SCRIPT) for s, rid in state_map.items() if s]
    c.executemany(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?,?,?,?,?)",
        rows
    )

    # 4. provenance_log
    params = json.dumps({"method": "spatial join vs world_borders+state_borders", **cnt})
    c.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted,
             fields_populated, parameters, records_attempted,
             records_matched, status, notes)
        VALUES (?,?,?,?,?,0,?,?,?,?,'completed',?)
    """, (SCRIPT, SCRIPT, started, NOW(), len(us_ids),
          json.dumps(["country", "state"]), params,
          total_attempted, len(us_ids),
          f"{(len(state_updates)):,} state assignments"))

    db.commit()

    c.execute("SELECT COUNT(*) FROM churches WHERE country='MX'")
    remaining = c.fetchone()[0]

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  MX→US fixed:                  {len(us_ids):>8,}")
    print(f"  States assigned:              {len(state_updates):>8,}")
    print(f"  Confirmed as MX (unchanged):  {cnt['in_mx']:>8,}")
    print(f"  Needs review (no polygon):    {cnt['in_neither']:>8,}")
    print(f"  MX records remaining:         {remaining:>8,}")

    db.close()
    os.remove(TEMP)
    print(f"\n→ {TEMP} cleaned up. Done.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        phase2()
    else:
        phase1()

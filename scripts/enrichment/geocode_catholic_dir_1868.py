#!/usr/bin/env python3
"""
Geocode 1868 Catholic Directory entries.
Phase 1: City-centroid from GRID churches.db
Phase 2: Census batch geocoding for entries with street addresses
Phase 3: Proximity-match to existing GRID churches

Usage:
  python scripts/enrichment/geocode_catholic_dir_1868.py              # Full run
  python scripts/enrichment/geocode_catholic_dir_1868.py --phase 1    # City centroids only
  python scripts/enrichment/geocode_catholic_dir_1868.py --phase 2    # Census geocoding only
  python scripts/enrichment/geocode_catholic_dir_1868.py --phase 3    # GRID match only
  python scripts/enrichment/geocode_catholic_dir_1868.py --summary    # Stats only
"""

import sqlite3, json, time, requests, re, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

DIR_DB = Path("E:/grid/data/catholic_directory.db")
GRID_DB = Path("E:/grid/churches.db")
DIR_YEAR = 1868
CHUNK_SIZE = 500

# ── Ensure lat/lon columns exist ──
def ensure_schema():
    db = sqlite3.connect(str(DIR_DB))
    # Add lat/lon columns if needed
    try:
        db.execute("ALTER TABLE dir_entries ADD COLUMN latitude REAL")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE dir_entries ADD COLUMN longitude REAL")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE dir_entries ADD COLUMN geocode_source TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE dir_entries ADD COLUMN grid_church_rowid INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE dir_entries ADD COLUMN geocode_confidence REAL")
    except sqlite3.OperationalError:
        pass
    db.commit()
    db.close()


# ── Phase 1: City centroids from GRID ──
def phase1_city_centroids():
    """Get city centroid from existing GRID churches for each (city, state) pair.
    Uses a single bulk query to GRID, then matches in-memory."""
    print("\n" + "="*60)
    print("Phase 1: City-Centroid Geocoding")
    print("="*60)

    dir_db = sqlite3.connect(str(DIR_DB))
    dir_db.row_factory = sqlite3.Row

    # Collect unique (city, state) pairs
    pairs = dir_db.execute("""
        SELECT DISTINCT city, state FROM dir_entries
        WHERE directory_year=? AND city IS NOT NULL AND state IS NOT NULL
        AND latitude IS NULL
    """, (DIR_YEAR,)).fetchall()

    print(f"  {len(pairs):,} unique (city, state) pairs to resolve")

    # Bulk-load ALL US city centroids from GRID in one query
    grid = sqlite3.connect(str(GRID_DB))
    print("  Loading city centroids from GRID...")
    centroids = {}
    for row in grid.execute("""
        SELECT UPPER(city) as city, UPPER(state) as state,
               AVG(latitude) as lat, AVG(longitude) as lon, COUNT(*) as cnt
        FROM churches
        WHERE country='US' AND latitude IS NOT NULL AND longitude IS NOT NULL
        AND latitude != 0 AND city IS NOT NULL AND state IS NOT NULL
        GROUP BY UPPER(city), UPPER(state)
    """):
        if row[2] and row[3]:
            centroids[(row[0], row[1])] = (round(row[2], 6), round(row[3], 6), row[4])

    print(f"  Loaded {len(centroids):,} unique city centroids from GRID")

    # Match and update in bulk
    resolved = 0
    updates = []
    for pair in pairs:
        city, state = pair["city"], pair["state"]
        if not city or not state:
            continue
        key = (city.upper().strip(), state.upper().strip())
        if key in centroids:
            lat, lon, cnt = centroids[key]
            updates.append((lat, lon, DIR_YEAR, city, state))
            resolved += 1

    # Batch update
    for chunk_start in range(0, len(updates), CHUNK_SIZE):
        chunk = updates[chunk_start:chunk_start + CHUNK_SIZE]
        dir_db.executemany("""
            UPDATE dir_entries SET latitude=?, longitude=?,
            geocode_source='grid_city_centroid', geocode_confidence=0.7
            WHERE directory_year=? AND city=? AND state=? AND latitude IS NULL
        """, chunk)
    dir_db.commit()

    print(f"  Resolved {resolved:,}/{len(pairs):,}")
    print(f"  Updated {len(updates):,} entries with city centroids")

    grid.close()
    dir_db.close()
    return len(updates)


# ── Phase 2: Census batch geocoding for street addresses ──
def phase2_census_geocode():
    """Geocode entries with street addresses via Census batch API."""
    print("\n" + "="*60)
    print("Phase 2: Census Batch Geocoding (street addresses)")
    print("="*60)

    dir_db = sqlite3.connect(str(DIR_DB))
    dir_db.row_factory = sqlite3.Row

    entries = dir_db.execute("""
        SELECT id, name, address, city, state FROM dir_entries
        WHERE directory_year=? AND address IS NOT NULL AND length(address) > 3
        AND city IS NOT NULL AND state IS NOT NULL
        AND latitude IS NULL
    """, (DIR_YEAR,)).fetchall()

    print(f"  {len(entries):,} entries with street addresses to geocode")

    if not entries:
        dir_db.close()
        return 0

    # Build Census API payload (max 1000 per batch)
    BATCH = 1000
    geocoded = 0

    for batch_start in range(0, len(entries), BATCH):
        batch = entries[batch_start:batch_start + BATCH]

        # Build CSV: id, address, city, state, zip
        lines = ["Unique ID,Street address,City,State,ZIP"]
        for e in batch:
            uid = e["id"]
            addr = (e["address"] or "").replace(",", " ").strip()
            city = (e["city"] or "").strip()
            state = (e["state"] or "").strip()
            # Census API needs clean CSV
            line = f'{uid},"{addr}","{city}","{state}",""'
            lines.append(line)

        csv_text = "\n".join(lines)

        try:
            r = requests.post(
                "https://geocoding.geo.census.gov/geocoder/locations/addressbatch",
                data={"benchmark": "Public_AR_Current", "vintage": "Current_Current"},
                files={"addressFile": ("addrs.csv", csv_text.encode("utf-8"), "text/csv")},
                timeout=120,
            )

            if r.status_code == 200:
                for line in r.text.strip().split("\n"):
                    parts = line.split(",")
                    if len(parts) >= 6:
                        try:
                            uid = int(parts[0].strip('"'))
                            lat = float(parts[4].strip('"'))
                            lon = float(parts[5].strip('"'))
                            if lat != 0 and lon != 0:
                                dir_db.execute("""
                                    UPDATE dir_entries SET latitude=?, longitude=?,
                                    geocode_source='census_batch', geocode_confidence=0.9
                                    WHERE id=?
                                """, (round(lat, 6), round(lon, 6), uid))
                                geocoded += 1
                        except (ValueError, IndexError):
                            continue

            print(f"    Batch {batch_start//BATCH + 1}: {geocoded} geocoded so far")
        except Exception as e:
            print(f"    Batch error: {e}")

        time.sleep(1)

    dir_db.commit()
    print(f"  Census geocoded: {geocoded:,} entries")
    dir_db.close()
    return geocoded


# ── Phase 3: Match to GRID churches ──
def phase3_match_to_grid():
    """Proximity-match geocoded entries to existing GRID churches."""
    print("\n" + "="*60)
    print("Phase 3: Match to GRID Churches")
    print("="*60)

    dir_db = sqlite3.connect(str(DIR_DB))
    dir_db.row_factory = sqlite3.Row

    # Get geocoded entries
    entries = dir_db.execute("""
        SELECT id, name, city, state, latitude, longitude, entity_type
        FROM dir_entries
        WHERE directory_year=? AND latitude IS NOT NULL AND longitude IS NOT NULL
        AND grid_church_rowid IS NULL
    """, (DIR_YEAR,)).fetchall()

    print(f"  {len(entries):,} geocoded entries to match")

    grid = sqlite3.connect(str(GRID_DB))
    grid.row_factory = sqlite3.Row

    # Load GRID churches index for nearby lookup
    # Get all US churches with coords for KD-tree
    us_coords = grid.execute("""
        SELECT rowid, name, latitude, longitude, city, state, faith, tradition
        FROM churches WHERE country='US'
        AND latitude IS NOT NULL AND longitude IS NOT NULL
        AND latitude != 0
    """).fetchall()

    print(f"  {len(us_coords):,} US churches in GRID index")

    # Build spatial index via simple grid
    from math import radians, cos, sin, asin, sqrt

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        return R * 2 * asin(sqrt(a))

    # Simple grid bucketing: 0.01 degree (~1km) cells
    grid_cells = defaultdict(list)
    for c in us_coords:
        cell = (int(c["latitude"] * 100), int(c["longitude"] * 100))
        grid_cells[cell].append(c)

    matched = 0
    for i, e in enumerate(entries):
        elat, elon = e["latitude"], e["longitude"]
        ename = (e["name"] or "").lower().strip()
        cell = (int(elat * 100), int(elon * 100))

        best_match = None
        best_dist = 5.0  # max 5km
        best_score = 0

        # Check nearby cells
        for dc in range(-1, 2):
            for dr in range(-1, 2):
                c = (cell[0] + dr, cell[1] + dc)
                for gc in grid_cells.get(c, []):
                    dist = haversine(elat, elon, gc["latitude"], gc["longitude"])
                    if dist > best_dist:
                        continue

                    score = (1 - dist/max(best_dist, 0.001)) * 30  # proximity score max 30
                    gcname = (gc["name"] or "").lower().strip()

                    # Name match bonus
                    if ename and gcname:
                        # Remove common words for comparison
                        for w in ["church", "chapel", "cathedral", "saint", "st.", "st ",
                                   "catholic", "roman", "parish", "mission", "school",
                                   "academy", "college", "seminary", "convent", "hospital",
                                   "orphan", "asylum"]:
                            ename_clean = ename.replace(w, "")
                            gcname_clean = gcname.replace(w, "")

                        # Word overlap
                        ewords = set(ename_clean.split())
                        gwords = set(gcname_clean.split())
                        common = ewords & gwords
                        if common:
                            score += len(common) * 20

                        # Exact name match
                        if ename == gcname:
                            score += 50

                    # Faith bonus: Catholic entries should match Christian churches
                    gc_faith = (gc["faith"] or "").lower()
                    gc_tradition = (gc["tradition"] or "").lower()
                    if gc_faith == "christian":
                        score += 10
                        if any(w in gc_tradition for w in ["catholic", "roman"]):
                            score += 20  # Extra for Catholic tradition

                    # City match
                    if (e["city"] or "").upper() == (gc["city"] or "").upper():
                        score += 15

                    if score > best_score:
                        best_score = score
                        best_match = gc
                        best_dist = dist

        if best_match and best_score >= 60:
            dir_db.execute("""
                UPDATE dir_entries SET grid_church_rowid=?, geocode_confidence=?
                WHERE id=?
            """, (best_match["rowid"], min(0.95, best_score/100), e["id"]))
            matched += 1

        if (i+1) % 500 == 0:
            print(f"    {i+1:,}/{len(entries):,} processed, {matched:,} matched")

    dir_db.commit()
    print(f"  Matched: {matched:,}/{len(entries):,} ({matched/len(entries)*100:.1f}%)")

    dir_db.close()
    grid.close()
    return matched


# ── Summary ──
def print_summary():
    dir_db = sqlite3.connect(str(DIR_DB))
    dir_db.row_factory = sqlite3.Row

    total = dir_db.execute("SELECT COUNT(*) as c FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)).fetchone()["c"]
    geocoded = dir_db.execute("SELECT COUNT(*) as c FROM dir_entries WHERE directory_year=? AND latitude IS NOT NULL", (DIR_YEAR,)).fetchone()["c"]
    matched = dir_db.execute("SELECT COUNT(*) as c FROM dir_entries WHERE directory_year=? AND grid_church_rowid IS NOT NULL", (DIR_YEAR,)).fetchone()["c"]

    print(f"\n{'='*60}")
    print(f"1868 Geocoding Summary")
    print(f"{'='*60}")
    print(f"  Total entries:     {total:>8,}")
    print(f"  Geocoded:          {geocoded:>8,} ({geocoded/total*100:.1f}%)")
    print(f"  Matched to GRID:   {matched:>8,} ({matched/total*100:.1f}%)")

    # By source
    for r in dir_db.execute("""
        SELECT geocode_source, COUNT(*) as cnt FROM dir_entries
        WHERE directory_year=? AND latitude IS NOT NULL
        GROUP BY geocode_source ORDER BY cnt DESC
    """, (DIR_YEAR,)):
        print(f"    {r['geocode_source']:25s} {r['cnt']:>8,}")

    dir_db.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Geocode 1868 Catholic Directory entries")
    p.add_argument("--phase", type=int, choices=[1, 2, 3], help="Run specific phase only")
    p.add_argument("--summary", action="store_true", help="Show stats only")
    args = p.parse_args()

    ensure_schema()

    if args.summary:
        print_summary()
        sys.exit(0)

    if args.phase is None or args.phase == 1:
        phase1_city_centroids()

    if args.phase is None or args.phase == 2:
        phase2_census_geocode()

    if args.phase is None or args.phase == 3:
        phase3_match_to_grid()

    print_summary()
    print("Done.")

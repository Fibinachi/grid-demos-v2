"""
Import unmatched NHL landmarks using Wikipedia API for coordinate resolution.
Fetches Wikipedia pages via MediaWiki API to get coordinates, then either:
  - Finds matching church in DB via coordinate proximity + name match
  - Falls back to inserting new church records

Usage:
    python scripts/enrichment/import_nhl_unmatched.py
"""

import json
import math
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from gw_db import connect, Provenance, register_source, log_change, log_changes_batch

# ── Paths ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TARGETS_PATH = PROJECT_ROOT / "data" / "nhl_import_targets_39.json"
RAW_PATH = PROJECT_ROOT / "data" / "nhl_churches_raw.json"
CHUNK_SIZE = 500
SCRIPT_NAME = "import_nhl_unmatched"
SOURCE_NAME = "wikipedia_nhl_via_api"

# ── Wikipedia API helpers ──

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_HEADERS = {
    "User-Agent": "GRID-NHL-Import/1.0 (https://github.com/GRID-project; grid-project-research@example.com)"
}

def fetch_wikipedia_coords(title: str) -> dict | None:
    """Fetch coordinates and page info from Wikipedia for a given page title."""
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "coordinates|pageprops|extracts",
        "exintro": True,
        "exchars": 500,
        "explaintext": True,
        "formatversion": 2,
    }
    try:
        resp = httpx.get(WIKIPEDIA_API, params=params, headers=WIKIPEDIA_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return None
        page = pages[0]
        result = {
            "pageid": page.get("pageid"),
            "title": page.get("title"),
            "extract": page.get("extract", ""),
        }
        coords = page.get("coordinates")
        if coords:
            result["lat"] = coords[0].get("lat")
            result["lon"] = coords[0].get("lon")
        return result
    except Exception as e:
        print(f"    ⚠ API error: {e}")
        return None


def extract_wikipedia_title(url: str) -> str:
    """Extract the page title from a Wikipedia URL."""
    if not url:
        return ""
    # Handle encoded URLs
    from urllib.parse import unquote
    title = url.rsplit("/", 1)[-1]
    title = unquote(title)
    title = title.replace("_", " ")
    return title


# ── Coordinate distance ──

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Haversine distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Name normalization ──

def normalize(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_similarity(a: str, b: str) -> float:
    """Simple Jaccard-like name similarity based on word overlap."""
    words_a = set(normalize(a).split())
    words_b = set(normalize(b).split())
    skip = {"the", "church", "chapel", "of", "and", "in", "at", "st", "saint",
             "san", "santa", "first", "old", "new", "our", "lady",
             "mission", "cathedral", "temple", "house", "meeting",
             "episcopal", "ruins", "destroyed", "parish", "los", "las",
             "angeles", "de", "del", "borough", "county", "township"}
    words_a = words_a - skip
    words_b = words_b - skip
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


# ── DB Indexing ──

def build_spatial_index(db) -> list[dict]:
    """Load all churches with coordinates into memory."""
    c = db.cursor()
    c.execute("SELECT id, name, city, state, latitude, longitude FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY id")
    index = []
    for row in c.fetchall():
        index.append({
            "id": row[0],
            "name": (row[1] or "").strip(),
            "city": (row[2] or "").strip().lower(),
            "state": (row[3] or "").strip().upper(),
            "lat": row[4],
            "lon": row[5],
        })
    return index


def find_nearby_churches(spatial_index: list[dict], lat: float, lon: float, radius_km: float = 0.5) -> list[dict]:
    """Find all churches within radius_km of a point."""
    results = []
    for church in spatial_index:
        dist = haversine_km(lat, lon, church["lat"], church["lon"])
        if dist <= radius_km:
            results.append({**church, "distance_km": dist})
    results.sort(key=lambda r: r["distance_km"])
    return results


# ── Main import logic ──

def main():
    # Load targets
    with open(TARGETS_PATH, encoding="utf-8") as f:
        targets = json.load(f)

    # Load raw for supplementary data
    with open(RAW_PATH, encoding="utf-8") as f:
        raw_all = json.load(f)
    raw_by_name = {}
    for entry in raw_all:
        raw_by_name[entry["Church"]] = entry

    print(f"Loaded {len(targets)} target NHL entries")
    print()

    # Connect to DB
    db = connect(timeout=60)
    print(f"Building spatial index...")
    spatial_index = build_spatial_index(db)
    print(f"Loaded {len(spatial_index):,} geocoded churches into memory")

    # Register source
    register_source(db, SOURCE_NAME, "web_scrape",
                    description="Wikipedia API - coordinates and page data for NHL churches",
                    refreshable=True, refresh_url="same",
                    refresh_type="manual", refresh_freq="yearly")

    results = []

    with Provenance(db, SCRIPT_NAME, source=SOURCE_NAME,
                     action="enriched",
                     fields="is_landmark,heritage_status,heritage_source,name,city,state,latitude,longitude,country,denomination,building_year,source",
                     records_attempted=len(targets)) as prov:

        for idx, target in enumerate(targets, 1):
            nhl_name = target["name"]
            location = target["location"]
            url = target["url"]
            designated = target.get("designated", "")
            built = target.get("built", "")
            affiliation = target.get("affiliation", "")

            # Parse year from built string
            year = None
            if built:
                ym = re.search(r"(\d{4})", built)
                if ym:
                    year = int(ym.group(1))

            is_former = (designated == "")
            heritage_val = "Former National Historic Landmark" if is_former else "National Historic Landmark"
            heritage_src = f"NHL designated {designated}" if designated else "National Historic Landmark"

            print(f"[{idx:2d}/{len(targets)}] {nhl_name[:55]:55s}")

            # Fetch Wikipedia page for coordinates
            wiki_title = extract_wikipedia_title(url)
            page_data = fetch_wikipedia_coords(wiki_title)
            time.sleep(0.3)  # Be nice to Wikipedia API

            lat = page_data.get("lat") if page_data else None
            lon = page_data.get("lon") if page_data else None

            if lat and lon:
                print(f"      Coords: {lat:.5f}, {lon:.5f}")

                # Search nearby churches
                nearby = find_nearby_churches(spatial_index, lat, lon, radius_km=0.5)
                if not nearby:
                    nearby = find_nearby_churches(spatial_index, lat, lon, radius_km=2.0)

                best_match = None
                if nearby:
                    # Check each nearby by name similarity
                    for candidate in nearby[:10]:
                        sim = name_similarity(nhl_name, candidate["name"])
                        if sim > 0.3:
                            best_match = candidate
                            break
                    # If no good name match, take the closest one
                    if not best_match and nearby:
                        best_match = nearby[0]

                if best_match:
                    ch_id = best_match["id"]
                    dist = best_match["distance_km"]
                    print(f"      ✅ DB match: ID={ch_id} | '{best_match['name'][:45]:45s}' | {best_match.get('city','')}, {best_match.get('state','')} | dist={dist:.3f}km | sim={name_similarity(nhl_name, best_match['name']):.2f}")
                    # Update with NHL designation
                    c = db.cursor()
                    c.execute("SELECT heritage_status, heritage_source, is_landmark FROM churches WHERE id = ?", (ch_id,))
                    old = c.fetchone()
                    old_status, old_source, old_landmark = old if old else (None, None, None)

                    c.execute("""
                        UPDATE churches
                        SET is_landmark = 1,
                            heritage_status = ?,
                            heritage_source = ?
                        WHERE id = ?
                    """, (heritage_val, heritage_src, ch_id))

                    changes = []
                    if old_status != heritage_val:
                        changes.append((ch_id, "heritage_status", old_status, heritage_val))
                    if old_source != heritage_src:
                        changes.append((ch_id, "heritage_source", old_source, heritage_src))
                    if not old_landmark:
                        changes.append((ch_id, "is_landmark", str(old_landmark), "1"))

                    if changes:
                        log_changes_batch(db, changes, source=SCRIPT_NAME)

                    prov.churches_updated += 1
                    results.append({
                        "nhl_name": nhl_name,
                        "action": "updated",
                        "church_id": ch_id,
                        "db_name": best_match["name"],
                        "db_city": best_match.get("city", ""),
                        "db_state": best_match.get("state", ""),
                        "distance_km": round(dist, 4),
                        "name_similarity": round(name_similarity(nhl_name, best_match["name"]), 2),
                        "lat": lat,
                        "lon": lon,
                    })
                    continue

                # No nearby match found but we have coords - need to insert
                print(f"      No DB match within 2km — will insert new record")
            else:
                print(f"      No coordinates from Wikipedia")

            # ── Insert new record ──
            # Parse location
            loc_parts = [p.strip() for p in location.rsplit(",", 1)]
            city = loc_parts[0] if len(loc_parts) >= 1 else ""
            state_raw = loc_parts[1] if len(loc_parts) >= 2 else ""

            # Clean state
            state = state_raw.split()[0] if state_raw else ""
            state = re.sub(r"[^A-Za-z]", "", state).upper()[:2] if state else ""
            # Handle "South Carolina" -> "SC"
            state_map = {
                "SOUTH CAROLINA": "SC", "SOUTH": "SC",
                "NEW YORK CITY": "NY", "NEW YORK": "NY",
                "BUCKS COUNTY": "PA",
                "SAN LUIS OBISPO COUNTY": "CA",
                "MONTEREY COUNTY": "CA",  # We'll just use CA for the state
            }
            if state in state_map:
                state = state_map[state]

            # Determine country
            country = "US"

            # Determine denomination from affiliation
            denom_map = {
                "roman catholic": "Roman Catholic",
                "episcopal": "Episcopal",
                "anglican": "Anglican",
                "society of friends": "Society of Friends (Quaker)",
                "congregational": "Congregational",
                "congregational, unitarian universalist": "Unitarian Universalist",
                "unitarian universalist": "Unitarian Universalist",
                "anglican, unitarian": "Unitarian Universalist",
                "baptist": "Baptist",
                "presbyterian": "Presbyterian",
                "united church of christ": "United Church of Christ",
                "russian orthodox": "Russian Orthodox",
                "a.m.e.": "AME",
                "a.m.e. zion": "AME Zion",
                "reformed church of france": "Reformed",
            }
            denomination = denom_map.get(affiliation.lower().strip(), affiliation)

            # Insert new church
            c = db.cursor()
            try:
                c.execute("""
                    INSERT INTO churches
                        (name, city, state, country, latitude, longitude,
                         denomination, building_year, is_landmark,
                         heritage_status, heritage_source, source,
                         geocode_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """, (
                    nhl_name, city, state, country,
                    lat, lon,
                    denomination, year,
                    heritage_val, heritage_src,
                    SOURCE_NAME,
                    "wikipedia" if lat else None,
                ))
                church_id = c.lastrowid
                print(f"      ✅ Inserted: ID={church_id}")

                log_change(db, church_id, "name", None, nhl_name, source=SCRIPT_NAME)
                if city:
                    log_change(db, church_id, "city", None, city, source=SCRIPT_NAME)
                if state:
                    log_change(db, church_id, "state", None, state, source=SCRIPT_NAME)
                if country:
                    log_change(db, church_id, "country", None, country, source=SCRIPT_NAME)
                if lat and lon:
                    log_change(db, church_id, "latitude", None, str(lat), source=SCRIPT_NAME)
                    log_change(db, church_id, "longitude", None, str(lon), source=SCRIPT_NAME)
                if denomination:
                    log_change(db, church_id, "denomination", None, denomination, source=SCRIPT_NAME)
                if year:
                    log_change(db, church_id, "building_year", None, str(year), source=SCRIPT_NAME)
                log_change(db, church_id, "is_landmark", None, "1", source=SCRIPT_NAME)
                log_change(db, church_id, "heritage_status", None, heritage_val, source=SCRIPT_NAME)
                log_change(db, church_id, "heritage_source", None, heritage_src, source=SCRIPT_NAME)

                prov.churches_inserted += 1
                results.append({
                    "nhl_name": nhl_name,
                    "action": "inserted",
                    "church_id": church_id,
                    "lat": lat,
                    "lon": lon,
                    "city": city,
                    "state": state,
                })

            except Exception as e:
                print(f"      ❌ Insert failed: {e}")
                results.append({
                    "nhl_name": nhl_name,
                    "action": "error",
                    "error": str(e),
                })

            if (idx + 1) % CHUNK_SIZE == 0:
                db.commit()

        db.commit()

    # Write results
    output_path = PROJECT_ROOT / "data" / "nhl_unmatched_import_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    updated = sum(1 for r in results if r["action"] == "updated")
    inserted = sum(1 for r in results if r["action"] == "inserted")
    errors = sum(1 for r in results if r["action"] == "error")

    print(f"\n{'='*60}")
    print(f"Results: {updated} updated, {inserted} inserted, {errors} errors")
    print(f"Details: {output_path}")


if __name__ == "__main__":
    main()

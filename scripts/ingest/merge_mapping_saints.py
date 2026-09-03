"""
Mapping Saints Merge — Import 3,773 medieval Nordic religious places into churches.db.
Source: Mapping Saints REST API (saints.dh.gu.se), CC-BY-SA 4.0 / CC0.
Data: data/sources/mapping_saints_places.json (11 MB, downloaded 07-10).

Strategy:
1. Create mapping_saints table with full MS data
2. Match by GPS proximity (Haversine < 500m) within same country
3. For unmatched with Wikidata QID, try to find churches with same QID
4. Create new churches for unmatched entries
5. Log provenance
"""
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from gw_db import connect, Provenance, log_change

DB_PATH = "E:/grid/churches.db"
MS_JSON = Path("E:/grid/data/sources/mapping_saints_places.json")
MATCH_RADIUS_M = 500  # Match within 500m

# Country name to ISO2 mapping
COUNTRY_MAP = {
    "Sweden": "SE", "Sverige": "SE",
    "Finland": "FI",
    "Norway": "NO",
    "Denmark": "DK",
    "Germany": "DE",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
    "Poland": "PL",
    "Netherlands": "NL",
    "Estonia": "EE",
    "Latvia": "LV",
    "Switzerland": "CH",
    "England": "GB",
    "Russian Federation": "RU",
    "Israel": "IL",
    "Vatican City": "VA",
    "Baltic Sea": None,  # Can't match
    "Unknown": None,
}

# Place type mapping to GRID landmark_type
PLACE_TYPE_MAP = {
    "Parish church": "church",
    "Church": "church",
    "Church, Religious Order": "church",
    "Chapel": "chapel",
    "Chapel in church": "chapel",
    "Altar in church": "church",
    "Monastery": "monastery",
    "Holy Well": "shrine",
    "Wayside Shrine": "shrine",
    "Runestone": "monument",
    "Castle": "other",
    "Guild house": "community_center",
    "Hospital": "other",
    "Village": "other",
    "Town": "other",
    "Farm": "other",
    "Estate": "other",
    "Manor Farm": "other",
    "Landscape feature": "other",
    "Unknown": "other",
}

def progress_bar(current, total, width=40):
    if total == 0:
        return f"[{'█'*width}] {current}"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"


def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lon points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Load Mapping Saints JSON ──
print("Loading Mapping Saints JSON...")
with open(MS_JSON, encoding="utf-8") as f:
    ms_data = json.load(f)
results = ms_data["results"]
print(f"  {len(results):,} places")

# Extract relevant fields
ms_records = []
for r in results:
    geom = r.get("geometry") or {}
    coords = geom.get("coordinates", [None, None])
    lon, lat = (coords[0], coords[1]) if len(coords) >= 2 else (None, None)
    if lat is None or lon is None:
        continue

    place_type = (r.get("place_type") or {}).get("name", "Unknown")
    parish = (r.get("parish") or {}).get("name", "")
    diocese = ((r.get("parish") or {}).get("medival_organization") or {}).get("name", "")
    parent = (r.get("parent") or {}).get("name", "")
    country_ms = r.get("country", "Unknown")
    country_iso = COUNTRY_MAP.get(country_ms)
    wd = r.get("wikidata", "") or ""

    # Extract cult relations
    cults = []
    for cr in r.get("relation_cult_place", []):
        cults.append({
            "name": cr.get("place", ""),
            "type": cr.get("cult_type", ""),
            "agent": cr.get("relation_cult_agent", ""),
            "minyear": cr.get("minyear"),
            "maxyear": cr.get("maxyear"),
        })

    ms_records.append({
        "ms_id": r["id"],
        "name": r.get("name", ""),
        "place_type": place_type,
        "parish": parish,
        "diocese": diocese,
        "parent_place": parent,
        "municipality": r.get("municipality", ""),
        "county": r.get("county", ""),
        "country_ms": country_ms,
        "country_iso": country_iso,
        "lat": lat,
        "lon": lon,
        "wikidata": wd,
        "construction_date": r.get("construction_date", "") or "",
        "not_before": r.get("not_before", "") or "",
        "not_after": r.get("not_after", "") or "",
        "cults_json": json.dumps(cults, ensure_ascii=False) if cults else None,
        "comment": r.get("comment", "") or "",
    })

by_country = Counter(r["country_ms"] for r in ms_records)
print(f"  Parsed: {len(ms_records):,} records")
print(f"  Countries: {len(by_country)}")

# ── Create mapping_saints table ──
print("\nCreating mapping_saints table...")
db = connect(DB_PATH)
db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
db.execute("""
CREATE TABLE IF NOT EXISTS mapping_saints (
    ms_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    place_type TEXT,
    parish TEXT,
    diocese TEXT,
    parent_place TEXT,
    municipality TEXT,
    county TEXT,
    country_ms TEXT,
    country_iso TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    wikidata TEXT,
    construction_date TEXT,
    not_before TEXT,
    not_after TEXT,
    cults_json TEXT,
    comment TEXT
)
""")
db.commit()

# Clear and reload in batches
print("  Loading data...")
db.execute("DELETE FROM mapping_saints")
db.commit()

CHUNK = 500
for start in range(0, len(ms_records), CHUNK):
    chunk = ms_records[start:start + CHUNK]
    db.executemany("""
        INSERT OR REPLACE INTO mapping_saints
        (ms_id, name, place_type, parish, diocese, parent_place, municipality, county,
         country_ms, country_iso, lat, lon, wikidata, construction_date,
         not_before, not_after, cults_json, comment)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [(
        r["ms_id"], r["name"], r["place_type"], r["parish"], r["diocese"],
        r["parent_place"], r["municipality"], r["county"], r["country_ms"],
        r["country_iso"], r["lat"], r["lon"], r["wikidata"],
        r["construction_date"], r["not_before"], r["not_after"],
        r["cults_json"], r["comment"],
    ) for r in chunk])
    db.commit()
    print(f"  {progress_bar(start + len(chunk), len(ms_records))}", flush=True)

print(f"  {len(ms_records):,} rows inserted")

# ── Phase 1: GPS proximity match ──
print(f"\nPhase 1: GPS proximity match (< {MATCH_RADIUS_M}m)...")

# Load all churches in relevant countries with coords
iso_set = set(r["country_iso"] for r in ms_records if r["country_iso"])
iso_list = "','".join(iso_set)
churches = db.execute(f"""
    SELECT rowid, name, latitude, longitude, country
    FROM churches
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    AND country IN ('{iso_list}')
""").fetchall()
print(f"  {len(churches):,} candidate churches in target countries")

# Build church index by country with bbox pre-filter support
church_by_country = {}
for ch in churches:
    church_by_country.setdefault(ch[4], []).append(ch)

# Pre-compute bbox degree offset (~0.01 deg ≈ 1.1km at equator, ~550m at 60°N)
BBOX_DEG = 0.01

matched = {}  # ms_id -> church_rowid
church_matched = set()
gps_hits = 0

for i, ms in enumerate(ms_records):
    iso = ms["country_iso"]
    if not iso or iso not in church_by_country:
        continue
    best_dist = MATCH_RADIUS_M + 1
    best_ch = None
    mlat, mlon = ms["lat"], ms["lon"]
    # Bounding box pre-filter
    lat_min, lat_max = mlat - BBOX_DEG, mlat + BBOX_DEG
    lon_min, lon_max = mlon - BBOX_DEG, mlon + BBOX_DEG
    for ch in church_by_country[iso]:
        if ch[0] in church_matched:
            continue
        # Quick bbox check before expensive Haversine
        if not (lat_min <= ch[2] <= lat_max and lon_min <= ch[3] <= lon_max):
            continue
        dist = haversine_m(mlat, mlon, ch[2], ch[3])
        if dist < best_dist:
            best_dist = dist
            best_ch = ch
    if best_ch:
        matched[ms["ms_id"]] = best_ch[0]
        church_matched.add(best_ch[0])
        gps_hits += 1

    if (i + 1) % 500 == 0:
        print(f"  {progress_bar(i+1, len(ms_records))}  matched: {gps_hits}", flush=True)

print(f"  GPS matched: {gps_hits:,} / {len(ms_records):,}")

# ── Phase 2: Name similarity match for remaining ──
unmatched = [r for r in ms_records if r["ms_id"] not in matched]
print(f"\nPhase 2: Name match for {len(unmatched):,} unmatched...")

name_hits = 0
for i, ms in enumerate(unmatched):
    iso = ms["country_iso"]
    if not iso or iso not in church_by_country:
        continue
    ms_name = ms["name"].lower().strip()
    if len(ms_name) < 3:
        continue
    best_dist = MATCH_RADIUS_M * 4 + 1  # 2km for name match
    best_ch = None
    for ch in church_by_country[iso]:
        if ch[0] in church_matched:
            continue
        ch_name = (ch[1] or "").lower().strip()
        # Simple containment match
        if ms_name in ch_name or ch_name in ms_name:
            dist = haversine_m(ms["lat"], ms["lon"], ch[2], ch[3])
            if dist < best_dist:
                best_dist = dist
                best_ch = ch
    if best_ch:
        matched[ms["ms_id"]] = best_ch[0]
        church_matched.add(best_ch[0])
        name_hits += 1

    if (i + 1) % 500 == 0:
        print(f"  {progress_bar(i+1, len(unmatched))}  name matched: {name_hits}", flush=True)

print(f"  Name matched: {name_hits:,}")
total_matched = len(matched)
print(f"\nTotal matched: {total_matched:,} / {len(ms_records):,} ({total_matched/len(ms_records)*100:.1f}%)")

# ── Apply mapping_saints_id to churches ──
print("\nUpdating churches.mapping_saints_id...")
updated = 0
for ms_id, church_rowid in matched.items():
    db.execute("UPDATE churches SET mapping_saints_id = ? WHERE rowid = ?", (str(ms_id), church_rowid))
    updated += 1
db.commit()
print(f"  {updated:,} churches updated")

# ── Phase 3: Create new churches for unmatched ──
new_unmatched = [r for r in ms_records if r["ms_id"] not in matched]
print(f"\nPhase 3: Creating {len(new_unmatched):,} new church records...")

# Get max id
max_id = db.execute("SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) FROM churches").fetchone()[0]

new_created = 0
place_type_counts = Counter()

for i, ms in enumerate(new_unmatched):
    if not ms["country_iso"]:
        continue

    new_id = max_id + new_created + 1
    landmark_type = PLACE_TYPE_MAP.get(ms["place_type"], "other")
    place_type_counts[ms["place_type"]] += 1

    # Determine faith/tradition — medieval Nordic = Christian
    faith = "Christian"
    tradition = None
    taxonomy_id = None  # Default for non-church types
    if ms["place_type"] in ("Parish church", "Church", "Church, Religious Order", "Chapel",
                             "Chapel in church", "Altar in church", "Monastery"):
        tradition = "Catholic"  # Pre-Reformation = Catholic
        taxonomy_id = 100  # Catholic

    source = f"mapping_saints_{ms['ms_id']}"

    db.execute("""
        INSERT INTO churches (id, name, landmark_type, faith, tradition,
            taxonomy_id, latitude, longitude, country, state, city,
            mapping_saints_id, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(new_id), ms["name"], landmark_type, faith, tradition,
        taxonomy_id, ms["lat"], ms["lon"], ms["country_iso"],
        ms["county"], ms["municipality"],
        str(ms["ms_id"]), source,
    ))
    new_created += 1

    if (i + 1) % 500 == 0:
        db.commit()
        print(f"  {progress_bar(i+1, len(new_unmatched))}  created: {new_created:,}", flush=True)

db.commit()
print(f"  New churches created: {new_created:,}")
print(f"\nNew church types:")
for pt, n in place_type_counts.most_common(15):
    print(f"  {pt:30s} {n:5,}")

# ── Provenance ──
db.execute("""
    INSERT INTO provenance_log (source, script_name, fields_populated, row_count, started_at, completed_at, status)
    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'), 'completed')
""", ("mapping_saints_merge", "merge_mapping_saints.py",
      f"Matched {total_matched} + created {new_created} new from Mapping Saints (3,773 medieval Nordic places)",
      total_matched + new_created))
db.commit()

# ── Summary ──
print(f"\n{'='*60}")
print(f"Mapping Saints Merge Complete")
print(f"  Total MS records:  {len(ms_records):,}")
print(f"  GPS matched:       {gps_hits:,}")
print(f"  Name matched:      {name_hits:,}")
print(f"  Total matched:     {total_matched:,}")
print(f"  New churches:      {new_created:,}")
print(f"  Unmatched:         {len(ms_records) - total_matched - new_created:,}")
print(f"  DB: {DB_PATH}")
db.close()

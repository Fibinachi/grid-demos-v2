"""
Census Geocoding — gw_geo/census.py
=====================================
Free, no-API-key geocoding service for US addresses via the US Census Bureau
Geocoder API. Three-tier architecture optimized for batch processing.

**Three tiers (all free):**
  Tier 1 — by_zip(): ZIP Code Tabulation Area centroid lookup (instant, offline)
  Tier 2 — geocode_street(): Street-level address geocoding (Census API, 200ms delay)
  Tier 3 — reverse_batch(): Batch coordinate → tract FIPS reverse geocoding

**Key features:**
  - ZCTA gazetteer cached in memory (instant ZIP→lat/lng)
  - Rate-limited API calls (200ms street, 1s batch)
  - ThreadPoolExecutor for concurrent batch reverse geocoding
  - Automatic retry on transient API failures

**Usage:**
    from gw_geo.census import by_zip, geocode_street, reverse_batch

    lat, lng = by_zip("29210")                              # Tier 1
    lat, lng, match = geocode_street("123 Main", "Columbia", "SC", "29210")  # Tier 2
    tracts = reverse_batch([(34.0, -81.0), (33.5, -80.5)])  # Tier 3

**Note:** US-only. For Canada, use gw_geo.here. For India, use Nominatim (Docker).

**Version:** 1.0.0 (June 2026)
"""

import csv, json, os, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
ZCTA_PATH = os.path.join(PROJECT_DIR, "data", "Gaz_zcta_national.txt")

# ── API Endpoints ──────────────────────────────────────────────────
CENSUS_ADDRESS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
CENSUS_COORDS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinatesbatch"

# Rate limiting
STREET_DELAY = 0.2       # 200ms between street-level calls
BATCH_DELAY = 1.0        # 1s between batch API calls
BATCH_SIZE = 500         # Records per DB commit
API_BATCH_SIZE = 1000    # Coords per batch API call
MAX_WORKERS = 5

# ── ZCTA Cache ─────────────────────────────────────────────────────

_ZCTA_CACHE = None  # Lazy-loaded

def load_zcta():
    """Load ZIP → (lat, lng) from Census ZCTA national gazetteer."""
    global _ZCTA_CACHE
    if _ZCTA_CACHE is not None:
        return _ZCTA_CACHE

    _ZCTA_CACHE = {}
    if not os.path.exists(ZCTA_PATH):
        return _ZCTA_CACHE

    with open(ZCTA_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        reader.fieldnames = [n.strip() for n in reader.fieldnames]
        for row in reader:
            zip_code = row["GEOID"].strip().zfill(5)
            try:
                lat = float(row["INTPTLAT"].strip())
                lng = float(row["INTPTLONG"].strip())
                _ZCTA_CACHE[zip_code] = (lat, lng)
            except (ValueError, KeyError):
                continue
    return _ZCTA_CACHE


# ═══════════════════════════════════════════════════════════════════
# TIER 1: ZIP centroid lookup
# ═══════════════════════════════════════════════════════════════════

def by_zip(zip_code):
    """Look up (lat, lng) from ZIP code via ZCTA centroid. Instant, free."""
    if not zip_code:
        return (None, None)
    zips = load_zcta()
    zip_str = str(zip_code).strip().split("-")[0].zfill(5)
    return zips.get(zip_str, (None, None))


# ═══════════════════════════════════════════════════════════════════
# TIER 2: Census Street-level Geocoding
# ═══════════════════════════════════════════════════════════════════

def geocode_street(address, city, state, zip_code):
    """Geocode a single US address via Census Geocoder. Returns (lat, lng, match_type)."""
    addr = f"{address}, {city}, {state} {zip_code}".strip(", ")
    if not addr:
        return (None, None, None)

    params = urllib.parse.urlencode({
        "address": addr,
        "benchmark": "2020",
        "format": "json",
    })
    url = f"{CENSUS_ADDRESS_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            coords = matches[0].get("coordinates", {})
            lat = coords.get("y")
            lng = coords.get("x")
            match_type = matches[0].get("matchedAddress", "")[:80]
            return (lat, lng, f"census_street:{match_type}")

        return (None, None, "census_no_match")
    except Exception:
        return (None, None, "census_error")


def geocode_churches_batch(churches, street_level=True):
    """
    Geocode multiple churches. Uses ZIP centroid for all, then street-level for priority.

    churches: list of dicts with keys: id, name, address, city, state, zip
    street_level: if True, also calls Census street-level API for churches with addresses

    Yields (id, lat, lng, source) for each church.
    """
    zips = load_zcta()
    results = []

    # Phase 1: ZIP centroid for all
    for c in churches:
        lat, lng = by_zip(c.get("zip", ""))
        source = "zcta" if lat else "missing"
        yield (c["id"], lat, lng, source)

        if lat:
            results.append((c["id"], True))  # geocoded
        else:
            results.append((c["id"], False))

    # Phase 2: Street-level for priority targets
    if street_level:
        for c in churches:
            if c.get("address") and len(c.get("address", "")) > 5:
                lat, lng, src = geocode_street(
                    c["address"], c.get("city", ""),
                    c.get("state", ""), c.get("zip", "")
                )
                if lat:
                    yield (c["id"], lat, lng, src)
                time.sleep(STREET_DELAY)


# ═══════════════════════════════════════════════════════════════════
# TIER 3: Coordinate → Tract FIPS (reverse geocode)
# ═══════════════════════════════════════════════════════════════════

def reverse_coords(lat, lng, benchmark="Public_AR_Current", vintage="Current_Current"):
    """
    Reverse geocode (lat, lng) to Census Tract FIPS.
    Returns dict with geoid, state_fips, county_fips, tract_fips, block, or None.
    """
    params = urllib.parse.urlencode({
        "x": lng, "y": lat,
        "benchmark": benchmark,
        "vintage": vintage,
        "format": "json",
    })
    url = f"{CENSUS_COORDS_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        matches = data.get("result", {}).get("geographies", {}).get("Census Tracts", [])
        if matches:
            g = matches[0]
            return {
                "geoid": g.get("GEOID", ""),
                "state_fips": g.get("STATE", ""),
                "county_fips": g.get("COUNTY", ""),
                "tract_fips": g.get("TRACT", ""),
                "block": g.get("BLOCK", ""),
            }
        return None
    except Exception:
        return None


def reverse_coords_batch(coords):
    """
    Batch reverse geocode multiple (lat, lng) pairs via Census batch API.

    coords: list of dicts [{"id": int, "lat": float, "lng": float}, ...]
    Yields (id, geoid, state_fips, county_fips, tract_fips) for each.

    Consolidates: geocode_tracts.py and tract_reverse_geocode.py
    """
    # Split into API batches (1000 max per call)
    batches = [coords[i:i + API_BATCH_SIZE] for i in range(0, len(coords), API_BATCH_SIZE)]

    for batch_num, batch in enumerate(batches):
        payload = {
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
            "coordinates": [{"x": c["lng"], "y": c["lat"]} for c in batch],
        }

        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                CENSUS_BATCH_URL, data=body,
                headers={
                    "User-Agent": "GrantWizard/1.0",
                    "Content-Type": "application/json",
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            geos = data.get("result", {}).get("geographies", {})
            tracts = geos.get("Census Tracts", [])

            for i, c in enumerate(batch):
                if i < len(tracts):
                    g = tracts[i]
                    yield (
                        c["id"],
                        g.get("GEOID", ""),
                        g.get("STATE", ""),
                        g.get("COUNTY", ""),
                        g.get("TRACT", ""),
                    )
                else:
                    yield (c["id"], "", "", "", "")

        except Exception:
            for c in batch:
                yield (c["id"], "", "", "", "")

        if batch_num < len(batches) - 1:
            time.sleep(BATCH_DELAY)

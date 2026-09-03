"""
Mapbox Geocoding API (~84K credits remaining)
===============================================
Consolidates: mapbox_geocode.py

Single entry point for Mapbox-based geocoding.
"""

import json, os, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Mapbox API key (must be set via environment variable)
MAPBOX_KEY = os.environ.get("MAPBOX_API_KEY", "")
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json?access_token={key}&limit=1&country=US"

MAX_WORKERS = 8
RATE_LIMIT = 0.1  # 100ms between calls (~10/sec, safe for free tier)

_stats = {"called": 0, "matched": 0, "errors": 0}
_stats_lock = __import__("threading").Lock()


def geocode(address=None, name=None, city=None, state=None, zip_code=None):
    """
    Geocode a church via Mapbox.
    Prefers street address, falls back to name+city+state.

    Returns (lat, lng, source) or (None, None, None).
    """
    # Build query
    if address and len(address) > 5:
        query = f"{address}, {city or ''}, {state or ''} {zip_code or ''}".strip()
    else:
        query = f"{name or ''}, {city or ''}, {state or ''}".strip()

    if not query or query.strip(",").strip() == "":
        return (None, None, None)

    url = GEOCODE_URL.format(
        query=urllib.parse.quote(query),
        key=MAPBOX_KEY
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        with _stats_lock:
            _stats["called"] += 1

        features = data.get("features", [])
        if features:
            center = features[0].get("center", [])
            if len(center) == 2:
                with _stats_lock:
                    _stats["matched"] += 1
                return (center[1], center[0], "mapbox_street")

        return (None, None, None)

    except Exception:
        with _stats_lock:
            _stats["errors"] += 1
        return (None, None, None)


def geocode_batch(churches, workers=MAX_WORKERS):
    """
    Geocode multiple churches in parallel via Mapbox.

    churches: list of dicts with keys: id, name, address, city, state, zip
    Yields (id, lat, lng, source) for each church.
    """
    def _geocode_one(c):
        result = geocode(
            address=c.get("address"),
            name=c.get("name"),
            city=c.get("city"),
            state=c.get("state"),
            zip_code=c.get("zip"),
        )
        return (c["id"], result[0], result[1], result[2])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_geocode_one, c) for c in churches]
        for f in as_completed(futures):
            yield f.result()


def stats():
    """Return current API call stats."""
    with _stats_lock:
        return dict(_stats)


REVERSE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{lon},{lat}.json?access_token={key}&types=address&limit=1"


def reverse(lat, lon):
    """
    Reverse geocode (lat, lon) -> US street address via Mapbox.

    Uses types=address so POI results (the church itself) are excluded and the
    nearest street address range is returned instead.

    Returns dict {street, city, state, postcode, place_name} or None.
      street = "123 Main St", state = 2-letter code (e.g. "SC").
    """
    if lat is None or lon is None:
        return None
    url = REVERSE_URL.format(lon=lon, lat=lat, key=MAPBOX_KEY)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        with _stats_lock:
            _stats["called"] += 1

        feats = data.get("features", [])
        if not feats:
            return None

        f = feats[0]
        road = (f.get("text") or "").strip()       # street name
        num = (f.get("address") or "").strip()     # house number
        street = f"{num} {road}".strip()

        city = state = postcode = ""
        for ctx in f.get("context", []):
            cid = ctx.get("id", "") or ""
            if cid.startswith("place"):
                city = ctx.get("text", "")
            elif cid.startswith("region"):
                sc = ctx.get("short_code", "") or ""
                state = sc.split("-")[-1]
            elif cid.startswith("postcode"):
                postcode = ctx.get("text", "")

        if not street and not city:
            return None

        with _stats_lock:
            _stats["matched"] += 1

        return {
            "street": street,
            "city": city,
            "state": state,
            "postcode": postcode,
            "place_name": f.get("place_name", ""),
        }
    except Exception:
        with _stats_lock:
            _stats["errors"] += 1
        return None


def reverse_batch(coords, workers=MAX_WORKERS):
    """
    Reverse geocode many (id, lat, lon) tuples in parallel.

    Yields (id, result_dict) where result_dict is reverse()'s dict or None.
    """
    def _one(item):
        cid, lat, lon = item
        return (cid, reverse(lat, lon))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, item) for item in coords]
        for fut in as_completed(futures):
            yield fut.result()

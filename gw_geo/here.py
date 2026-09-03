"""
HERE.com Geocoding & Places API (30K req/month budget)
========================================================
Consolidates: here_geocode.py

Manages quota tracking and three-phase enrichment:
  --missing    Geocode churches missing lat/lng
  --upgrade    Re-geocode ZIP-centroid → street-level (high-value only)
  --places     Look up website/phone via HERE Places API
"""

import json, os, time, urllib.request, urllib.parse
from datetime import date

# ── Config ─────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_FILE = os.path.join(PROJECT_DIR, "data", "here_api_key.json")
QUOTA_FILE = os.path.join(PROJECT_DIR, "data", "here_quota.json")

HERE_GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"
HERE_DISCOVER_URL = "https://discover.search.hereapi.com/v1/discover"

MAX_MONTHLY = 30000
RATE_LIMIT = 0.15  # ~6.5 req/sec

_seen_countries = set()  # Track unique countries for stats


def _load_api_key():
    key = os.environ.get("HERE_API_KEY", "")
    if key:
        return key
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE) as f:
            return json.load(f).get("here_api_key", "")
    return None


def _this_month():
    return date.today().isoformat()[:7]


def _load_quota():
    """Return calls used this month."""
    if not os.path.exists(QUOTA_FILE):
        return 0
    try:
        with open(QUOTA_FILE) as f:
            data = json.load(f)
        if data.get("month") == _this_month():
            return data.get("used", 0)
    except Exception:
        pass
    return 0


def _save_quota(used):
    """Persist monthly quota usage."""
    with open(QUOTA_FILE, "w") as f:
        json.dump({"month": _this_month(), "used": used}, f)


def quota_remaining():
    """Return remaining API calls this month."""
    return max(0, MAX_MONTHLY - _load_quota())


# ═══════════════════════════════════════════════════════════════════
# GEOCODING
# ═══════════════════════════════════════════════════════════════════

def geocode(query):
    """
    Geocode an address/query string via HERE Geocoding API.
    Returns (lat, lng, address, score) or (None, None, None, 0).
    Deducts from monthly quota automatically.
    """
    if _load_quota() >= MAX_MONTHLY:
        return (None, None, None, 0)

    result = _geocode(query)
    _save_quota(_load_quota() + 1)
    return result


def _geocode(query):
    """Internal: single geocode call with no quota check."""
    api_key = _load_api_key()
    if not api_key:
        return (None, None, None, 0)

    params = urllib.parse.urlencode({
        "q": query,
        "apiKey": api_key,
        "limit": 1,
    })
    url = f"{HERE_GEOCODE_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        items = data.get("items", [])
        if items:
            pos = items[0].get("position", {})
            addr = items[0].get("address", {})
            lat = pos.get("lat")
            lng = pos.get("lng")
            address = addr.get("label", "")
            score = items[0].get("scoring", {}).get("queryScore", 0)
            _seen_countries.add(addr.get("countryCode", ""))
            return (lat, lng, address, score)

        return (None, None, None, 0)
    except Exception:
        return (None, None, None, 0)


# ═══════════════════════════════════════════════════════════════════
# PLACES LOOKUP (website/phone)
# ═══════════════════════════════════════════════════════════════════

def discover_places(query, lat=None, lng=None):
    """
    Discover places via HERE Discover API.
    Returns list of dicts with name, website, phone, address.
    """
    api_key = _load_api_key()
    if not api_key or _load_quota() >= MAX_MONTHLY:
        return []

    params = {"q": query, "apiKey": api_key, "limit": 3}
    if lat is not None and lng is not None:
        params["at"] = f"{lat},{lng}"
    url = f"{HERE_DISCOVER_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in data.get("items", []):
            results.append({
                "name": item.get("title", ""),
                "website": item.get("contacts", [{}])[0].get("www", [{}])[0].get("value", ""),
                "phone": (
                    item.get("contacts", [{}])[0].get("phone", [{}])[0].get("value", "")
                    if item.get("contacts") else ""
                ),
                "address": item.get("address", {}).get("label", ""),
            })

        _save_quota(_load_quota() + 1)
        return results
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════
# BATCH HELPERS
# ═══════════════════════════════════════════════════════════════════

def geocode_batch(queries, on_result=None):
    """
    Geocode multiple queries with rate limiting and quota tracking.

    queries: list of (id, query_string)
    on_result: optional callback(id, lat, lng, address, score)
    Yields (id, lat, lng, address, score) for each.
    """
    for qid, query in queries:
        lat, lng, addr, score = geocode(query)
        if on_result:
            on_result(qid, lat, lng, addr, score)
        yield (qid, lat, lng, addr, score)
        time.sleep(RATE_LIMIT)

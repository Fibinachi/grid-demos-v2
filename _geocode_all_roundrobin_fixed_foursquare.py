"""_geocode_all_roundrobin.py — Multi-provider live Nominatim backfill (3x speed).

Same pipeline as _geocode_all_live.py but runs ONE WORKER THREAD PER PROVIDER in
round-robin, so we can poll 3 public geocoders concurrently while keeping each
provider within its own 1 req/s policy:

    provider A  nominatim.openstreetmap.org   (Nominatim JSON, 1 req/s)
    provider B  nominatim.geocoding.ai        (Nominatim JSON, 1 req/s)
    provider C  photon.komoot.io              (Photon JSON,   1 req/s)

Order (2026-08-18): FORWARD name search FIRST (tight 0.5 km box) THEN the
reverse hunt ALWAYS runs for every site (cross-check + gap fill) -> loose 2 km
name search last. The forward pass returns the church POI's OWN address AND its
precise POI coordinates (more accurate than the stored GPS); reverse describes
the actual point (house-numbered street/city/postcode) and fills any gaps the
forward pass left. Forward winners logged as osm_search / photon_search. When a
forward search wins, the church's lat/lon is upgraded to the POI point (only if
the move stays within the tight 0.5 km box) and logged as geocode_precision.

Each site: input -> provider reverse -> result -> post to churches.db
(set_components + geocode_source + nominatim_geocode_log + change log)
-> live globe (data/live_map/points.jsonl).

Skips any site already checked on Nominatim within SKIP_MONTHS (default 6),
matching the month-level cutoff of scripts/enrichment/reverse_geocode_nominatim.py.

Usage:
  python _geocode_all_roundrobin.py                  # full backlog, 3 providers
  python _geocode_all_roundrobin.py --limit 30       # test 30
  python _geocode_all_roundrobin.py --dry-run        # count + sample only
  python _geocode_all_roundrobin.py --random 500     # 500 random un-geocoded sites
  python _geocode_all_roundrobin.py --providers osm,geocoding.ai   # subset
"""
import calendar
import json
import math
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from queue import Queue

# non-Latin names in per-entry logs must not crash under cp1252 redirects (Tee)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r"E:\grid")
from scripts.grid_address import set_components  # noqa: E402
from scripts.enrichment.llm_translate import (  # noqa: E402
    is_non_latin, needs_translation, translate_names, apply_name_translations,
    apply_address_translations)

DB = "E:/grid/churches.db"
LIVE_STREAM = "E:/grid/data/live_map/points.jsonl"
RATE_DELAY = 1.1  # per-provider policy: ~0.9 req/s (reduced from 2.0 to speed up)
SOURCE = "nominatim_live_all_2026"
UA = "GRID/1.0 (https://github.com/grid; academic research; contact charles@gridataset.com)"
# geocode.maps.co free plan: 25K @ 5 req/s then 1 req/s. We run it at 1 req/s.
GEOMAPCO_KEY = os.environ.get("GEOMAPCO_API_KEY", "")
# geocode.earth (Pelias) - used ONLY as a failover when a primary provider
# errors out or returns no street (saves quota: fires only on misses).
EARTH_KEY = os.environ.get("GEOCODE_EARTH_API_KEY", "")
# ReportAll (US parcel data) - final US-only failover for parcel-grade addresses.
REPORTALL_KEY = os.environ.get("REPORTALL_CLIENT_KEY", "")
# TAMU Geoservices reverse geocoder - US-only fallback (free account).
# DISABLED 2026-08-17: (a) US-only while the backlog run is international,
# (b) free quota exhausted (QuotaExceededError even on US coords). Set to a
# valid key to re-enable.
TAMU_KEY = os.environ.get("TAMU_API_KEY", "")
# TomTom reverse geocoder - global fallback (free tier 20K requests/month).
TOMTOM_KEY = os.environ.get("TOMTOM_API_KEY", "")
# Mapbox reverse geocoder - global backup (free tier ~100K credits/month).
MAPBOX_KEY = os.environ.get("MAPBOX_API_KEY", "")
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
# Ambee (global geocoder) - absolute last resort, hard-capped at 100 calls/day.
AMBEE_KEY = os.environ.get("AMBEE_API_KEY", "")
# Foursquare Places API - first-attempt forward geocoder (free tier, no 1 req/s cap).
FOURSQUARE_KEY = os.environ.get("FOURSQUARE_API_KEY", "")
# ChibiGeo (hosted Photon-compatible service, app.chibigeo.com/v1/photon) -
# reverse + forward provider. 2500 requests/day. Key from env var only.
CHIBIGEO_KEY = os.environ.get("CHIBIGEO_API_KEY", "")
# Geocodio (US/CA forward + reverse, data enrichment) - 2,500 requests/day
GEOCODIO_KEY = os.environ.get("GEOCODIO_API_KEY", "")
# LocationIQ (Nominatim-compatible, global forward + reverse) - 5,000 requests/day
LOCATIONIQ_KEY = os.environ.get("LOCATIONIQ_API_KEY", "")
AMBEE_DAILY = 100
AMBEE_QUOTA_FILE = "E:/grid/data/staging/ambee_quota.json"
_ambee_q_lock = threading.Lock()


def ambee_quota_take():
    """Atomically check + consume one Ambee daily call (persistent across restarts)."""
    with _ambee_q_lock:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        used = 0
        try:
            with open(AMBEE_QUOTA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("date") == today:
                used = d.get("used", 0)
        except Exception:
            pass
        if used >= AMBEE_DAILY:
            return False
        os.makedirs(os.path.dirname(AMBEE_QUOTA_FILE), exist_ok=True)
        with open(AMBEE_QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today, "used": used + 1}, f)
        return True

CHIBIGEO_DAILY = 2500
CHIBIGEO_QUOTA_FILE = "E:/grid/data/staging/chibigeo_quota.json"
_chibigeo_q_lock = threading.Lock()
_CHIBIGEO_LOCK = threading.Lock()
_CHIBIGEO_ERRS = 0
_CHIBIGEO_DISABLED = False


def chibigeo_quota_take():
    """Atomically check + consume one ChibiGeo daily call (persistent across
    restarts; daily limit is 2500)."""
    with _chibigeo_q_lock:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        used = 0
        try:
            with open(CHIBIGEO_QUOTA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("date") == today:
                used = d.get("used", 0)
        except Exception:
            pass
        if used >= CHIBIGEO_DAILY:
            return False
        os.makedirs(os.path.dirname(CHIBIGEO_QUOTA_FILE), exist_ok=True)
        with open(CHIBIGEO_QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today, "used": used + 1}, f)
        return True

GEOCODIO_DAILY = 2500
GEOCODIO_QUOTA_FILE = "E:/grid/data/staging/geocodio_quota.json"
_geocodio_q_lock = threading.Lock()
_GEOCODIO_LOCK = threading.Lock()
_GEOCODIO_ERRS = 0
_GEOCODIO_DISABLED = False


def geocodio_quota_take():
    """Atomically check + consume one Geocodio daily call (persistent across
    restarts; daily limit is 2500)."""
    with _geocodio_q_lock:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        used = 0
        try:
            with open(GEOCODIO_QUOTA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("date") == today:
                used = d.get("used", 0)
        except Exception:
            pass
        if used >= GEOCODIO_DAILY:
            return False
        os.makedirs(os.path.dirname(GEOCODIO_QUOTA_FILE), exist_ok=True)
        with open(GEOCODIO_QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today, "used": used + 1}, f)
        return True

LOCATIONIQ_DAILY = 5000
LOCATIONIQ_QUOTA_FILE = "E:/grid/data/staging/locationiq_quota.json"
_locationiq_q_lock = threading.Lock()
_LOCATIONIQ_LOCK = threading.Lock()
_LOCATIONIQ_ERRS = 0
_LOCATIONIQ_DISABLED = False


def locationiq_quota_take():
    """Atomically check + consume one LocationIQ daily call (persistent across
    restarts; daily limit is 5000)."""
    with _locationiq_q_lock:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        used = 0
        try:
            with open(LOCATIONIQ_QUOTA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("date") == today:
                used = d.get("used", 0)
        except Exception:
            pass
        if used >= LOCATIONIQ_DAILY:
            return False
        os.makedirs(os.path.dirname(LOCATIONIQ_QUOTA_FILE), exist_ok=True)
        with open(LOCATIONIQ_QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today, "used": used + 1}, f)
        return True

DRY_RUN = "--dry-run" in sys.argv
LIMIT = None
RANDOM_N = None
RANDOMIZE_ALL = False
SKIP_MONTHS = 6
PROVIDER_ARG = None
IDS_FILE = None
SOURCE_ARG = None
# integrated LLM name translation: geocode+store -> fallbacks+store -> translate+store
TRANSLATE = "--no-translate" not in sys.argv
CENSUS_ENABLED = "--no-census" not in sys.argv
TR_PROVIDER = "gemini"   # gemini | groq
TR_BATCH = 100
TR_MODEL = os.environ.get("GEMINI_MODEL", "")
for i, a in enumerate(sys.argv):
    if a.startswith("--limit="):
        LIMIT = int(a.split("=")[1])
    elif a == "--limit" and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])
    if a.startswith("--random="):
        RANDOM_N = int(a.split("=")[1])
    elif a == "--random" and i + 1 < len(sys.argv):
        RANDOM_N = int(sys.argv[i + 1])
    if a == "--randomize":
        RANDOMIZE_ALL = True
    if a.startswith("--skip-months="):
        SKIP_MONTHS = int(a.split("=")[1])
    if a.startswith("--providers="):
        PROVIDER_ARG = [x.strip() for x in a.split("=")[1].split(",") if x.strip()]
    if a.startswith("--translate-provider="):
        TR_PROVIDER = a.split("=")[1]
    if a.startswith("--translate-batch="):
        TR_BATCH = int(a.split("=")[1])
    if a.startswith("--ids-file="):
        IDS_FILE = a.split("=", 1)[1]
    elif a == "--ids-file" and i + 1 < len(sys.argv):
        IDS_FILE = sys.argv[i + 1]
    if a.startswith("--source="):
        SOURCE_ARG = a.split("=", 1)[1]
    elif a == "--source" and i + 1 < len(sys.argv):
        SOURCE_ARG = sys.argv[i + 1]
if SOURCE_ARG:
    SOURCE = SOURCE_ARG

ALL_PROVIDERS = [
    {"name": "osm", "url": "https://nominatim.openstreetmap.org/reverse", "kind": "nominatim"},
    {"name": "geocoding.ai", "url": "https://nominatim.geocoding.ai/reverse", "kind": "nominatim"},
    {"name": "photon", "url": "https://photon.komoot.io/reverse", "kind": "photon"},
    {"name": "geocode.maps.co", "url": "https://geocode.maps.co/reverse", "kind": "mapsco"},
    # TAMU REMOVED from primary providers 2026-08-17: it is US-only (this run is
    # international) and its free quota is exhausted (QuotaExceededError even on
    # US coords). As a primary provider its worker thread called reverse_tamu on
    # EVERY site with no country guard. Kept only as a US-guarded failover below,
    # and TAMU_KEY="" disables that too. Re-add only with a valid key + the guard
    # `country == "US"` applied in the worker.
]
if PROVIDER_ARG:
    PROVIDERS = [p for p in ALL_PROVIDERS if p["name"] in PROVIDER_ARG]
else:
    PROVIDERS = ALL_PROVIDERS
if not PROVIDERS:
    print("[FAIL] no providers selected")
    sys.exit(1)


class RateLimiter:
    """Per-provider rate limiter: guarantees >= delay seconds between requests,
    safe to share across threads (so cross-provider retries still respect
    each provider's own 1 req/s policy)."""

    def __init__(self, delay):
        self.delay = delay
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self):
        with self.lock:
            now = time.time()
            w = self.next_at - now
            if w > 0:
                time.sleep(w)
            self.next_at = max(now, self.next_at) + self.delay

    def backoff(self, factor=2.0, cap=60.0):
        """Permanently increase this provider's request spacing after a
        rate-limit / backoff hit. Never lowers back -- once throttled, stay
        throttled for the rest of the run, so a 429-prone host is not
        hammered again at its base rate."""
        with self.lock:
            self.delay = min(cap, self.delay * factor)


# Limiters are attached to ALL providers (not just the selected subset), so
# the forward-search lookups below always find them even when --providers
# excludes a host (e.g. running osm-free alongside the UK Nominatim batch).
for _p in ALL_PROVIDERS:
    # geocode.maps.co is strict (429s if pushed) - give it a 2.0 s policy;
    # others share RATE_DELAY. (name is "geocode.maps.co", not "mapsco")
    _p["limiter"] = RateLimiter(2.0) if _p["name"] == "geocode.maps.co" else RateLimiter(RATE_DELAY)
EARTH_LIMITER = RateLimiter(RATE_DELAY)
REPORTALL_LIMITER = RateLimiter(2.0)
TAMU_LIMITER = RateLimiter(RATE_DELAY)
TOMTOM_LIMITER = RateLimiter(RATE_DELAY)
MAPBOX_LIMITER = RateLimiter(RATE_DELAY)
AMBEE_LIMITER = RateLimiter(RATE_DELAY)
# Forward name-search shares the SAME per-provider rate budget as the reverse
# calls (a second independent limiter could exceed 1 req/s on the shared host).
_OSM_LIMITER = next(p["limiter"] for p in ALL_PROVIDERS if p["name"] == "osm")
_PHOTON_LIMITER = next(p["limiter"] for p in ALL_PROVIDERS if p["name"] == "photon")
# Additional forward-search providers (2026-08-18). Each has its OWN limiter
# because they are independent hosts (no shared-host 1 req/s policy):
#   - mapsco: geocode.maps.co is a separate host from OSM; 1 req/s policy on
#     its own domain.
#   - mapbox: free tier ~600/min -> 0.1 s spacing is plenty safe.
#   - earth:  geocode.earth (Pelias) quota'd -> keep 1 req/s.
#   - ban:    BAN France is free and has no documented rate cap; be polite at
#             0.25 s (4 req/s).
#   - chibigeo: independent host, 1 req/s budget
#   - geocodio: US/CA only, 1 req/s budget
#   - locationiq: Nominatim-compatible, 1 req/s budget
_MAPSCO_FWD_LIMITER = RateLimiter(2.0)
_MAPBOX_FWD_LIMITER = RateLimiter(0.1)
_EARTH_FWD_LIMITER = RateLimiter(1.0)
_BAN_FWD_LIMITER = RateLimiter(0.25)
# ChibiGeo is an independent host (not OSM) - its own 1 req/s rate budget.
_CHIBIGEO_LIMITER = RateLimiter(1.0)
# Geocodio is US/CA only, 1 req/s budget
_GEOCODIO_LIMITER = RateLimiter(1.0)
# LocationIQ is Nominatim-compatible, 1 req/s budget
_LOCATIONIQ_LIMITER = RateLimiter(1.0)
# ChibiGeo is an independent host (not OSM) - its own 1 req/s rate budget.
_CHIBIGEO_LIMITER = RateLimiter(1.0)
_FOURSQUARE_FWD_LIMITER = RateLimiter(0.1)  # no documented cap; keep a polite 10 req/s ceiling
# Foursquare circuit breaker: paid/quota'd API (freePro tier). Once it runs out
# of credits it 429s with "no API credits remaining" for the WHOLE run, so stop
# calling it after a few quota errors instead of wasting a request per church.
_FSQ_LOCK = threading.Lock()
_FSQ_FAILS = 0
_FSQ_DISABLED = False
_FSQ_DISABLE_AFTER = 3
# VK Maps Overpass mirror (maps.mail.ru) - public OSM Overpass API; be polite at
# 1 req/s since it is a shared public mirror.
_VK_FWD_LIMITER = RateLimiter(1.0)
# VK circuit breaker: the public mirror 504s (gateway timeout) frequently on
# name-regex radius queries. Disable after a few consecutive failures so it
# can't spam the log for every church.
_VK_LOCK = threading.Lock()
_VK_FAILS = 0
_VK_DISABLED = False
_VK_DISABLE_AFTER = 3

# ── geocode.earth circuit breaker ─────────────────────────────────────
# geocode.earth (Pelias) is a quota'd provider used ONLY as failover. Its free
# tier is small, so once it starts returning 429 we stop calling it for the
# rest of the run instead of burning requests + spamming the log.
EARTH_LOCK = threading.Lock()
EARTH_429S = 0
EARTH_DISABLED = False
EARTH_DISABLE_AFTER = 5  # consecutive 429s before we cut it off

# ── geocode.maps.co circuit breaker ──────────────────────────────────
# geocode.maps.co free plan 429s hard once its quota is hit; disable after
# repeated 429s (covers forward name-search + reverse calls).
MAPSCO_LOCK = threading.Lock()
MAPSCO_429S = 0
MAPSCO_DISABLED = False
MAPSCO_DISABLE_AFTER = 5

# ── tomtom circuit breaker ────────────────────────────────────────────
# TomTom is a global fallback. A 401/403 from TomTom means the API key is
# invalid/expired/blocked (NOT a transient rate limit) — it will NEVER
# succeed again this run, so cut it off after the FIRST auth failure instead
# of burning a request per site and spamming the log.
TOMTOM_LOCK = threading.Lock()
TOMTOM_AUTH_FAILS = 0
TOMTOM_DISABLED = False
TOMTOM_DISABLE_AFTER = 1  # one 401/403 is enough — key is bad

# ── tamu circuit breaker ──────────────────────────────────────────────
# TAMU Geoservices (US reverse fallback) returns statusCode 470
# QuotaExceededError once its free monthly quota is gone — it will not
# recover this run, so cut it off instead of burning a request per site.
TAMU_LOCK = threading.Lock()
TAMU_QUOTA_FAILS = 0
TAMU_DISABLED = False
TAMU_DISABLE_AFTER = 2  # a couple of confirmations before cutting off


def provider_call(prov, lat, lon):
    prov["limiter"].wait()
    return provider_reverse(prov, lat, lon)


def earth_call(lat, lon):
    if EARTH_DISABLED:
        return None
    EARTH_LIMITER.wait()
    return reverse_geocode_earth(lat, lon)



def reportall_call(lat, lon):
    REPORTALL_LIMITER.wait()
    return reverse_reportall(lat, lon)


def tamu_call(lat, lon):
    if TAMU_DISABLED:
        return None
    TAMU_LIMITER.wait()
    return reverse_tamu(lat, lon)

def tomtom_call(lat, lon):
    if TOMTOM_DISABLED:
        return None
    TOMTOM_LIMITER.wait()
    return reverse_tomtom(lat, lon)


def mapbox_call(lat, lon):
    MAPBOX_LIMITER.wait()
    return reverse_mapbox(lat, lon)


def ambee_call(lat, lon):
    AMBEE_LIMITER.wait()
    return reverse_ambee(lat, lon)


def cutoff_month():
    now = datetime.now(timezone.utc)
    m = now.month - SKIP_MONTHS
    y = now.year
    while m < 1:
        m += 12
        y -= 1
    return f"{y}-{m:02d}-01"


def build_street(addr):
    parts = []
    hn = addr.get("house_number", "")
    road = (addr.get("road") or addr.get("pedestrian") or
            addr.get("footway") or addr.get("path") or "")
    if hn and road:
        parts.append(f"{hn} {road}")
    elif road:
        parts.append(road)
    nb = addr.get("neighbourhood") or addr.get("suburb") or addr.get("quarter") or ""
    if nb and nb != road:
        parts.append(nb)
    return ", ".join(parts) if parts else ""


def extract_city(addr):
    raw = (addr.get("city") or addr.get("town") or addr.get("village") or
           addr.get("hamlet") or addr.get("municipality") or
           addr.get("suburb") or "")
    if not raw:
        return ""
    if re.search(r"&#\d+;|&#x[0-9a-f]+;|&lt;|&gt;|&amp;|&quot;", raw):
        return ""
    try:
        raw = unescape(raw)
    except Exception:
        pass
    raw = raw.strip()
    if not raw:
        return ""
    if re.search(r"[\u00b0\u2032\u2033]", raw):
        return ""
    if len(raw) > 80 or raw.count(",") >= 3:
        return ""
    if re.search(r"\b(is one|is a|located in|directly subject|under the)\b", raw, re.IGNORECASE):
        return ""
    return raw


NUMBERED_STREET_RE = re.compile(r"^\s*\d+[A-Za-z]?\s+\S")


def numbered_street(r):
    """True when the result carries a proper, building-level street address --
    a house number followed by a street name (e.g. '123 Main St'), as opposed
    to a bare street name ('Main St') that can't locate a building. The hunt
    keeps rolling through providers until this is found."""
    if not r or not r.get("street"):
        return False
    return bool(NUMBERED_STREET_RE.match(r.get("street") or ""))


def reverse_nominatim(url, lat, lon):
    u = url + "?" + urllib.parse.urlencode({
        "lat": lat, "lon": lon, "format": "json", "addressdetails": 1, "accept-language": "en"})
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        addr = data.get("address", {})
        return {
            "street": build_street(addr),
            "city": extract_city(addr),
            "state": (addr.get("state") or addr.get("province") or
                      addr.get("region") or addr.get("state_district") or ""),
            "postcode": addr.get("postcode", ""),
            "country": addr.get("country", ""),
            "nom_lat": float(data.get("lat", lat)),
            "nom_lon": float(data.get("lon", lon)),
        }
    except Exception as e:
        print(f"\n  [WARN] {url} error for {lat},{lon}: {e}")
        return None


def reverse_photon(lat, lon):
    u = "https://photon.komoot.io/reverse?" + urllib.parse.urlencode({"lon": lon, "lat": lat})
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        feats = data.get("features") or []
        if not feats:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        p = feats[0].get("properties") or {}
        geom = feats[0].get("geometry") or {}
        coords = geom.get("coordinates") or []
        hn = p.get("housenumber") or ""
        st = p.get("street") or ""
        street = f"{hn} {st}".strip() if (hn or st) else (p.get("name") or "")
        return {
            "street": street,
            "city": p.get("city") or p.get("locality") or p.get("district") or "",
            "state": p.get("state") or "",
            "postcode": p.get("postcode") or "",
            "country": p.get("country") or "",
            "nom_lat": coords[1] if len(coords) > 1 else lat,
            "nom_lon": coords[0] if coords else lon,
        }
    except Exception as e:
        print(f"\n  [WARN] photon error for {lat},{lon}: {e}")
        return None


def reverse_chibigeo(lat, lon):
    """Reverse geocode via ChibiGeo (Photon-compatible, key on hand,
    independent host). Mirrors reverse_photon but appends the API key and uses
    its own rate limiter + quota/circuit-breaker guards."""
    global _CHIBIGEO_ERRS, _CHIBIGEO_DISABLED
    if not CHIBIGEO_KEY or _CHIBIGEO_DISABLED:
        return None
    u = ("https://app.chibigeo.com/v1/photon/reverse?" + urllib.parse.urlencode(
        {"lon": lon, "lat": lat}))
    _CHIBIGEO_LIMITER.wait()
    try:
        req = urllib.request.Request(
            u, headers={"User-Agent": UA, "X-Api-Key": CHIBIGEO_KEY})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        feats = data.get("features") or []
        if not feats:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        p = feats[0].get("properties") or {}
        geom = feats[0].get("geometry") or {}
        coords = geom.get("coordinates") or []
        hn = p.get("housenumber") or ""
        st = p.get("street") or ""
        street = f"{hn} {st}".strip() if (hn or st) else (p.get("name") or "")
        return {
            "street": street,
            "city": p.get("city") or p.get("locality") or p.get("district") or "",
            "state": p.get("state") or "",
            "postcode": p.get("postcode") or "",
            "country": p.get("country") or "",
            "nom_lat": coords[1] if len(coords) > 1 else lat,
            "nom_lon": coords[0] if coords else lon,
        }
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 402, 429):
            with _CHIBIGEO_LOCK:
                _CHIBIGEO_ERRS += 1
                if _CHIBIGEO_ERRS >= 2:
                    _CHIBIGEO_DISABLED = True
                    print(f"\n  [WARN] chibigeo auth/quota failure "
                          f"({e.code}) - DISABLED for rest of run")
        else:
            print(f"\n  [WARN] chibigeo HTTP {e.code} for {lat},{lon}")
        return None
    except Exception as e:
        print(f"\n  [WARN] chibigeo error for {lat},{lon}: {e}")
        return None


def reverse_geocodio(lat, lon):
    """Reverse geocode via Geocodio (US/CA, batch-capable, data enrichment).
    Mirrors reverse_photon but uses Geocodio's API (api.geocod.io) with key.
    Returns the standard result dict or None."""
    global _GEOCODIO_ERRS, _GEOCODIO_DISABLED
    if not GEOCODIO_KEY or _GEOCODIO_DISABLED:
        return None
    u = ("https://api.geocod.io/v1/reverse?" + urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "api_key": GEOCODIO_KEY}))
    _GEOCODIO_LIMITER.wait()
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        # Geocodio returns {\"results\": [{"address_components": {...}, ...}]}
        feats = data.get("results") or []
        if not feats:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        p = feats[0].get("address_components") or {}
        # Geocodio uses \"street_number\" + \"street_name\" + \"street_suffix\"
        hn = p.get("street_number") or ""
        st = p.get("street_name") or ""
        suf = p.get("street_suffix") or ""
        street = f"{hn} {st} {suf}".strip() if (hn or st or suf) else ""
        return {
            "street": street,
            "city": p.get("city") or p.get("locality") or "",
            "state": p.get("state") or p.get("region") or "",
            "postcode": p.get("postal_code") or "",
            "country": p.get("country") or "",
            "nom_lat": float(p.get("latitude") or lat),
            "nom_lon": float(p.get("longitude") or lon),
        }
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 402, 429):
            with _GEOCODIO_LOCK:
                _GEOCODIO_ERRS += 1
                if _GEOCODIO_ERRS >= 2:
                    _GEOCODIO_DISABLED = True
                    print(f"\n  [WARN] geocodio auth/quota failure "
                          f"({e.code}) - DISABLED for rest of run")
        else:
            print(f"\n  [WARN] geocodio HTTP {e.code} for {lat},{lon}")
        return None
    except Exception as e:
        print(f"\n  [WARN] geocodio error for {lat},{lon}: {e}")
        return None


def reverse_locationiq(lat, lon):
    """Reverse geocode via LocationIQ (Nominatim-compatible, global).
    Mirrors reverse_photon but uses LocationIQ's API (us1.locationiq.com).
    Returns the standard result dict or None."""
    global _LOCATIONIQ_ERRS, _LOCATIONIQ_DISABLED
    if not LOCATIONIQ_KEY or _LOCATIONIQ_DISABLED:
        return None
    u = ("https://us1.locationiq.com/v1/reverse?" + urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "key": LOCATIONIQ_KEY}))
    _LOCATIONIQ_LIMITER.wait()
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        feats = data.get("features") or []
        if not feats:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        p = feats[0].get("properties") or {}
        geom = feats[0].get("geometry") or {}
        coords = geom.get("coordinates") or []
        hn = p.get("housenumber") or ""
        st = p.get("street") or ""
        street = f"{hn} {st}".strip() if (hn or st) else (p.get("name") or "")
        return {
            "street": street,
            "city": p.get("city") or p.get("locality") or p.get("district") or "",
            "state": p.get("state") or "",
            "postcode": p.get("postcode") or "",
            "country": p.get("country") or "",
            "nom_lat": coords[1] if len(coords) > 1 else lat,
            "nom_lon": coords[0] if coords else lon,
        }
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 402, 429):
            with _LOCATIONIQ_LOCK:
                _LOCATIONIQ_ERRS += 1
                if _LOCATIONIQ_ERRS >= 2:
                    _LOCATIONIQ_DISABLED = True
                    print(f"\n  [WARN] locationiq auth/quota failure "
                          f"({e.code}) - DISABLED for rest of run")
        else:
            print(f"\n  [WARN] locationiq HTTP {e.code} for {lat},{lon}")
        return None
    except Exception as e:
        print(f"\n  [WARN] locationiq error for {lat},{lon}: {e}")
        return None


def reverse_mapsco(lat, lon):
    global MAPSCO_429S, MAPSCO_DISABLED
    if MAPSCO_DISABLED:
        return None
    u = "https://geocode.maps.co/reverse?" + urllib.parse.urlencode({
        "lat": lat, "lon": lon, "api_key": GEOMAPCO_KEY})
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        if "error" in data or "address" not in data:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        addr = data.get("address", {})
        return {
            "street": build_street(addr),
            "city": extract_city(addr),
            "state": (addr.get("state") or addr.get("province") or
                      addr.get("region") or addr.get("state_district") or ""),
            "postcode": addr.get("postcode", ""),
            "country": addr.get("country", ""),
            "nom_lat": float(data.get("lat", lat)),
            "nom_lon": float(data.get("lon", lon)),
        }
    except urllib.error.HTTPError as e:
        if e.code == 429:
            with MAPSCO_LOCK:
                MAPSCO_429S += 1
                if MAPSCO_429S >= MAPSCO_DISABLE_AFTER:
                    MAPSCO_DISABLED = True
                    print(f"\n  [WARN] geocode.maps.co rate-limited "
                          f"({MAPSCO_429S}x HTTP 429) - DISABLED for rest of run")
        else:
            print(f"\n  [WARN] geocode.maps.co HTTP {e.code} for {lat},{lon}")
        return None
    except Exception as e:
        print(f"\n  [WARN] geocode.maps.co error for {lat},{lon}: {e}")
        return None


def provider_reverse(prov, lat, lon):
    if prov["kind"] == "nominatim":
        return reverse_nominatim(prov["url"], lat, lon)
    if prov["kind"] == "mapsco":
        return reverse_mapsco(lat, lon)
    if prov["kind"] == "tamu":
        return reverse_tamu(lat, lon)
    if prov["kind"] == "chibigeo":
        return reverse_chibigeo(lat, lon)
    if prov["kind"] == "geocodio":
        return reverse_geocodio(lat, lon)
    if prov["kind"] == "locationiq":
        return reverse_locationiq(lat, lon)
    return reverse_photon(lat, lon)


_progress_open = False  # True while the \r progress line is still on-screen


def print_entry(chid, name, lat, lon, res, winner, status):
    """Live per-entry status line on the geocoder task:
    input (id | name | coords) -> output (resolved address | winning provider).
    Closes any in-progress \r progress line first so the two never collide."""
    global _progress_open
    if _progress_open:
        print()
        _progress_open = False

    def fc(v):
        try:
            return f"{float(v):.5f}"
        except (TypeError, ValueError):
            return str(v or "")

    inp = f"{chid} | {name or '?'} | {fc(lat)},{fc(lon)}"
    if status == "success" and res:
        addr = ", ".join(x for x in (res.get("street"), res.get("city"),
                                     res.get("state"), res.get("postcode"),
                                     res.get("country")) if x)
        print(f"[OK] {inp} -> {addr} ({winner})")
    elif status == "wrong_gps" and res:
        addr = ", ".join(x for x in (res.get("street"), res.get("city"),
                                     res.get("state")) if x)
        print(f"[WARN] {inp} -> {addr} ({winner}) — name-street mismatch, NOT written")
    elif status == "skip_complete":
        print(f"[SKIP] {inp} -> complete authoritative address (not overwritten)")
    elif status == "no_result":
        print(f"[NO] {inp} -> no address")
    else:
        print(f"[ERR] {inp} -> {status}")


def feed_live(church_id, name, lat, lon, res, status, tag, src=None, eng=None):
    os.makedirs(os.path.dirname(LIVE_STREAM), exist_ok=True)
    rec = {
        "id": church_id,
        "name": (name or "")[:80],
        "eng": (eng or "")[:80],
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "street": (res or {}).get("street", "") if res else "",
        "city": (res or {}).get("city", "") if res else "",
        "state": (res or {}).get("state", "") if res else "",
        "postcode": (res or {}).get("postcode", "") if res else "",
        "country": (res or {}).get("country", "") if res else "",
        "status": status,
        "tag": tag,
        "src": src,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with open(LIVE_STREAM, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def flash_live(church_id, name, translation, src):
    """Emit a translation-flash event to the globe stream (dot lights up +
    change-feed line)."""
    os.makedirs(os.path.dirname(LIVE_STREAM), exist_ok=True)
    rec = {"id": church_id, "flash": True, "field": "name_english",
           "name": (name or "")[:80], "value": (translation or "")[:120],
           "src": src, "ts": datetime.now(timezone.utc).isoformat()}
    with open(LIVE_STREAM, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def flash_addr_live(church_id, comps, src):
    """Emit an address-translation flash carrying the English street/city/state
    so the globe can update the dot's tooltip in place."""
    os.makedirs(os.path.dirname(LIVE_STREAM), exist_ok=True)
    rec = {"id": church_id, "flash": True, "field": "address",
           "street_en": (comps.get("street") or "")[:80],
           "city_en": (comps.get("city") or "")[:80],
           "state_en": (comps.get("state") or "")[:80],
           "src": src, "ts": datetime.now(timezone.utc).isoformat()}
    with open(LIVE_STREAM, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def reverse_geocode_earth(lat, lon):
    global EARTH_429S, EARTH_DISABLED
    u = "https://api.geocode.earth/v1/reverse?" + urllib.parse.urlencode({
        "point.lat": lat, "point.lon": lon, "api_key": EARTH_KEY, "size": 1})
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        feats = data.get("features") or []
        if not feats:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        p = feats[0].get("properties") or {}
        hn = p.get("housenumber") or ""
        st = p.get("street") or ""
        street = f"{hn} {st}".strip() if (hn or st) else ""
        return {
            "street": street,
            "city": p.get("locality") or "",
            "state": p.get("region") or "",
            "postcode": p.get("postalcode") or "",
            "country": p.get("country") or "",
            "nom_lat": lat, "nom_lon": lon,
        }
    except urllib.error.HTTPError as e:
        if e.code == 429:
            with EARTH_LOCK:
                EARTH_429S += 1
                if EARTH_429S == EARTH_DISABLE_AFTER:
                    EARTH_DISABLED = True
                    print(f"\n  [WARN] geocode.earth rate-limited "
                          f"({EARTH_429S}x HTTP 429) - DISABLED for rest of run")
        else:
            print(f"\n  [WARN] geocode.earth HTTP {e.code} for {lat},{lon}")
        return None
    except Exception as e:
        print(f"\n  [WARN] geocode.earth error for {lat},{lon}: {e}")
        return None


def reverse_reportall(lat, lon):
    u = ("https://reportallusa.com/api/parcels?v=9&client=" + urllib.parse.quote(REPORTALL_KEY)
         + "&spatial_intersect=POINT(" + f"{lon:.6f}%20{lat:.6f}" + ")&si_srid=4326&rpp=1")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("status") != "OK":
            return None
        results = data.get("results") or []
        if not results:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        p = results[0]
        street = " ".join(x for x in (p.get("addr_number") or "",
                                       p.get("addr_street_prefix") or "",
                                       p.get("addr_street_name") or "",
                                       p.get("addr_street_suffix") or "",
                                       p.get("addr_street_type") or "") if x)
        if not street:
            street = p.get("address") or ""
        return {
            "street": street,
            "city": p.get("addr_city") or "",
            "state": p.get("state_abbr") or "",
            "postcode": p.get("addr_zip") or "",
            "country": "United States",
            "nom_lat": lat, "nom_lon": lon,
        }
    except Exception as e:
        print(f"\n  [WARN] reportall error for {lat},{lon}: {e}")
        return None


def reverse_ambee(lat, lon):
    u = "https://api.ambeedata.com/geocode/reverse/by-lat-lng?" + urllib.parse.urlencode(
        {"lat": lat, "lng": lon})
    try:
        req = urllib.request.Request(u, headers={
            "x-api-key": AMBEE_KEY, "Content-type": "application/json", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("message") != "success":
            return None
        items = data.get("data") or []
        if not items:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        a = items[0].get("address") or {}
        street = " ".join(x for x in (a.get("houseNumber") or "", a.get("street") or "") if x)
        return {
            "street": street,
            "city": a.get("city") or "",
            "state": a.get("state") or "",
            "postcode": a.get("postalCode") or "",
            "country": a.get("countryName") or "",
            "nom_lat": lat, "nom_lon": lon,
        }
    except Exception as e:
        print(f"\n  [WARN] ambee error for {lat},{lon}: {e}")
        return None


def reverse_tamu(lat, lon):
    global TAMU_QUOTA_FAILS, TAMU_DISABLED
    u = "https://geoservices.tamu.edu/Api/ReverseGeocoding/V5/?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "apikey": TAMU_KEY,
        "format": "json", "version": "5.0.0", "notStore": "true"})
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("statusCode") != 200 or data.get("message") != "Success":
            msg = (data.get("message") or "").lower()
            if "quota" in msg or "exceed" in msg or data.get("statusCode") == 470:
                with TAMU_LOCK:
                    TAMU_QUOTA_FAILS += 1
                    if TAMU_QUOTA_FAILS >= TAMU_DISABLE_AFTER:
                        TAMU_DISABLED = True
                        print(f"\n  [WARN] tamu quota exceeded "
                              f"({TAMU_QUOTA_FAILS}x {data.get('message')}) "
                              f"- DISABLED for rest of run")
            return None
        res = (data.get("data") or {}).get("results") or []
        if not res:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        p = res[0]
        return {
            "street": p.get("streetAddress") or "",
            "city": p.get("city") or "",
            "state": p.get("state") or "",
            "postcode": p.get("zip") or "",
            "country": "United States",
            "nom_lat": lat, "nom_lon": lon,
        }
    except Exception as e:
        print(f"\n  [WARN] tamu error for {lat},{lon}: {e}")
        return None


def reverse_tomtom(lat, lon):
    global TOMTOM_AUTH_FAILS, TOMTOM_DISABLED
    u = (f"https://api.tomtom.com/search/2/reverseGeocode/{lat},{lon}.json"
         f"?key={TOMTOM_KEY}&language=en")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
        addrs = data.get("addresses") or []
        if not addrs:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        a = addrs[0].get("address") or {}
        street = " ".join(x for x in (a.get("streetNumber"), a.get("streetName")) if x)
        return {
            "street": street,
            "city": a.get("municipality") or "",
            "state": a.get("countrySubdivision") or "",
            "postcode": a.get("postalCode") or "",
            "country": a.get("country") or "",
            "nom_lat": lat, "nom_lon": lon,
        }
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            with TOMTOM_LOCK:
                TOMTOM_AUTH_FAILS += 1
                if TOMTOM_AUTH_FAILS >= TOMTOM_DISABLE_AFTER:
                    TOMTOM_DISABLED = True
                    print(f"\n  [WARN] tomtom auth failed ({TOMTOM_AUTH_FAILS}x HTTP {e.code}) "
                          f"- key invalid/blocked, DISABLED for rest of run")
        else:
            print(f"\n  [WARN] tomtom HTTP {e.code} for {lat},{lon}")
        return None
    except Exception as e:
        print(f"\n  [WARN] tomtom error for {lat},{lon}: {e}")
        return None


MAPBOX_REVERSE_URL = ("https://api.mapbox.com/geocoding/v5/mapbox.places/"
                      "{lon},{lat}.json?access_token={key}&types=address"
                      "&limit=1&language=en")


def reverse_mapbox(lat, lon):
    """Reverse geocode (lat, lon) -> address via Mapbox.

    Uses types=address so POI results (the church itself) are excluded and the
    nearest street address range is returned instead (same as gw_geo/mapbox.py).
    Returns dict {street, city, state, postcode, country, nom_lat, nom_lon} or None.
    """
    u = MAPBOX_REVERSE_URL.format(lon=lon, lat=lat, key=MAPBOX_KEY)
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        feats = data.get("features") or []
        if not feats:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        f = feats[0]
        road = (f.get("text") or "").strip()
        num = (f.get("address") or "").strip()
        street = f"{num} {road}".strip()
        city = state = postcode = country = ""
        for ctx in f.get("context", []):
            cid = ctx.get("id", "") or ""
            if cid.startswith("place"):
                city = ctx.get("text", "")
            elif cid.startswith("region"):
                sc = ctx.get("short_code", "") or ""
                state = sc.split("-")[-1]
            elif cid.startswith("postcode"):
                postcode = ctx.get("text", "")
            elif cid.startswith("country"):
                country = ctx.get("text", "")
        return {
            "street": street,
            "city": city,
            "state": state,
            "postcode": postcode,
            "country": country,
            "nom_lat": lat, "nom_lon": lon,
        }
    except Exception as e:
        print(f"\n  [WARN] mapbox error for {lat},{lon}: {e}")
        return None


# ── NAME-NEARBY FORWARD SEARCH (rescue after the reverse hunt fails) ─────
# Reverse geocoding can only describe the nearest addressable building to a
# point. Churches mapped in OSM as named POIs with address tags are invisible
# to it, but findable by FORWARD search on the church's name within a small
# box around our known coords. These run ONLY when the reverse chain above
# returned no numbered street, and only accept results that (a) are within
# SEARCH_RADIUS_KM of our point and (b) look like a place of worship, so a
# same-name wrong match can't be written into the DB.

SEARCH_RADIUS_KM = 2.0
PRIMARY_SEARCH_RADIUS_KM = 0.5  # tight box for the primary forward-name pass
WRONG_GPS_KM = 50.0  # a same-name worship place farther than this = stored GPS suspect

WORSHIP_TYPES = {
    "place_of_worship", "church", "cathedral", "basilica", "chapel",
    "mosque", "synagogue", "temple", "gurdwara", "shrine", "monastery",
    "convent", "abbey", "priory", "hermitage", "wayside_shrine",
    "wayside_cross", "religious",
}


def looks_like_worship(cls, typ, display_name=""):
    """True when an OSM/Photon class/type (or name) indicates a religious
    building rather than, say, a shop or house that happens to share a name."""
    if cls in WORSHIP_TYPES or typ in WORSHIP_TYPES:
        return True
    s = (display_name or "").lower()
    return any(w in s for w in ("church", "cathedral", "basilica", "chapel",
                                "mosque", "synagogue", "gurdwara", "worship"))


def _viewbox_around(lat, lon, km):
    """(minlon, minlat, maxlon, maxlat) box roughly `km` on a side around a point."""
    dlat = km / 111.32
    dlon = km / (111.32 * max(0.2, math.cos(math.radians(lat))))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _dist_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    hav = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(hav))


_NAME_SEARCH_WINNERS = ("osm_search", "photon_search", "foursquare_search",
                        "mapsco_search", "mapbox_search", "earth_search",
                        "ban_search", "vk_search")


def forward_photon_unbiased(name, limit=10):
    """Unbiased Photon name search (NO GPS viewbox). Returns list of hit dicts
    with name/lat/lon/osm_key/osm_value. Best-effort: [] on any failure."""
    try:
        u = ("https://photon.komoot.io/api/?" + urllib.parse.urlencode(
            {"q": name, "limit": limit}))
        with urllib.request.urlopen(u, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    hits = []
    for f in data.get("features", []):
        props = f.get("properties", {})
        geo = f.get("geometry", {}).get("coordinates", [None, None])
        hits.append({"name": props.get("name"),
                     "lat": geo[1], "lon": geo[0],
                     "osm_key": props.get("osm_key"),
                     "osm_value": props.get("osm_value")})
    return hits


def _name_tokens(s):
    return {t for t in _re.findall(r"[a-z]+", (s or "").lower()) if len(t) >= 3}


def _close_match(hit_name, church_name):
    """Is a search hit the SAME church as the target? Strong match if the hit
    name is a token-prefix of the church name (e.g. 'Seacoast Church' ->
    'Seacoast Church Mount Pleasant Campus') OR their token Jaccard is high.
    Deliberately excludes denomination-shared words from counting as separate
    churches (e.g. a different 'Southside Vineyard' isn't '... of Augusta')."""
    th, tc = _name_tokens(hit_name), _name_tokens(church_name)
    if not th or not tc:
        return False
    inter = len(th & tc)
    if inter == 0:
        return False
    jacc = inter / len(th | tc)
    if jacc >= 0.7:
        return True
    # token-subset: hit ⊆ church (e.g. 'Seacoast Church' ⊆
    # 'Seacoast Church Mount Pleasant Campus') -> same org, qualifier dropped.
    if th <= tc:
        return True
    return False


def _unbiased_gps_crosscheck(church_name, lat, lon,
                             wrong_km=WRONG_GPS_KM, limit=10):
    """Wrong-GPS cross-check. Returns True if the stored GPS is very likely
    wrong: a strong same-org match for the church name exists but NONE is
    within wrong_km of the stored GPS. If the name is common (>=3 strong
    matches scattered >300 km apart) we can't tell, so return False (don't
    block). Low-harm bias: false positives go to a review table, never written."""
    hits = forward_photon_unbiased(church_name, limit=limit)
    close = [h for h in hits
             if h.get("lat") is not None and h.get("lon") is not None
             and _close_match(h.get("name"), church_name)]
    if not close:
        return False
    near = [h for h in close
            if _dist_km(lat, lon, h["lat"], h["lon"]) <= wrong_km]
    if near:
        return False  # a same-org place near the GPS -> stored GPS is plausible
    # All strong matches are far from the GPS. Common-name guard: if many
    # strong matches are scattered nationwide, the name is generic -> can't tell.
    if len(close) >= 3:
        max_pair = 0.0
        for i in range(len(close)):
            for j in range(i + 1, len(close)):
                d = _dist_km(close[i]["lat"], close[i]["lon"],
                             close[j]["lat"], close[j]["lon"])
                if d > max_pair:
                    max_pair = d
        if max_pair > 300.0:
            return False  # scattered -> common name, can't tell
    return True


def _get_json_retry(req, timeout=20, retries=3, base_delay=2.0, limiter=None):
    """GET/POST JSON with exponential backoff on 429/5xx (rate limits).
    Returns parsed JSON, or raises on final failure (caller's except handles it).
    On a 429/5xx the provider's rate limiter is permanently widened (never
    lowered back), so a throttled host is not hammered at its base rate again."""
    delay = base_delay
    for _attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and _attempt < retries - 1:
                print(f"\n  [retry] HTTP {e.code} after {delay:.0f}s ({_attempt+1}/{retries})",
                      end="", flush=True)
                if limiter is not None:
                    limiter.backoff()
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise  # pragma: no cover


# ── US Census Geocoder normalization (inline parallel stage) ─────────
# After the forward pass writes a US address, a background worker normalizes it
# through the Census onelineaddress endpoint (USPS-standardized matchedAddress
# + Tiger coordinates) at 1 req/s. Runs in a parallel thread so it does not
# extend the pass critical path (the pass is far slower than 1 church/s).
CENSUS_DELAY = 1.0
CENSUS_ADDR_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def _census_oneline(full_addr):
    """One Census Geocoder onelineaddress call -> (lat, lon, matched_address)."""
    params = urllib.parse.urlencode({"address": full_addr, "benchmark": "2020",
                                     "format": "json"})
    url = f"{CENSUS_ADDR_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    m = (data.get("result") or {}).get("addressMatches") or []
    if not m:
        return (None, None, None)
    coords = m[0].get("coordinates") or {}
    return (coords.get("y"), coords.get("x"), m[0].get("matchedAddress"))


def _split_matched(matched):
    """Best-effort split of a Census matchedAddress into street/city/state/zip.
    Census returns '1200 SWINGINGDALE DR, COLUMBIA, SC, 29210'."""
    if not matched:
        return (None, None, None, None)
    parts = [p.strip() for p in matched.split(",") if p.strip()]
    if not parts:
        return (None, None, None, None)
    street = parts[0]
    zip_code = state = city = None
    if parts:
        last = parts[-1]
        if re.match(r"^\d{5}(-\d{4})?$", last):
            zip_code = last.split("-")[0]
            parts = parts[:-1]
    if parts and re.match(r"^[A-Z]{2}$", parts[-1]):
        state = parts[-1]
        parts = parts[:-1]
    if len(parts) > 1:
        city = parts[1]
    elif parts and parts[0] != street:
        city = parts[0]
    return (street, city, state, zip_code)


def _current_components(db, cid):
    """Read the current address components for a church from the live schema."""
    out = {"street": "", "city": "", "state": "", "postcode": "", "country": ""}
    for ctype, cval in db.execute("""
        SELECT ac.component_type, ac.component_value
        FROM church_addresses ca
        JOIN address_components ac ON ca.address_id = ac.address_id
        WHERE ca.church_id=? AND ca.is_current=1
    """, (cid,)):
        if cval and ctype in out:
            out[ctype] = cval
    return out


# Address-bearing (AUTHORITATIVE) source markers — a church carrying any of
# these in churches.source has a real street address from IRS / phone books /
# directories / registries / scrapers and must NOT be overwritten by a forward
# name-search result. (It is still Census-normalized by the writer.)
AUTHORITATIVE_MARKERS = (
    "irs", "overture", "directory", "scraper", "api", "census", "import",
    "ppp", "kaggle", "umc", "cogic", "coc_", "masstimes", "kentucky",
    "txbaptists", "wesleyan", "efca", "arp", "ame_district", "diocese",
    "parish", "opc", "seacoast", "newspring", "cumberland", "cbf",
    "flbaptist", "lcms", "sbc", "nbc", "ipeds", "la_catholic", "csv",
    "contacts", "churchunion", "phone", "loc", "register", "highlands",
    "tn_parcel",
)


def _is_authoritative_source(db, chid):
    """True if the church's churches.source carries an authoritative,
    address-bearing source (IRS / phone books / directories / registries /
    scrapers). Such records must NOT be overwritten by a forward name-search
    result — they are authoritative. Reverse-derived point entries (no address
    source) return False and ARE re-run."""
    row = db.execute("SELECT source FROM churches WHERE id=?", (chid,)).fetchone()
    src = (row[0] if row else "") or ""
    sl = src.lower()
    return any(m in sl for m in AUTHORITATIVE_MARKERS)


def census_worker(census_q, stats, slock):
    """Consume forward-pass US addresses, normalize via Census at 1 req/s, and
    apply USPS-standardized components + Tiger coords with provenance."""
    cdb = sqlite3.connect("E:/grid/churches.db", timeout=120)
    cdb.execute("PRAGMA journal_mode=WAL")
    cdb.execute("PRAGMA busy_timeout=600000")
    cdb.execute("PRAGMA synchronous=NORMAL")
    cdb.execute("PRAGMA cache_size=-1000000")  # 1 GB page cache (huge DB)
    csrc = "census_normalize_2026"
    with slock:
        stats["census"] = {"n": 0, "ok": 0, "err": 0}
    while True:
        item = census_q.get()
        if item is None:
            break
        chid, street, city, state, postcode = item
        with slock:
            stats["census"]["n"] += 1
        full = ", ".join(x for x in (street, city, state, postcode) if x)
        lat = lon = matched = None
        if full:
            try:
                lat, lon, matched = _census_oneline(full)
            except Exception:
                lat = lon = matched = None
        nstreet, ncity, nstate, nzip = _split_matched(matched)
        ok = False
        if nstreet and lat is not None and lon is not None:
            for _attempt in range(3):
                try:
                    old = _current_components(cdb, chid)
                    new = {}
                    for k, v in (("street", nstreet), ("city", ncity),
                                 ("state", nstate), ("postcode", nzip)):
                        if v and v != old.get(k):
                            new[k] = v
                    changes = []
                    if new:
                        set_components(cdb, chid, new, update_legacy=False)
                        for k, v in new.items():
                            changes.append((chid, k, old.get(k), v))
                    cur = cdb.execute(
                        "SELECT latitude,longitude FROM churches WHERE id=?",
                        (chid,)).fetchone()
                    if cur and cur[0] is not None:
                        try:
                            if (abs(float(cur[0]) - lat) > 1e-6
                                    or abs(float(cur[1]) - lon) > 1e-6):
                                cdb.execute(
                                    "UPDATE churches SET latitude=?, longitude=?, "
                                    "last_updated=datetime('now') WHERE id=?",
                                    (lat, lon, chid))
                                changes.append((chid, "latitude", float(cur[0]), lat))
                                changes.append((chid, "longitude", float(cur[1]), lon))
                        except (ValueError, TypeError):
                            pass
                    changes.append((chid, "census_normalized", None,
                                    matched or "census_street"))
                    cdb.executemany(
                        "INSERT INTO enrichment_change_log (church_id, field_name, "
                        "old_value, new_value, change_source, changed_at) "
                        "VALUES (?,?,?,?,?,?)",
                        [(c, f, o, n, csrc,
                          datetime.now(timezone.utc).isoformat())
                         for c, f, o, n in changes])
                    cdb.commit()
                    ok = True
                    break
                except sqlite3.OperationalError:
                    cdb.rollback()
                    time.sleep(1.0)
        with slock:
            stats["census"]["ok" if ok else "err"] += 1
        time.sleep(CENSUS_DELAY)
    cdb.close()


def forward_nominatim_search(name, eng, lat, lon, country, radius=SEARCH_RADIUS_KM):
    """Bounded forward search on the church's name (Nominatim /search).
    Tries the original name first, then the English name. Shares the osm
    provider's rate limiter so reverse + search can't exceed 1 req/s on
    openstreetmap.org. Returns the standard result dict or None."""
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    minlon, minlat, maxlon, maxlat = _viewbox_around(lat, lon, radius)
    for q in dict.fromkeys(queries):
        params = {
            "q": q, "format": "json", "addressdetails": 1,
            "limit": 3, "bounded": 1, "accept-language": "en",
            "viewbox": f"{minlon},{minlat},{maxlon},{maxlat}",
        }
        if country and len(country) == 2:
            params["countrycodes"] = country.lower()
        u = ("https://nominatim.openstreetmap.org/search?"
             + urllib.parse.urlencode(params))
        _OSM_LIMITER.wait()
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            data = _get_json_retry(req, limiter=_OSM_LIMITER)
        except Exception as e:
            print(f"\n  [WARN] osm name-search error for {q}: {e}")
            continue
        for hit in data:
            try:
                lat2, lon2 = float(hit["lat"]), float(hit["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            cls = hit.get("class", "") or ""
            typ = hit.get("type", "") or ""
            if not looks_like_worship(cls, typ, hit.get("display_name", "")):
                continue
            addr = hit.get("address", {}) or {}
            street = build_street(addr)
            if not street:
                continue
            return {
                "street": street,
                "city": extract_city(addr),
                "state": (addr.get("state") or addr.get("province") or
                          addr.get("region") or addr.get("state_district") or ""),
                "postcode": addr.get("postcode", ""),
                "country": addr.get("country", ""),
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


def forward_photon_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward search on the church's name via Photon, biased to our coords
    (Photon has no viewbox, so we verify distance client-side). Shares the
    photon provider's rate limiter. Returns the standard result dict or None."""
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    for q in dict.fromkeys(queries):
        u = ("https://photon.komoot.io/api/?" + urllib.parse.urlencode(
            {"q": q, "lon": lon, "lat": lat, "limit": 5, "lang": "en"}))
        _PHOTON_LIMITER.wait()
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            data = _get_json_retry(req, limiter=_PHOTON_LIMITER)
        except Exception as e:
            print(f"\n  [WARN] photon name-search error for {q}: {e}")
            continue
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon2, lat2 = float(coords[0]), float(coords[1])
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            if not looks_like_worship(props.get("osm_key", ""),
                                      props.get("osm_value", ""),
                                      props.get("name", "")):
                continue
            hn = props.get("housenumber") or ""
            st = props.get("street") or ""
            street = f"{hn} {st}".strip() if (hn or st) else ""
            if not street:
                continue
            return {
                "street": street,
                "city": (props.get("city") or props.get("locality")
                         or props.get("district") or ""),
                "state": props.get("state") or "",
                "postcode": props.get("postcode") or "",
                "country": props.get("country") or "",
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


def forward_chibigeo_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward search on the church's name via ChibiGeo (Photon-compatible,
    key on hand, independent host). Mirrors forward_photon_search. Returns the
    standard result dict or None."""
    if not CHIBIGEO_KEY or _CHIBIGEO_DISABLED:
        return None
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    for q in dict.fromkeys(queries):
        u = ("https://app.chibigeo.com/v1/photon/api/?" + urllib.parse.urlencode(
            {"q": q, "lon": lon, "lat": lat, "limit": 5, "lang": "en"}))
        _CHIBIGEO_LIMITER.wait()
        try:
            req = urllib.request.Request(
                u, headers={"User-Agent": UA, "X-Api-Key": CHIBIGEO_KEY})
            data = _get_json_retry(req, limiter=_CHIBIGEO_LIMITER)
        except Exception as e:
            print(f"\n  [WARN] chibigeo name-search error for {q}: {e}")
            continue
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon2, lat2 = float(coords[0]), float(coords[1])
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            if not looks_like_worship(props.get("osm_key", ""),
                                      props.get("osm_value", ""),
                                      props.get("name", "")):
                continue
            hn = props.get("housenumber") or ""
            st = props.get("street") or ""
            street = f"{hn} {st}".strip() if (hn or st) else ""
            if not street:
                continue
            return {
                "street": street,
                "city": (props.get("city") or props.get("locality")
                         or props.get("district") or ""),
                "state": props.get("state") or "",
                "postcode": props.get("postcode") or "",
                "country": props.get("country") or "",
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


def forward_geocodio_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward name search via Geocodio (US/CA, batch-capable). Mirrors
    forward_photon_search. Returns the standard result dict or None."""
    global _GEOCODIO_ERRS, _GEOCODIO_DISABLED
    if not GEOCODIO_KEY or _GEOCODIO_DISABLED:
        return None
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    for q in dict.fromkeys(queries):
        u = ("https://api.geocod.io/v1/forward?" + urllib.parse.urlencode(
            {"q": q, "api_key": GEOCODIO_KEY}))
        _GEOCODIO_LIMITER.wait()
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            data = _get_json_retry(req, limiter=_GEOCODIO_LIMITER)
        except Exception as e:
            print(f"\n  [WARN] geocodio name-search error for {q}: {e}")
            continue
        for hit in data.get("results") or []:
            ac = hit.get("address_components") or {}
            lat2 = float(ac.get("latitude") or hit.get("latitude") or 0)
            lon2 = float(ac.get("longitude") or hit.get("longitude") or 0)
            if not (lat2 and lon2):
                continue
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            hn = ac.get("street_number") or ""
            st = ac.get("street_name") or ""
            suf = ac.get("street_suffix") or ""
            street = f"{hn} {st} {suf}".strip() if (hn or st or suf) else ""
            if not street:
                continue
            return {
                "street": street,
                "city": ac.get("city") or ac.get("locality") or "",
                "state": ac.get("state") or ac.get("region") or "",
                "postcode": ac.get("postal_code") or "",
                "country": ac.get("country") or "",
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


def forward_locationiq_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward name search via LocationIQ (Nominatim-compatible, global).
    Mirrors forward_photon_search. Returns the standard result dict or None."""
    global _LOCATIONIQ_ERRS, _LOCATIONIQ_DISABLED
    if not LOCATIONIQ_KEY or _LOCATIONIQ_DISABLED:
        return None
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    minlon, minlat, maxlon, maxlat = _viewbox_around(lat, lon, radius)
    for q in dict.fromkeys(queries):
        u = ("https://us1.locationiq.com/v1/search?" + urllib.parse.urlencode(
            {"q": q, "format": "json", "addressdetails": 1, "limit": 3,
             "bounded": 1, "accept-language": "en",
             "viewbox": f"{minlon},{minlat},{maxlon},{maxlat}",
             "key": LOCATIONIQ_KEY}))
        _LOCATIONIQ_LIMITER.wait()
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            data = _get_json_retry(req, limiter=_LOCATIONIQ_LIMITER)
        except Exception as e:
            print(f"\n  [WARN] locationiq name-search error for {q}: {e}")
            continue
        for hit in data:
            try:
                lat2, lon2 = float(hit["lat"]), float(hit["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            addr = hit.get("address") or {}
            hn = addr.get("house_number") or ""
            st = addr.get("road") or addr.get("street") or ""
            street = f"{hn} {st}".strip() if (hn or st) else ""
            if not street:
                continue
            return {
                "street": street,
                "city": extract_city(addr),
                "state": (addr.get("state") or addr.get("province") or
                          addr.get("region") or addr.get("state_district") or ""),
                "postcode": addr.get("postcode") or "",
                "country": addr.get("country") or "",
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


def forward_mapsco_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward name search via geocode.maps.co (Nominatim-compatible /search,
    key on hand, no OSM-host rate issue). Shares the mapsco provider limiter.
    Returns the standard result dict or None."""
    global MAPSCO_429S, MAPSCO_DISABLED
    if MAPSCO_DISABLED:
        return None
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    minlon, minlat, maxlon, maxlat = _viewbox_around(lat, lon, radius)
    for q in dict.fromkeys(queries):
        params = {
            "q": q, "format": "json", "addressdetails": 1,
            "limit": 3, "bounded": 1, "accept-language": "en",
            "viewbox": f"{minlon},{minlat},{maxlon},{maxlat}",
            "api_key": GEOMAPCO_KEY,
        }
        u = "https://geocode.maps.co/search?" + urllib.parse.urlencode(params)
        _MAPSCO_FWD_LIMITER.wait()
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            data = _get_json_retry(req, limiter=_MAPSCO_FWD_LIMITER)
        except Exception as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                with MAPSCO_LOCK:
                    MAPSCO_429S += 1
                    if MAPSCO_429S >= MAPSCO_DISABLE_AFTER:
                        MAPSCO_DISABLED = True
                        print(f"\n  [WARN] geocode.maps.co rate-limited "
                              f"({MAPSCO_429S}x HTTP 429) - DISABLED for rest of run")
            else:
                print(f"\n  [WARN] mapsco name-search error for {q}: {e}")
            continue
        for hit in data:
            try:
                lat2, lon2 = float(hit["lat"]), float(hit["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            cls = hit.get("class", "") or ""
            typ = hit.get("type", "") or ""
            if not looks_like_worship(cls, typ, hit.get("display_name", "")):
                continue
            addr = hit.get("address", {}) or {}
            street = build_street(addr)
            if not street:
                continue
            return {
                "street": street,
                "city": extract_city(addr),
                "state": (addr.get("state") or addr.get("province") or
                          addr.get("region") or addr.get("state_district") or ""),
                "postcode": addr.get("postcode", ""),
                "country": addr.get("country", ""),
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


def forward_mapbox_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward name search via Mapbox Geocoding (mapbox.places), proximity-
    biased to our coords. Key on hand; free tier ~600/min (no OSM 1 req/s cap).
    Returns the standard result dict or None."""
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    for q in dict.fromkeys(queries):
        u = ("https://api.mapbox.com/geocoding/v5/mapbox.places/"
             + urllib.parse.quote(q) + ".json?" + urllib.parse.urlencode({
                 "proximity": f"{lon},{lat}", "limit": 5,
                 "access_token": MAPBOX_KEY,
             }))
        _MAPBOX_FWD_LIMITER.wait()
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            data = _get_json_retry(req, limiter=_MAPBOX_FWD_LIMITER)
        except Exception as e:
            print(f"\n  [WARN] mapbox name-search error for {q}: {e}")
            continue
        for feat in data.get("features") or []:
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon2, lat2 = float(coords[0]), float(coords[1])
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            ptypes = feat.get("place_type") or []
            pname = (feat.get("text") or "") + " " + (feat.get("place_name") or "")
            if not looks_like_worship("", "", pname):
                if "poi" not in ptypes and "address" not in ptypes:
                    continue
            props = feat.get("properties") or {}
            street = props.get("address") or feat.get("address") or ""
            context = feat.get("context") or []
            city = state = postcode = country = ""
            for c in context:
                cid = c.get("id", "")
                txt = c.get("text", "")
                if cid.startswith("place") or cid.startswith("locality"):
                    city = city or txt
                elif cid.startswith("region"):
                    state = state or txt
                elif cid.startswith("postcode"):
                    postcode = postcode or txt
                elif cid.startswith("country"):
                    country = country or txt
            if not street:
                continue
            return {
                "street": street,
                "city": city,
                "state": state,
                "postcode": postcode,
                "country": country,
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


def forward_earth_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward name search via geocode.earth (Pelias /v1/search), bounded to a
    rect around our coords. Key on hand (quota'd). Returns the standard result
    dict or None. Shares the earth circuit breaker: once it 429s/fails
    repeatedly we disable earth entirely (reverse + forward) so it stops
    burning requests on every church."""
    global EARTH_429S, EARTH_DISABLED
    if EARTH_DISABLED:
        return None
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    d = max(0.01, radius / 111.32)
    for q in dict.fromkeys(queries):
        u = ("https://api.geocode.earth/v1/search?" + urllib.parse.urlencode({
            "text": q, "size": 3, "api_key": EARTH_KEY,
            "boundary.rect.min_lon": lon - d, "boundary.rect.min_lat": lat - d,
            "boundary.rect.max_lon": lon + d, "boundary.rect.max_lat": lat + d,
        }))
        _EARTH_FWD_LIMITER.wait()
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            data = _get_json_retry(req, timeout=5, limiter=_EARTH_FWD_LIMITER)
        except Exception as e:
            with EARTH_LOCK:
                EARTH_429S += 1
                if EARTH_429S >= EARTH_DISABLE_AFTER:
                    EARTH_DISABLED = True
                    print(f"\n  [WARN] geocode.earth repeatedly failing "
                          f"({EARTH_429S}x) - DISABLED for rest of run")
            print(f"\n  [WARN] earth name-search error for {q}: {e}")
            continue
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon2, lat2 = float(coords[0]), float(coords[1])
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            layers = props.get("layer", "") or ""
            pname = (props.get("name") or "") + " " + (props.get("label") or "")
            if not looks_like_worship("", layers, pname):
                if layers not in ("venue", "address", "street"):
                    continue
            hn = props.get("housenumber") or ""
            st = props.get("street") or ""
            street = f"{hn} {st}".strip() if (hn or st) else ""
            if not street:
                continue
            return {
                "street": street,
                "city": (props.get("locality") or props.get("borough")
                         or props.get("neighbourhood") or ""),
                "state": props.get("region") or "",
                "postcode": props.get("postalcode") or "",
                "country": props.get("country") or "",
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


def forward_ban_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward search via BAN France (api-adresse.data.gouv.fr) — free, no key,
    no rate cap, FRANCE-ONLY (caller gates on country == 'FR'). Returns the
    standard result dict or None."""
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    for q in dict.fromkeys(queries):
        u = ("https://api-adresse.data.gouv.fr/search/?" + urllib.parse.urlencode({
            "q": q, "limit": 5, "lat": lat, "lon": lon,
        }))
        _BAN_FWD_LIMITER.wait()
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            data = _get_json_retry(req, limiter=_BAN_FWD_LIMITER)
        except Exception as e:
            print(f"\n  [WARN] ban name-search error for {q}: {e}")
            continue
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            lon2, lat2 = float(coords[0]), float(coords[1])
            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue
            label = props.get("label") or ""
            if not looks_like_worship("", "", label):
                continue
            street = props.get("name") or ""
            city = props.get("city") or ""
            postcode = props.get("postcode") or ""
            if not street:
                continue
            return {
                "street": street,
                "city": city,
                "state": "",
                "postcode": postcode,
                "country": "France",
                "nom_lat": lat2, "nom_lon": lon2,
            }
    return None


# VK Maps Overpass (public OSM Overpass mirror) - forward name search.
# Used by scripts/enrichment/_import_jp*.py; here it finds the church's own
# place-of-worship POI + address tags around our coords via Overpass `around`.
VK_OVERPASS = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"


def forward_vk_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward name search via VK Maps Overpass (public OSM mirror). Queries
    places of worship whose name contains <q> within `radius` of our coords
    (Overpass `around`), returning the POI's address + precise point."""
    global _VK_FAILS, _VK_DISABLED
    if _VK_DISABLED:
        return None
    queries = [q for q in (name, eng)
               if q and isinstance(q, str) and len(q.strip()) >= 3]
    if not queries:
        return None
    radius_m = max(100, min(int(radius * 1000), 50000))
    for q in dict.fromkeys(queries):
        qesc = q.replace("\\", "\\\\").replace('"', '\\"')
        ov = (f"[out:json][timeout:25];\n(\n"
              f"  nwr[amenity=place_of_worship]"
              f"[~\"^name(:.*)?$\"~\"{qesc}\",i]"
              f"(around:{radius_m},{lat},{lon});\n);\n"
              f"out center tags 30;")
        _VK_FWD_LIMITER.wait()
        try:
            req = urllib.request.Request(VK_OVERPASS, data=ov.encode("utf-8"),
                                        headers={"User-Agent": UA},
                                        method="POST")
            data = _get_json_retry(req, timeout=30, limiter=_VK_FWD_LIMITER)
        except Exception as e:
            with _VK_LOCK:
                _VK_FAILS += 1
                if _VK_FAILS >= _VK_DISABLE_AFTER:
                    _VK_DISABLED = True
                    print(f"\n  [WARN] vk overpass repeatedly failing ({_VK_FAILS}x "
                          f"{type(e).__name__}) - DISABLED for rest of run")
            print(f"\n  [WARN] vk overpass search error for {q}: {e}")
            continue
        for el in data.get("elements") or []:
            elat = el.get("lat") or (el.get("center") or {}).get("lat")
            elon = el.get("lon") or (el.get("center") or {}).get("lon")
            if elat is None or elon is None:
                continue
            elat, elon = float(elat), float(elon)
            if _dist_km(lat, lon, elat, elon) > radius:
                continue
            tags = el.get("tags") or {}
            hn = tags.get("addr:housenumber") or ""
            st = tags.get("addr:street") or ""
            street = f"{hn} {st}".strip() if (hn or st) else ""
            if not street:
                continue
            return {
                "street": street,
                "city": tags.get("addr:city") or tags.get("addr:place") or "",
                "state": tags.get("addr:state") or "",
                "postcode": tags.get("addr:postcode") or "",
                "country": tags.get("addr:country") or "",
                "nom_lat": elat, "nom_lon": elon,
            }
    return None


# Foursquare category IDs for the places we care about: the Spiritual Center
# family (Community and Government > Spiritual Center). Used to restrict
# /v3/places/search to religious venues, so a same-name cafe/shop/office can
# never win the forward-name match.
FOURSQUARE_WORSHIP_CATEGORIES = [
    "4bf58dd8d48988d131941735",  # Spiritual Center
    "52e81612bcbc57f1066b7a3e",  # Buddhist Temple
    "58daa1558bbb0b01f18ec1eb",  # Cemevi
    "4bf58dd8d48988d132941735",  # Church
    "56aa371be4b08b9a8d5734fc",  # Confucian Temple
    "52e81612bcbc57f1066b7a3f",  # Hindu Temple
    "5744ccdfe4b0c0459246b4ac",  # Kingdom Hall
    "52e81612bcbc57f1066b7a40",  # Monastery
    "4bf58dd8d48988d138941735",  # Mosque
    "52e81612bcbc57f1066b7a41",  # Prayer Room
    "4eb1d80a4b900d56c88a45ff",  # Shrine
    "5bae9231bedf3950379f89c9",  # Sikh Temple
    "4bf58dd8d48988d139941735",  # Synagogue
    "4bf58dd8d48988d13a941735",  # Temple
    "56aa371be4b08b9a8d5734f6",  # Terreiro
]
FOURSQUARE_WORSHIP_SET = set(FOURSQUARE_WORSHIP_CATEGORIES)
# Migrated Places API (2026): new host + date-version header; coordinates are
# top-level latitude/longitude; category ids are under fsq_category_id.
FOURSQUARE_SEARCH_URL = "https://places-api.foursquare.com/places/search"
FOURSQUARE_API_VERSION = "2025-06-17"


def forward_foursquare_search(name, eng, lat, lon, radius=SEARCH_RADIUS_KM):
    """Forward name search via Foursquare Places API.

    Restricts results to the Spiritual Center category family (both via the
    API's `categories` filter and a client-side check) so only an actual
    place of worship can satisfy the match.
    """

    global _FSQ_FAILS, _FSQ_DISABLED
    if not FOURSQUARE_KEY or _FSQ_DISABLED:
        return None

    queries = [
        q.strip()
        for q in (name, eng)
        if isinstance(q, str) and len(q.strip()) >= 3
    ]

    if not queries:
        return None

    for q in dict.fromkeys(queries):
        params = {
            "query": q,
            "ll": f"{lat:.6f},{lon:.6f}",
            "radius": max(100, min(int(radius * 1000), 100000)),
            "limit": 5,
            "categories": ",".join(FOURSQUARE_WORSHIP_CATEGORIES),
        }

        url = (
            FOURSQUARE_SEARCH_URL + "?"
            + urllib.parse.urlencode(params)
        )

        _FOURSQUARE_FWD_LIMITER.wait()

        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {FOURSQUARE_KEY}",
                "X-Places-Api-Version": FOURSQUARE_API_VERSION,
                "User-Agent": UA,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = json.loads(
                    response.read().decode("utf-8", errors="replace")
                )

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:2000]
            except Exception:
                pass

            print(
                f"\n[FOURSQUARE] HTTP {e.code} for {q!r}"
                f"\n  URL: {url}"
                f"\n  BODY: {body}"
            )

            if e.code >= 500:
                return None

            if e.code in (401, 403):
                print(
                    "\n[FOURSQUARE] Authentication/authorization "
                    "failure. Foursquare disabled for this run."
                )
                return None

            if e.code == 429:
                with _FSQ_LOCK:
                    _FSQ_FAILS += 1
                    if _FSQ_FAILS >= _FSQ_DISABLE_AFTER:
                        _FSQ_DISABLED = True
                        print("\n  [WARN] Foursquare quota exhausted "
                              f"({_FSQ_FAILS}x HTTP 429 'no API credits') - "
                              "DISABLED for rest of run")
                return None

            continue

        except Exception as e:
            print(f"\n[FOURSQUARE] Request failed for {q!r}: {e}")
            return None

        for result in data.get("results") or []:
            location = result.get("location") or {}

            # Client-side category check (fsq_category_id in the migrated API).
            cats = result.get("categories") or []
            if not any(c.get("fsq_category_id") in FOURSQUARE_WORSHIP_SET
                       for c in cats):
                continue

            # Migrated Places API exposes the POI's coordinates at the TOP
            # LEVEL as latitude/longitude (no geocodes object anymore).
            lat2 = result.get("latitude")
            lon2 = result.get("longitude")

            if lat2 is None or lon2 is None:
                continue

            lat2 = float(lat2)
            lon2 = float(lon2)

            if _dist_km(lat, lon, lat2, lon2) > radius:
                continue

            street = location.get("address") or ""
            city = location.get("locality") or ""
            state = location.get("region") or ""
            postcode = location.get("postcode") or ""
            country = location.get("country") or ""

            if not street:
                street = location.get("formatted_address") or ""

            if not street:
                continue

            return {
                "street": street,
                "city": city,
                "state": state,
                "postcode": postcode,
                "country": country,
                "nom_lat": lat2,
                "nom_lon": lon2,
            }

    return None


def worker(prov, work_q, res_q, stats, slock):
    name = prov["name"]
    others = [p for p in PROVIDERS if p["name"] != name]
    # prefer a different-kind provider first (photon <-> nominatim), so an OSM
    # failure tries photon before the other Nominatim-based providers.
    others.sort(key=lambda p: (p["kind"] == prov["kind"]))
    while True:
        item = work_q.get()
        if item is None:
            break
        chid, church_name, lat, lon, country, eng = item

        def classify(provname, res):
            with slock:
                stats[provname]["n"] += 1
                if res and res.get("street"):
                    stats[provname]["ok"] += 1
                elif res:
                    stats[provname]["empty"] += 1
                else:
                    stats[provname]["err"] += 1

        def merge_res(base, new):
            """Best-available merge: keep base, fill empty core fields from new.
            If base's street has no house number but new's does, upgrade the
            street (a bare 'Main St' can't locate a building; '123 Main St' can)."""
            if base is None:
                return new
            if new is None:
                return base
            out = dict(base)
            for k in ("street", "city", "state", "postcode", "country"):
                if not out.get(k) and new.get(k):
                    out[k] = new[k]
            if (out.get("street") and new.get("street")
                    and not numbered_street(out) and numbered_street(new)):
                out["street"] = new["street"]
            return out

        def absorb(provname, r2):
            """Merge r2 into res; credit winner if it supplied/upgraded the street."""
            nonlocal res, winner, rescued
            if r2 is None:
                return
            had_street = bool(res and res.get("street"))
            was_numbered = numbered_street(res)
            res = merge_res(res, r2)
            if (not had_street and r2.get("street")) or \
                    (not was_numbered and numbered_street(res)):
                winner = provname
                rescued = True

        # 1) FORWARD NAME SEARCH FIRST: we hold the church's name AND its
        #    coords, so the most accurate address is the one attached to the
        #    church's own POI (its OSM address tags) — not the nearest
        #    addressable building to the point (a reverse proxy). Search by
        #    name inside a TIGHT box (PRIMARY_SEARCH_RADIUS_KM) so only a
        #    same-building worship-class match can win outright.
        res = None
        winner = None
        tried = []
        rescued = False
        _rc_before = rescued
        _has_osm = any(p["name"] == "osm" for p in PROVIDERS)
        # Forward chain ordered by measured street-address success
        # (geocode_source wins in enrichment_change_log, 2026-08-14..20):
        # osm_search 998 > photon_search 843 > foursquare_search 128 >
        # earth_search 79 > mapsco_search 9 > ban/vk/chibigeo/mapbox ~0.
        # Poll best-first; break at the first house-numbered street.
        for sname, sfunc in (
                ("osm_search",
                 lambda: forward_nominatim_search(church_name, eng, lat, lon, country,
                                                  radius=PRIMARY_SEARCH_RADIUS_KM)
                 if _has_osm else None),
                ("photon_search",
                 lambda: forward_photon_search(church_name, eng, lat, lon,
                                               radius=PRIMARY_SEARCH_RADIUS_KM)),
                ("foursquare_search",
                 lambda: forward_foursquare_search(church_name, eng, lat, lon,
                                                  radius=PRIMARY_SEARCH_RADIUS_KM)
                 if FOURSQUARE_KEY else None),
                ("earth_search",
                 lambda: forward_earth_search(church_name, eng, lat, lon,
                                               radius=PRIMARY_SEARCH_RADIUS_KM)),
                ("mapsco_search",
                 lambda: forward_mapsco_search(church_name, eng, lat, lon,
                                               radius=PRIMARY_SEARCH_RADIUS_KM)),
                ("ban_search",
                 lambda: forward_ban_search(church_name, eng, lat, lon,
                                            radius=PRIMARY_SEARCH_RADIUS_KM)
                 if country == "FR" else None),
                ("vk_search",
                 lambda: forward_vk_search(church_name, eng, lat, lon,
                                           radius=PRIMARY_SEARCH_RADIUS_KM)),
                # ChibiGeo: quota-paid (2500/day) - reached only when the free
                # providers above found no numbered street.
                ("chibigeo_search",
                 lambda: forward_chibigeo_search(church_name, eng, lat, lon,
                                                 radius=PRIMARY_SEARCH_RADIUS_KM)
                 if CHIBIGEO_KEY else None),
                # Geocodio: US/CA only, 2500/day quota - before Mapbox.
                ("geocodio_search",
                 lambda: forward_geocodio_search(church_name, eng, lat, lon,
                                                 radius=PRIMARY_SEARCH_RADIUS_KM)
                 if GEOCODIO_KEY else None),
                # LocationIQ: global, 5000/day quota - before Mapbox.
                ("locationiq_search",
                 lambda: forward_locationiq_search(church_name, eng, lat, lon,
                                                  radius=PRIMARY_SEARCH_RADIUS_KM)
                 if LOCATIONIQ_KEY else None),
                # Mapbox LAST RESORT: limited API credits - only reached when
                # every other forward provider failed to find a numbered street.
                ("mapbox_search",
                 lambda: forward_mapbox_search(church_name, eng, lat, lon,
                                               radius=PRIMARY_SEARCH_RADIUS_KM))):
            fres = sfunc()
            classify(sname, fres)
            absorb(sname, fres)
            tried.append(sname)
            if numbered_street(res):
                break
        rescued = _rc_before  # forward is the PRIMARY source — not "rescued"
        # 1b) LOOP FORWARD -> REVERSE: a forward win carries the POI's OWN
        #     precise coordinates (nom_lat/nom_lon). Reverse-geocode AT those
        #     coordinates (not the stored, possibly coarse GPS) so the street
        #     address describes the actual building rather than the nearest
        #     building to a coarse point. Falls back to the stored GPS when no
        #     forward hit or the forward point is implausibly far.
        rlat, rlon = lat, lon
        if res is not None and res.get("nom_lat") is not None \
                and res.get("nom_lon") is not None:
            try:
                _d = _dist_km(lat, lon, float(res["nom_lat"]),
                              float(res["nom_lon"]))
                if 0.0 < _d <= SEARCH_RADIUS_KM:
                    rlat, rlon = float(res["nom_lat"]), float(res["nom_lon"])
            except (TypeError, ValueError):
                pass
        # 2) REVERSE HUNT (always, cross-check + fill): forward can return a
        #    bare road name without a house number; reverse describes the
        #    ACTUAL point (its house-numbered street, city, postcode). Run the
        #    primary reverse chain for EVERY church and merge it into the
        #    forward result (forward's own fields win; reverse fills gaps).
        #    We stop adding providers once the merged result already carries a
        #    numbered street (forward usually provides one), so quota-heavy
        #    providers are only added when still missing a building-level
        #    address.
        res0 = provider_call(prov, rlat, rlon)
        classify(name, res0)
        absorb(name, res0)   # merge into any partial forward result
        tried.append(name)
        for p2 in others:
            r2 = provider_call(p2, rlat, rlon)
            classify(p2["name"], r2)
            absorb(p2["name"], r2)
            tried.append(p2["name"])
            if numbered_street(res):
                break
        if not numbered_street(res) and EARTH_KEY:
            re_ = earth_call(rlat, rlon)
            classify("geocode.earth", re_)
            absorb("geocode.earth", re_)
            tried.append("geocode.earth")
        if not numbered_street(res) and TOMTOM_KEY:
            tt = tomtom_call(rlat, rlon)
            classify("tomtom", tt)
            absorb("tomtom", tt)
            tried.append("tomtom")
        if not numbered_street(res) and country == "US" and REPORTALL_KEY:
            rr = reportall_call(rlat, rlon)
            classify("reportall", rr)
            absorb("reportall", rr)
            tried.append("reportall")
        if not numbered_street(res) and country == "US" and TAMU_KEY:
            tm = tamu_call(rlat, rlon)
            classify("tamu", tm)
            absorb("tamu", tm)
            tried.append("tamu")
        if not numbered_street(res) and AMBEE_KEY:
            if ambee_quota_take():
                am = ambee_call(rlat, rlon)
                classify("ambee", am)
                absorb("ambee", am)
                tried.append("ambee")
        if not numbered_street(res) and CHIBIGEO_KEY:
            if chibigeo_quota_take():
                cb = reverse_chibigeo(rlat, rlon)
                classify("chibigeo", cb)
                absorb("chibigeo", cb)
                tried.append("chibigeo")
        # Mapbox LAST RESORT: limited API credits - only reached when every
        # other reverse provider found no numbered street.
        if not numbered_street(res) and MAPBOX_KEY:
            mb = mapbox_call(rlat, rlon)
            classify("mapbox", mb)
            absorb("mapbox", mb)
            tried.append("mapbox")
        # 4) LOOSE NAME RESCUE: reverse also found nothing — gamble on a
        #    same-name worship-class result up to SEARCH_RADIUS_KM (2 km).
        #    Last resort only; the tight forward pass already tried close range.
        #    Anchored at the forward-refined point (rlat/rlon) when available.
        if not numbered_street(res):
            for sname, sfunc in (
                    ("foursquare_search",
                     lambda: forward_foursquare_search(church_name, eng, rlat, rlon)
                     if FOURSQUARE_KEY else None),
                    ("osm_search",
                     lambda: forward_nominatim_search(church_name, eng, rlat, rlon, country)
                     if _has_osm else None),
                    ("photon_search",
                     lambda: forward_photon_search(church_name, eng, rlat, rlon)),
                    ("mapsco_search",
                     lambda: forward_mapsco_search(church_name, eng, rlat, rlon)),
                    ("earth_search",
                     lambda: forward_earth_search(church_name, eng, rlat, rlon)),
                    ("ban_search",
                     lambda: forward_ban_search(church_name, eng, rlat, rlon)
                     if country == "FR" else None),
                    ("vk_search",
                     lambda: forward_vk_search(church_name, eng, rlat, rlon)),
                    # ChibiGeo: quota-paid (2500/day) - last resort before Mapbox.
                    ("chibigeo_search",
                     lambda: forward_chibigeo_search(church_name, eng, rlat, rlon)
                     if CHIBIGEO_KEY else None),
                    # Mapbox LAST RESORT: limited API credits.
                    ("mapbox_search",
                     lambda: forward_mapbox_search(church_name, eng, rlat, rlon))):
                fres = sfunc()
                classify(sname, fres)
                absorb(sname, fres)
                tried.append(sname)
                if numbered_street(res):
                    break
        if rescued:
            with slock:
                stats["_rescued"]["n"] += 1
        # 5) UNBIASED NAME CROSS-CHECK (wrong-GPS guard): verify the stored GPS
        #    is plausible for a NAME-SEARCH winner by searching the church name
        #    with NO GPS bias. If every strong same-org match is far from the
        #    stored GPS, the GPS is wrong (e.g. #4334 NH->SC, #5161 IL->SC) --
        #    route to review instead of writing. Runs for NAME-SEARCH winners
        #    ONLY: for a REVERSE winner the address is derived FROM the stored
        #    GPS (always self-consistent), and the unbiased search often finds
        #    no same-name match at a small/untagged church's exact point, so
        #    running it there produced many FALSE positives (e.g. #6050 Torch
        #    Worship Center Iowa, #6094 7th Street COG Illinois -- both flagged
        #    despite self-consistent GPS). Genuine wrong-GPS duplicates are
        #    instead caught by the dedup/review workflow (#5992 -> #146816).
        if (res is not None and res.get("street")
                and winner in _NAME_SEARCH_WINNERS):
            try:
                # The winning NAME-SEARCH result is GPS-biased: it was found
                # NEAR the stored GPS. If its OWN coordinates are also within
                # WRONG_GPS_KM of the stored GPS, the stored GPS is validated by
                # the search itself (a real same-name place sits there) -- the
                # unbiased cross-check only tends to add FALSE positives in that
                # case (common names + OSM POI gaps, e.g. #2294892 Fairview
                # United Church -> 49 Wayne Dr, correct, but flagged). Only run
                # the cross-check when the result is NOT near the stored GPS.
                _rn_lat = res.get("nom_lat")
                _rn_lon = res.get("nom_lon")
                _res_near_gps = (
                    _rn_lat is not None and _rn_lon is not None
                    and _dist_km(lat, lon, float(_rn_lat), float(_rn_lon))
                    <= WRONG_GPS_KM)
                if (not _res_near_gps
                        and _unbiased_gps_crosscheck(church_name, lat, lon)):
                    res = dict(res)
                    res["wrong_gps"] = True
                    print(f"\n  [WARN] {chid} | {church_name} | {lat:.4f},{lon:.4f} -> "
                          f"all name matches far from stored GPS (wrong-GPS), "
                          "routed to review", flush=True)
            except Exception:
                pass
        # 5b) HOUSE-NUMBER COMPLETION: if we only got a bare street name (no
        #     house number), that is still the closest thing we have -- write
        #     it -- but try to upgrade it by reverse-geocoding AT the result's
        #     OWN coordinates to fetch a house number. Best-effort: a public
        #     photon reverse returns a housenumber when one exists at that
        #     point. If none is found, keep the bare street (still written).
        if (res is not None and res.get("street") and not numbered_street(res)
                and not res.get("wrong_gps")):
            try:
                _plat = float(res.get("nom_lat"))
                _plon = float(res.get("nom_lon"))
                _PHOTON_LIMITER.wait()
                _rr = reverse_photon(_plat, _plon)
                if _rr and _rr.get("street") and numbered_street(_rr):
                    print(f"\n  [OK] {chid} | {church_name} | completed street "
                          f"'{res.get('street')}' -> '{_rr['street']}' via photon reverse",
                          flush=True)
                    res = dict(res)
                    res["street"] = _rr["street"]
            except Exception:
                pass
        res_q.put((chid, church_name, lat, lon, res, winner, tried, eng))
        work_q.task_done()


import re as _re
_STREET_SUFFIX = (r"(?:ROAD|RD|STREET|ST|AVENUE|AVE|BLVD|BOULEVARD|DR|DRIVE|LANE|LN|"
                  r"WAY|COURT|CT|PLACE|PL|CIRCLE|CIR|HIGHWAY|HWY|PIKE|TRACE|TRAIL|"
                  r"TERRACE|TER|PARKWAY|PKWY|CROSSING|XING|LOOP|ROW)")
_NAME_STREET_RE = _re.compile(
    r"\b(?:OF|ON|AT)\s+([A-Z0-9][A-Z0-9.\'\-]*(?:\s+[A-Z0-9][A-Z0-9.\'\-]*)?)\s+"
    + _STREET_SUFFIX + r"\b", _re.IGNORECASE)


def _name_embedded_street(name):
    """If a church name embeds a street (e.g. 'OF ATLAS ROAD', 'ON MAIN ST'),
    return the lowercased street-name token(s); else None."""
    if not name:
        return None
    m = _NAME_STREET_RE.search(name)
    return m.group(1).strip().lower() if m else None


def post_result(db, now, chid, name, lat, lon, res, winner, tried, changes, log_rows):
    """Apply one result to the DB (called from the single writer thread).

    geocode_source is set to the WINNING provider; every provider that was
    queried but did not win is logged as an enrichment pass
    (field_name='geocode_pass') so the hunt is fully auditable.

    Retries on database lock errors with exponential backoff.
    """
    import time
    max_retries = 60
    for attempt in range(max_retries):
        try:
            # ── Authoritative-source guard: skip churches whose source is an
            #    address-bearing record (IRS / phone books / directories /
            #    registries / scrapers) AND that ALREADY have a COMPLETE,
            #    house-numbered street address. Those existing addresses are
            #    authoritative — don't let a forward name-search overwrite
            #    them. (Census normalization still applies via the writer.)
            #    Churches that are point-only (no street) OR whose street has
            #    no house number are NOT skipped: they are forward name-searched
            #    as a POI to obtain a complete address. Reverse-derived point
            #    entries (no address source) also re-run.
            _gcomps = _current_components(db, chid)
            if (_is_authoritative_source(db, chid)
                    and bool(NUMBERED_STREET_RE.match(_gcomps.get("street") or ""))):
                log_rows.append((chid, now, "no_result", None, None, None, None,
                                 None, None, None, None))
                return "skip_complete"
            if res:
                dist_m = round(math.sqrt((res["nom_lat"] - lat) ** 2 +
                                         (res["nom_lon"] - lon) ** 2) * 111320.0, 1)
                status = "success" if res["street"] else "no_result"
                # ── Wrong-GPS guard ──────────────────────────────────────────
                # If the church NAME embeds a street (e.g. 'OF ATLAS ROAD') but
                # the winning NAME-SEARCH result's street doesn't contain that
                # street, the stored GPS is suspect (duplicate/garbage GPS like
                # #4334 'Bible Way Church of Atlas Road' stored in NH). Don't
                # write the result — route to a review table instead.
                _wg = res.get("wrong_gps")
                _emb = _name_embedded_street(name)
                _emb_mismatch = False
                if (not _wg and winner in _NAME_SEARCH_WINNERS
                        and _emb and res.get("street")):
                    emb_words = {w for w in _emb.split() if len(w) >= 3 and not w.isdigit()}
                    res_words = set(_re.findall(r"[a-z]+", res["street"].lower()))
                    _emb_mismatch = bool(emb_words) and not (emb_words & res_words)
                if _wg or _emb_mismatch:
                    db.execute(
                        "CREATE TABLE IF NOT EXISTS fwd_wrong_gps_candidates ("
                        "church_id INTEGER PRIMARY KEY, name TEXT, "
                        "stored_lat REAL, stored_lon REAL, embedded_street TEXT, "
                        "result_street TEXT, result_city TEXT, result_state TEXT, "
                        "winner TEXT, created_at TEXT DEFAULT (datetime('now')))")
                    db.execute(
                        "INSERT OR REPLACE INTO fwd_wrong_gps_candidates "
                        "(church_id, name, stored_lat, stored_lon, embedded_street, "
                        " result_street, result_city, result_state, winner) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (chid, name, lat, lon, _emb, res.get("street"),
                         res.get("city"), res.get("state"), winner))
                    log_rows.append(
                        (chid, now, "no_result", res["street"], res["city"],
                         res["state"], res["postcode"], res.get("nom_lat"),
                         res.get("nom_lon"), None, res.get("country")))
                    return "wrong_gps"
                comps = {}
                if res["street"]:
                    comps["street"] = res["street"]
                for k in ("city", "state", "postcode", "country"):
                    if res[k]:
                        comps[k] = res[k]
                if comps:
                    set_components(db, chid, comps, update_legacy=False)
                    if winner:
                        db.execute("UPDATE church_addresses SET geocode_source=?, source=? "
                                   "WHERE church_id=? AND is_current=1", (winner, SOURCE, chid))
                    # per-record modification audit: log EVERY field that was written
                    for k, v in comps.items():
                        changes.append((chid, k, None, v))
                    if winner:
                        changes.append((chid, "geocode_source", None, winner))
                    # losers as enrichment passes (dedup'd, order preserved)
                    _seen = set()
                    for loser in tried:
                        if loser != winner and loser not in _seen:
                            _seen.add(loser)
                            changes.append((chid, "geocode_pass", None, loser))
                # ── Precision upgrade: a FORWARD search winner returns the
                #    church POI's OWN coordinates (nom_lat/nom_lon), which are
                #    more precise than the stored GPS (which may be a coarse
                #    centroid or an address-point proxy). Move the church to
                #    the POI point, but ONLY when the jump stays inside the
                #    tight primary search box (0.5 km) — a further jump would
                #    mean a same-name wrong site, not a precision fix.
                if winner in ("osm_search", "photon_search", "foursquare_search"):
                    try:
                        nlat = float(res["nom_lat"])
                        nlon = float(res["nom_lon"])
                    except (KeyError, TypeError, ValueError):
                        nlat = nlon = None
                    if nlat is not None and (abs(nlat - lat) > 1e-7 or abs(nlon - lon) > 1e-7):
                        dlat = abs(nlat - lat) * 111320.0
                        dlon = abs(nlon - lon) * 111320.0 * max(0.2, math.cos(math.radians(lat)))
                        if max(dlat, dlon) <= PRIMARY_SEARCH_RADIUS_KM * 1000.0:
                            cur = db.execute(
                                "SELECT latitude, longitude FROM churches WHERE id=?",
                                (chid,)).fetchone()
                            if cur and cur[0] is not None:
                                old_lat, old_lon = float(cur[0]), float(cur[1])
                                if (abs(old_lat - nlat) > 1e-7 or abs(old_lon - nlon) > 1e-7):
                                    db.execute(
                                        "UPDATE churches SET latitude=?, longitude=?, "
                                        "last_updated=datetime('now') WHERE id=?",
                                        (nlat, nlon, chid))
                                    changes.append((chid, "latitude", old_lat, nlat))
                                    changes.append((chid, "longitude", old_lon, nlon))
                                    changes.append((chid, "geocode_precision", None,
                                                    f"forward_{winner}"))
                log_rows.append((chid, now, status, res["street"], res["city"], res["state"],
                                 res["postcode"], res["nom_lat"], res["nom_lon"], dist_m,
                                 res["country"]))
                return status
            log_rows.append((chid, now, "http_error", None, None, None, None, None, None, None, None))
            return "http_error"
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                # release any transaction THIS connection holds before retrying,
                # so we never sit on a lock while waiting for the other writer
                try:
                    db.rollback()
                except Exception:
                    pass
                wait_time = min(30, 0.5 * (2 ** attempt))  # capped: .5,1,2,4,8,16,30,30...
                print(f"\n  [WARN] DB locked, retry {attempt+1}/{max_retries} after {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise


TR_SOURCE = {"gemini": "gemini_name_translate_live_2026",
             "groq": "groq_name_translate_live_2026"}


def translate_worker(tr_q, stats, slock):
    """Consume (church_id, name, country, street, city, state) items from the
    geocoder, batch-translate the name AND address fields via LLM, and store
    name_english + street_en/city_en/state_en address components (own DB
    connection; WAL handles concurrency). Logs every change to
    enrichment_change_log AND provenance_log."""
    tdb = sqlite3.connect(DB)
    tdb.execute("PRAGMA journal_mode=WAL")
    tdb.execute("PRAGMA busy_timeout=600000")
    tdb.execute("PRAGMA synchronous=NORMAL")
    tdb.execute("PRAGMA cache_size=-1000000")  # 1 GB page cache (huge DB)
    src = TR_SOURCE.get(TR_PROVIDER, "llm_name_translate_live_2026")
    t_start = datetime.now(timezone.utc).isoformat()
    n_updated = n_skipped = n_failed = 0
    prov_mark = 0  # translations already recorded to provenance_log

    def log_province():
        nonlocal prov_mark
        done_now = n_updated - prov_mark
        if done_now <= 0:
            return
        tdb.execute("""INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             fields_populated, records_attempted, status)
            VALUES (?,?,?,?,?,?,?,?)""",
            (src, "_geocode_all_roundrobin.py (translate_worker)", t_start,
             datetime.now(timezone.utc).isoformat(), done_now,
             "name_english,street_en,city_en,state_en", done_now, "completed"))
        tdb.commit()
        prov_mark = n_updated

    while True:
        item = tr_q.get()
        if item is None:
            break
        batch = [item]
        while len(batch) < TR_BATCH and not tr_q.empty():
            try:
                nxt = tr_q.get_nowait()
                if nxt is None:      # shutdown sentinel seen mid-batch
                    tr_q.put(nxt)    # put it back for the outer loop to consume
                    break
                batch.append(nxt)
            except Exception:
                break
        # build translation tasks: name + any non-Latin/foreign address fields
        tasks = []          # (church_id, field, original)
        for it in batch:
            chid, church_name, country, street, city, state = it
            if needs_translation(church_name, country):
                tasks.append((chid, "name", church_name))
            if needs_translation(street, country):
                tasks.append((chid, "street", street))
            if needs_translation(city, country):
                tasks.append((chid, "city", city))
            if needs_translation(state, country):
                tasks.append((chid, "state", state))
        if not tasks:
            continue
        names = [t[2] for t in tasks]
        outs = translate_names(names, provider=TR_PROVIDER, model=TR_MODEL)
        if outs is None:
            for cid, fld, _ in tasks:
                n_failed += 1
                print(f"[WARN] translate {cid} | {fld} | failed")
            continue
        now = datetime.now(timezone.utc).isoformat()
        name_triples = []     # (church_id, original, translation)
        addr_triples = []     # (church_id, component_type, original, translation)
        for (cid, fld, orig), tr in zip(tasks, outs):
            if fld == "name":
                name_triples.append((cid, orig, tr))
            else:
                addr_triples.append((cid, fld, orig, tr))
        # write translations with retry/rollback so a WAL lock can NEVER kill
        # this thread with an open transaction (which would hold the lock and
        # starve the main geocoder writer to death).
        written = False
        for _attempt in range(6):
            try:
                u, s, updated_ids = apply_name_translations(tdb, name_triples, src, now)
                au, as_, addr_updated_ids = apply_address_translations(tdb, addr_triples, src, now)
                tdb.commit()
                written = True
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and _attempt < 5:
                    try:
                        tdb.rollback()
                    except Exception:
                        pass
                    wt = min(30, 0.5 * (2 ** _attempt))
                    print(f"\n  [WARN] translate DB locked, retry {_attempt+1}/6 after {wt}s...")
                    time.sleep(wt)
                    continue
                print(f"\n  [WARN] translate DB write failed: {e}")
                try:
                    tdb.rollback()
                except Exception:
                    pass
                break
        if not written:
            n_failed += len(tasks)
            continue
        n_updated += u + au
        n_skipped += s + as_
        upd = set(updated_ids)
        for cid, orig, tr in name_triples:   # turn the dot's light on (after the move)
            if cid in upd:
                flash_live(cid, orig, tr, TR_PROVIDER)
        # flash address translations: group per church so the globe updates once
        addr_by_cid = {}
        for (cid, fld, orig, tr) in addr_triples:
            if tr and tr.strip().lower() != (orig or "").strip().lower():
                addr_by_cid.setdefault(cid, {})[fld] = tr
        for cid, comps in addr_by_cid.items():
            flash_addr_live(cid, comps, TR_PROVIDER)
        with slock:
            stats["_translated"] = {"n": n_updated, "skip": n_skipped, "err": n_failed}
        if n_updated - prov_mark >= 500:
            log_province()
    log_province()  # final flush on shutdown
    tdb.close()


def main():
    global _progress_open
    print("=" * 70)
    print("MULTI-PROVIDER LIVE NOMINATIM BACKFILL (round-robin)")
    print("=" * 70)
    mode = ("DRY-RUN" if DRY_RUN else
            ("IDS-FILE " + IDS_FILE if IDS_FILE else
             ("RANDOM " + str(RANDOM_N) if RANDOM_N else
              ("RANDOMIZE" if RANDOMIZE_ALL else
               ("LIMIT " + str(LIMIT) if LIMIT else "ALL")))))
    provs = ", ".join(p["name"] for p in PROVIDERS)
    print(f"mode: {mode}   providers: {provs}   skip-months: {SKIP_MONTHS} (cutoff {cutoff_month()})")
    print(f"expected rate: {len(PROVIDERS)*1/RATE_DELAY:.1f} req/s")

    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=600000")
    db.execute("PRAGMA cache_size=-1000000")  # 1 GB page cache (huge DB)
    db.execute("""CREATE TABLE IF NOT EXISTS nominatim_geocode_log (
        church_id INTEGER PRIMARY KEY,
        processed_at TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('success','no_city','no_result','http_error','exception')),
        street TEXT, city TEXT, state TEXT, zip TEXT,
        new_lat REAL, new_lon REAL, snap_m REAL, country TEXT
    )""")
    db.commit()

    cut = cutoff_month()

    print("\n[1] Selecting targets (GPS, no street, not geocoded since cutoff)...")
    common = """
        WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
          AND c.id NOT IN (SELECT church_id FROM nominatim_geocode_log WHERE processed_at >= ?)
          AND NOT EXISTS (
            SELECT 1 FROM church_addresses ca
            JOIN address_components ac ON ca.address_id=ac.address_id AND ac.component_type='street'
            WHERE ca.church_id=c.id AND ca.is_current=1 AND ac.component_value IS NOT NULL
              AND ac.component_value!='')
    """
    if IDS_FILE:
        with open(IDS_FILE) as f:
            ids = json.load(f)
        ids = sorted(set(int(x) for x in ids))
        # Resumability for THIS forward re-pass: skip only ids already corrected
        # by this forward pass (tracked in us_forward_done), NOT the historical
        # nominatim_geocode_log -- those are the very reverse-address churches we
        # are re-forwarding, so they must NOT be skipped.
        db.execute("CREATE TABLE IF NOT EXISTS us_forward_done "
                   "(church_id INTEGER PRIMARY KEY)")
        _done = {r[0] for r in db.execute("SELECT church_id FROM us_forward_done")}
        if _done:
            _before = len(ids)
            ids = [i for i in ids if i not in _done]
            if len(ids) < _before:
                print(f"  [resume] skipping {_before - len(ids):,} already forward-corrected")
        # chunk to stay under SQLite's variable limit (SQLITE_MAX_VARIABLE_NUMBER)
        rows = []
        CH = 2000
        for _i in range(0, len(ids), CH):
            _chunk = ids[_i:_i + CH]
            _ph = ",".join("?" for _ in _chunk)
            rows.extend(db.execute(
                "SELECT c.id, c.name, c.latitude, c.longitude, l.country, c.name_english "
                "FROM churches c LEFT JOIN church_location l ON c.id=l.church_id "
                f"WHERE c.id IN ({_ph})", _chunk).fetchall())
        print(f"  ids-file: {IDS_FILE} ({len(ids)} ids, {len(rows)} matched)")
    elif RANDOM_N:
        rows = db.execute("SELECT c.id, c.name, c.latitude, c.longitude, l.country, c.name_english "
                          "FROM churches c LEFT JOIN church_location l ON c.id=l.church_id "
                          + common + " ORDER BY RANDOM() LIMIT ?", (cut, RANDOM_N)).fetchall()
    elif RANDOMIZE_ALL:
        rows = db.execute("SELECT c.id, c.name, c.latitude, c.longitude, l.country, c.name_english "
                          "FROM churches c LEFT JOIN church_location l ON c.id=l.church_id "
                          + common + " ORDER BY RANDOM()", (cut,)).fetchall()
    else:
        rows = db.execute("SELECT c.id, c.name, c.latitude, c.longitude, l.country, c.name_english "
                          "FROM churches c LEFT JOIN church_location l ON c.id=l.church_id "
                          + common + " ORDER BY c.id", (cut,)).fetchall()
    targets = list(rows)
    print(f"  targets: {len(targets):,}")
    if LIMIT:
        targets = targets[:LIMIT]
        print(f"  limited to {len(targets):,}")

    if DRY_RUN:
        print("\n  sample:")
        for r in targets[:10]:
            print(f"    [{r[0]}] {str(r[1])[:50]} ({r[2]:.4f}, {r[3]:.4f})")
        rate = len(PROVIDERS) / RATE_DELAY
        print(f"  ETA: {len(targets)/rate/3600:.1f}h at {rate:.1f} req/s")
        print("  (re-run without --dry-run to process)")
        db.close()
        return

    if not targets:
        print("\n[SKIP] nothing to do - backlog clear or all recently checked")
        db.close()
        return

    # ── launch workers ─────────────────────────────────────────────────
    rate = len(PROVIDERS) / RATE_DELAY
    print(f"\n[2] Processing {len(targets):,} via {len(PROVIDERS)} providers "
          f"(~{rate:.1f} req/s, ETA {len(targets)/rate/3600:.1f}h)...")
    now = datetime.now(timezone.utc).isoformat()
    work_q = Queue()
    for t in targets:
        work_q.put(t)
    res_q = Queue()
    stats = {p["name"]: {"n": 0, "ok": 0, "empty": 0, "err": 0} for p in PROVIDERS}
    if EARTH_KEY:
        stats["geocode.earth"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    if REPORTALL_KEY:
        stats["reportall"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    if TAMU_KEY:
        stats["tamu"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    if TOMTOM_KEY:
        stats["tomtom"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    if MAPBOX_KEY:
        stats["mapbox"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    if AMBEE_KEY:
        stats["ambee"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    if CHIBIGEO_KEY:
        stats["chibigeo"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["osm_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["photon_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["mapsco_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["mapbox_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["earth_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["ban_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["foursquare_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["vk_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["chibigeo_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["_rescued"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    slock = threading.Lock()
    threads = []
    for p in PROVIDERS:
        th = threading.Thread(target=worker, args=(p, work_q, res_q, stats, slock), daemon=True)
        th.start()
        threads.append(th)
    tr_q = Queue()
    tr_th = None
    if TRANSLATE:
        tr_th = threading.Thread(target=translate_worker,
                                 args=(tr_q, stats, slock), daemon=True)
        tr_th.start()
        print(f"  [translate] {TR_PROVIDER} name translation ON (batch {TR_BATCH})")
    # inline US Census normalization stage (parallel, 1 req/s); disabled by --no-census
    census_q = Queue()
    census_th = None
    if CENSUS_ENABLED:
        census_th = threading.Thread(target=census_worker,
                                     args=(census_q, stats, slock), daemon=True)
        census_th.start()
        print("  [census] US address normalization ON (1 req/s, parallel)")
    else:
        print("  [census] DISABLED (--no-census) — will batch later")

    # ── single writer thread: drain results -> DB + live globe ─────────
    t0 = time.time()
    done = ok = no_result = err = wrong_gps = skipped_complete = 0
    changes = []
    log_rows = []
    census_pending = []
    while done < len(targets):
        chid, name, lat, lon, res, winner, tried, eng = res_q.get()
        done += 1
        status = post_result(db, now, chid, name, lat, lon, res, winner, tried, changes, log_rows)
        # mark this church as done for THIS forward pass (resumability marker)
        db.execute("INSERT OR IGNORE INTO us_forward_done (church_id) VALUES (?)", (chid,))
        # queue US addresses for the parallel Census normalization stage.
        # Enqueued here but only FLUSHED after commit (below) so the census
        # worker never races the writer's uncommitted raw address. Skipped when
        # census is disabled (--no-census).
        if (CENSUS_ENABLED and status == "success" and res and res.get("street")
                and (res.get("country") or "").upper()
                in ("US", "USA", "UNITED STATES", "")):
            census_pending.append((chid, res.get("street"), res.get("city"),
                                   res.get("state"), res.get("postcode")))
        print_entry(chid, name, lat, lon, res, winner, status)
        if status == "success":
            ok += 1
            feed_live(chid, name, lat, lon, res, "ok", "all", winner, eng)
        elif status == "skip_complete":
            # authoritative complete address — do NOT overwrite. If census is
            # enabled, still Census-normalize it (USPS + Tiger coords).
            skipped_complete += 1
            if CENSUS_ENABLED:
                _cc = _current_components(db, chid)
                census_pending.append((chid, _cc.get("street"), _cc.get("city"),
                                       _cc.get("state"), _cc.get("postcode")))
            feed_live(chid, name, lat, lon, None, "skip", "all", None, eng)
        elif status == "wrong_gps":
            wrong_gps += 1
            feed_live(chid, name, lat, lon, res, "warn", "all", winner, eng)
        elif status == "no_result":
            no_result += 1
            feed_live(chid, name, lat, lon, res, "empty", "all", None, eng)
        else:
            err += 1
            feed_live(chid, name, lat, lon, None, "error", "all", None, eng)
        if TRANSLATE:
            _rc = res or {}
            _country = _rc.get("country", "")
            if (needs_translation(name, _country)
                    or needs_translation(_rc.get("street", ""), _country)
                    or needs_translation(_rc.get("city", ""), _country)
                    or needs_translation(_rc.get("state", ""), _country)):
                tr_q.put((chid, name, _country, _rc.get("street", ""),
                          _rc.get("city", ""), _rc.get("state", "")))
        if done % 10 == 0 or done == len(targets):
            db.executemany("""INSERT OR REPLACE INTO nominatim_geocode_log
                (church_id, processed_at, status, street, city, state, zip,
                 new_lat, new_lon, snap_m, country)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", log_rows)
            if changes:
                db.executemany("""INSERT INTO enrichment_change_log
                    (church_id, field_name, old_value, new_value, change_source, changed_at)
                    VALUES (?,?,?,?,?,?)""",
                    [(cid, f, o, n, SOURCE, now) for cid, f, o, n in changes])
            db.commit()
            # flush this batch's addresses to the census normalizer now that the
            # raw address is committed (avoids a race with the writer's txn)
            if census_pending:
                for _it in census_pending:
                    census_q.put(_it)
                census_pending.clear()
            log_rows = []
            changes = []
            if done % 2000 == 0:
                db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        if done % 5 == 0 or done == len(targets):
            pct = done / len(targets) * 100
            eta_h = (len(targets) - done) / rate / 3600
            sp = {k: f"{v['ok']}/{v['n']}" for k, v in stats.items()
                  if k not in ("_rescued", "_translated")}
            print(f"\r  [{pct:5.1f}%] {done}/{len(targets)}  ok={ok}  no_addr={no_result}  "
                  f"err={err}  wrong_gps={wrong_gps}  skip={skipped_complete}  "
                  f"rescued={stats['_rescued']['n']}  "
                  f"elapsed={time.time()-t0:.0f}s  eta={eta_h:.1f}h  "
                  f"per={sp}", end="", flush=True)
            _progress_open = True
    print()

    # stop workers
    for _ in threads:
        work_q.put(None)
    if tr_th is not None:
        tr_q.put(None)
        tr_th.join()
        tr = stats.get("_translated", {})
        print(f"  [translate] {TR_PROVIDER}: updated={tr.get('n', 0)} "
              f"skipped={tr.get('skip', 0)} failed={tr.get('err', 0)}")
    if census_th is not None:
        census_q.put(None)
        census_th.join()
        cs = stats.get("census", {})
        print(f"  [census] normalized={cs.get('ok',0)} "
              f"no_match={cs.get('err',0)} total={cs.get('n',0)}")

    db.execute("""
        INSERT INTO provenance_log
          (source, script_name, started_at, completed_at, churches_updated,
           fields_populated, records_attempted, status)
        VALUES (?,?,?,?,?,?,?,?)""",
        (SOURCE, "_geocode_all_roundrobin.py", now, datetime.now(timezone.utc).isoformat(),
         ok, "street,city,state,postcode,country", len(targets), "completed"))
    db.commit()
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    print(f"\n[SUMMARY] {len(targets):,} in {time.time()-t0:.0f}s "
          f"(ok {ok}, no_address {no_result}, errors {err}, wrong_gps {wrong_gps}, "
          f"skip_complete {skipped_complete})")
    for k, v in stats.items():
        if k == "_rescued":
            print(f"  rescued by failover: {v['n']} sites")
            continue
        if k == "_translated":
            continue
        print(f"  provider {k}: {v['n']} req, {v['ok']} ok, {v['empty']} no_addr, {v['err']} err")
    print("  results posted to churches.db + live globe (http://127.0.0.1:8765)")
    db.close()
    print("\nDONE")


if __name__ == "__main__":
    main()

"""_geocode_all_roundrobin.py — Multi-provider live Nominatim backfill (3x speed).

Same pipeline as _geocode_all_live.py but runs ONE WORKER THREAD PER PROVIDER in
round-robin, so we can poll 3 public geocoders concurrently while keeping each
provider within its own 1 req/s policy:

    provider A  nominatim.openstreetmap.org   (Nominatim JSON, 1 req/s)
    provider B  nominatim.geocoding.ai        (Nominatim JSON, 1 req/s)
    provider C  photon.komoot.io              (Photon JSON,   1 req/s)

Order: FORWARD name search FIRST (tight 0.5 km box) -> reverse hunt
(geocode.earth -> tomtom -> mapbox -> reportall (US) -> tamu (US) -> ambee)
-> loose 2 km name search last. The forward pass returns the church POI's OWN
address (most accurate); reverse is the safe proxy fallback; the loose 2 km
name search is the last-resort rescue. Forward winners logged as
osm_search / photon_search.

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
RATE_DELAY = 2.0  # per-provider policy: max 1 req/s (increased to reduce 429s)
SOURCE = "nominatim_live_all_2026"
UA = "GRID/1.0 (https://github.com/grid; academic research; contact charles@gridataset.com)"
# geocode.maps.co free plan: 25K @ 5 req/s then 1 req/s. We run it at 1 req/s.
GEOMAPCO_KEY = os.environ.get("GEOMAPCO_API_KEY", "6812538a6a350959687023hqb35f651")
# geocode.earth (Pelias) - used ONLY as a failover when a primary provider
# errors out or returns no street (saves quota: fires only on misses).
# Key set as a Windows USER env var (GEOCODE_EARTH_API_KEY) - never hardcoded.
EARTH_KEY = os.environ.get("GEOCODE_EARTH_API_KEY", "")
# ReportAll (US parcel data) - final US-only failover for parcel-grade addresses.
REPORTALL_KEY = os.environ.get("REPORTALL_CLIENT_KEY", "0jf9knnTiz")
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
AMBEE_DAILY = 100
AMBEE_QUOTA_FILE = "E:/grid/data/staging/ambee_quota.json"
_ambee_q_lock = threading.Lock()
# Positionstack (global reverse + forward) - 100 uses/month free tier.
# Key set as a Windows USER env var (POSITIONSTACK_API_KEY) - never hardcoded.
POSITIONSTACK_KEY = os.environ.get("POSITIONSTACK_API_KEY", "")
# Maptiler (global reverse + forward) - generous free tier.
# Key set as a Windows USER env var (MAPTILER_API_KEY) - never hardcoded.
MAPTILER_KEY = os.environ.get("MAPTILER_API_KEY", "")
# Geocode.xyz (global reverse + forward, free tier is rate-limited).
# Key set as a Windows USER env var (GEOCODEXYZ_API_KEY) - never hardcoded.
GEOCODEXYZ_KEY = os.environ.get("GEOCODEXYZ_API_KEY", "")
# Geocodify (global reverse + forward).
# Key set as a Windows USER env var (GEOCODIFY_API_KEY) - never hardcoded.
GEOCODIFY_KEY = os.environ.get("GEOCODIFY_API_KEY", "")
# OS Data Hub (Ordnance Survey) Places API - GB-only authoritative reverse.
# Key set as a Windows USER env var (OS_DATAHUB_API_KEY) - never hardcoded.
OS_PLACES_KEY = os.environ.get("OS_DATAHUB_API_KEY", "")
# OpenRouteService (HeiGIT) - global reverse + forward geocoder.
# Key set as a Windows USER env var (ORS_API_KEY) - never hardcoded.
ORS_KEY = os.environ.get("ORS_API_KEY", "")
POSITIONSTACK_MONTHLY = 100
POSITIONSTACK_QUOTA_FILE = "E:/grid/data/staging/positionstack_quota.json"
_posstack_q_lock = threading.Lock()


def positionstack_quota_take():
    """Atomically check + consume one Positionstack monthly call (100/month)."""
    with _posstack_q_lock:
        ym = datetime.now(timezone.utc).strftime("%Y-%m")
        used = 0
        try:
            with open(POSITIONSTACK_QUOTA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("month") == ym:
                used = d.get("used", 0)
        except Exception:
            pass
        if used >= POSITIONSTACK_MONTHLY:
            return False
        os.makedirs(os.path.dirname(POSITIONSTACK_QUOTA_FILE), exist_ok=True)
        with open(POSITIONSTACK_QUOTA_FILE, "w", encoding="utf-8") as f:
            json.dump({"month": ym, "used": used + 1}, f)
        return True


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


for _p in PROVIDERS:
    _p["limiter"] = RateLimiter(RATE_DELAY)
EARTH_LIMITER = RateLimiter(RATE_DELAY)
REPORTALL_LIMITER = RateLimiter(RATE_DELAY)
TAMU_LIMITER = RateLimiter(RATE_DELAY)
TOMTOM_LIMITER = RateLimiter(RATE_DELAY)
MAPBOX_LIMITER = RateLimiter(RATE_DELAY)
AMBEE_LIMITER = RateLimiter(RATE_DELAY)
POSITIONSTACK_LIMITER = RateLimiter(RATE_DELAY)
MAPTILER_LIMITER = RateLimiter(RATE_DELAY)
GEOCODEXYZ_LIMITER = RateLimiter(2.0)  # geocode.xyz free tier throttles hard
GEOCODIFY_LIMITER = RateLimiter(RATE_DELAY)
OS_PLACES_LIMITER = RateLimiter(1.1)
ORS_LIMITER = RateLimiter(1.1)
# Forward name-search shares the SAME per-provider rate budget as the reverse
# calls (a second independent limiter could exceed 1 req/s on the shared host).
_OSM_LIMITER = next(p["limiter"] for p in ALL_PROVIDERS if p["name"] == "osm")
_PHOTON_LIMITER = next(p["limiter"] for p in ALL_PROVIDERS if p["name"] == "photon")

# ── geocode.earth circuit breaker ─────────────────────────────────────
# geocode.earth (Pelias) is a quota'd provider used ONLY as failover. Its free
# tier is small, so once it starts returning 429 we stop calling it for the
# rest of the run instead of burning requests + spamming the log.
EARTH_LOCK = threading.Lock()
EARTH_429S = 0
EARTH_DISABLED = False
EARTH_DISABLE_AFTER = 5  # consecutive 429s before we cut it off

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


def positionstack_call(lat, lon):
    POSITIONSTACK_LIMITER.wait()
    return reverse_positionstack(lat, lon)


def maptiler_call(lat, lon):
    MAPTILER_LIMITER.wait()
    return reverse_maptiler(lat, lon)


def geocodexyz_call(lat, lon):
    GEOCODEXYZ_LIMITER.wait()
    return reverse_geocodexyz(lat, lon)


def geocodify_call(lat, lon):
    GEOCODIFY_LIMITER.wait()
    return reverse_geocodify(lat, lon)


def os_places_call(lat, lon):
    OS_PLACES_LIMITER.wait()
    return reverse_os_places(lat, lon)


def ors_call(lat, lon):
    ORS_LIMITER.wait()
    return reverse_ors(lat, lon)


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


def reverse_mapsco(lat, lon):
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
        with urllib.request.urlopen(req, timeout=20) as r:
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


def reverse_positionstack(lat, lon):
    """Reverse geocode via Positionstack (global, 100 uses/month free tier)."""
    if not POSITIONSTACK_KEY:
        return None
    u = ("https://api.positionstack.com/v1/reverse?" + urllib.parse.urlencode(
        {"access_key": POSITIONSTACK_KEY, "query": f"{lat},{lon}"}))
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("error") or not data.get("data"):
            return None
        p = data["data"][0]
        street = " ".join(x for x in (p.get("number") or "", p.get("street") or "") if x)
        if not street:
            street = p.get("name") or ""
        return {
            "street": street,
            "city": p.get("locality") or p.get("county") or "",
            "state": p.get("region") or p.get("region_code") or "",
            "postcode": p.get("postal_code") or "",
            "country": p.get("country") or "",
            "nom_lat": float(p.get("latitude", lat)),
            "nom_lon": float(p.get("longitude", lon)),
        }
    except Exception as e:
        print(f"\n  [WARN] positionstack error for {lat},{lon}: {e}")
        return None


def reverse_maptiler(lat, lon):
    """Reverse geocode via Maptiler (global, generous free tier)."""
    if not MAPTILER_KEY:
        return None
    u = (f"https://api.maptiler.com/geocoding/{lon:.6f},{lat:.6f}.json?key="
         + MAPTILER_KEY)
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        feats = data.get("features") or []
        if not feats:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        p = feats[0].get("properties") or {}
        add = p.get("address") or {}
        hn = add.get("housenumber") or ""
        st = add.get("street") or ""
        street = f"{hn} {st}".strip() if (hn or st) else ""
        return {
            "street": street,
            "city": p.get("locality") or p.get("place") or "",
            "state": p.get("region") or "",
            "postcode": p.get("postcode") or "",
            "country": p.get("country") or "",
            "nom_lat": lat, "nom_lon": lon,
        }
    except Exception as e:
        print(f"\n  [WARN] maptiler error for {lat},{lon}: {e}")
        return None


def reverse_geocodexyz(lat, lon):
    """Reverse geocode via Geocode.xyz (global, free tier is rate-limited).
    API: geocode.xyz/{lat},{lon}?auth=KEY&geoit=json
    Returns the standard result dict or None."""
    if not GEOCODEXYZ_KEY:
        return None
    u = (f"https://geocode.xyz/{lat:.6f},{lon:.6f}?auth={GEOCODEXYZ_KEY}"
         + "&geoit=json")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
        if "error" in data or not data.get("city"):
            return None
        street = " ".join(x for x in (data.get("stnumber") or "",
                                       data.get("staddress") or "") if x)
        return {
            "street": street,
            "city": data.get("city") or "",
            "state": data.get("state") or data.get("prov") or "",
            "postcode": data.get("postal") or "",
            "country": data.get("country") or "",
            "nom_lat": float(data.get("latt", lat)),
            "nom_lon": float(data.get("longt", lon)),
        }
    except Exception as e:
        print(f"\n  [WARN] geocode.xyz error for {lat},{lon}: {e}")
        return None


def reverse_geocodify(lat, lon):
    """Reverse geocode via Geocodify (global).
    API: api.geocodify.com/v2/reverse?api_key=KEY&lat=..&lng=..
    Returns the standard result dict or None."""
    if not GEOCODIFY_KEY:
        return None
    u = ("https://api.geocodify.com/v2/reverse?" + urllib.parse.urlencode(
        {"api_key": GEOCODIFY_KEY, "lat": lat, "lng": lon}))
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
        street = f"{hn} {st}".strip() if (hn or st) else (p.get("label") or "")
        return {
            "street": street,
            "city": p.get("city") or p.get("locality") or "",
            "state": p.get("state") or "",
            "postcode": p.get("postcode") or "",
            "country": p.get("country") or "",
            "nom_lat": float(p.get("lat", lat)),
            "nom_lon": float(p.get("lon", lon)),
        }
    except Exception as e:
        print(f"\n  [WARN] geocodify error for {lat},{lon}: {e}")
        return None


def reverse_os_places(lat, lon):
    """Reverse geocode via OS Data Hub Places API (Ordnance Survey, GB-only,
    authoritative address data).
    API: api.os.uk/search/places/v1/reverse?point=LON,LAT&key=KEY
    Returns the standard result dict or None."""
    if not OS_PLACES_KEY:
        return None
    u = ("https://api.os.uk/search/places/v1/reverse?" + urllib.parse.urlencode(
        {"point": f"{lon},{lat}", "key": OS_PLACES_KEY, "maxresults": 1,
         "output_srs": "EPSG:4326"}))
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = data.get("results") or []
        if not results:
            return {"street": "", "city": "", "state": "", "postcode": "",
                    "country": "", "nom_lat": lat, "nom_lon": lon}
        dpa = results[0].get("DPA") or {}
        street = " ".join(x for x in (dpa.get("BUILDING_NUMBER") or "",
                                       dpa.get("THOROUGHFARE_NAME") or "") if x)
        return {
            "street": street,
            "city": dpa.get("POST_TOWN") or dpa.get("DEPENDENT_LOCALITY") or "",
            "state": dpa.get("LOCAL_CUSTODIAN_CODE") or "",
            "postcode": dpa.get("POSTCODE") or "",
            "country": "United Kingdom",
            "nom_lat": float(dpa.get("LATITUDE", lat)),
            "nom_lon": float(dpa.get("LONGITUDE", lon)),
        }
    except Exception as e:
        print(f"\n  [WARN] os_places error for {lat},{lon}: {e}")
        return None


def reverse_ors(lat, lon):
    """Reverse geocode via OpenRouteService (HeiGIT, global).
    API: api.heigit.org/geocode/reverse?point=LON,LAT&api_key=KEY&size=1
    Returns the standard result dict or None."""
    if not ORS_KEY:
        return None
    u = ("https://api.heigit.org/geocode/reverse?" + urllib.parse.urlencode(
        {"point": f"{lon},{lat}", "api_key": ORS_KEY, "size": 1}))
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
        street = f"{hn} {st}".strip() if (hn or st) else (p.get("name") or "")
        geom = feats[0].get("geometry") or {}
        coords = geom.get("coordinates") or []
        return {
            "street": street,
            "city": p.get("locality") or p.get("city") or "",
            "state": p.get("region") or "",
            "postcode": p.get("postalcode") or "",
            "country": p.get("country") or "",
            "nom_lat": coords[1] if len(coords) > 1 else lat,
            "nom_lon": coords[0] if coords else lon,
        }
    except Exception as e:
        print(f"\n  [WARN] ors error for {lat},{lon}: {e}")
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
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
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
                "name": hit.get("display_name", ""),
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
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
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
                "name": props.get("name") or "",
                "nom_lat": lat2, "nom_lon": lon2,
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
        for sname, sfunc in (
                ("osm_search",
                 lambda: forward_nominatim_search(church_name, eng, lat, lon, country,
                                                  radius=PRIMARY_SEARCH_RADIUS_KM)),
                ("photon_search",
                 lambda: forward_photon_search(church_name, eng, lat, lon,
                                               radius=PRIMARY_SEARCH_RADIUS_KM))):
            fres = sfunc()
            classify(sname, fres)
            absorb(sname, fres)
            tried.append(sname)
            if numbered_street(res):
                break
        rescued = _rc_before  # forward is the PRIMARY source — not "rescued"
        # 2) REVERSE HUNT (safe proxy): only when forward found no numbered
        #    street (name too generic/translated or POI unindexed). Reverse
        #    can only describe the actual point, so it's the deterministic
        #    fallback. Keep asking providers until one returns a proper
        #    numbered street address (e.g. '123 Main St'), merging the best
        #    components from each along the way. A bare 'Main St' without a
        #    house number can't locate a building, so we keep rolling.
        if not numbered_street(res):
            res0 = provider_call(prov, lat, lon)
            classify(name, res0)
            absorb(name, res0)   # merge into any partial forward result
            tried.append(name)
            for p2 in others:
                r2 = provider_call(p2, lat, lon)
                classify(p2["name"], r2)
                absorb(p2["name"], r2)
                tried.append(p2["name"])
                if numbered_street(res):
                    break
            if not numbered_street(res) and EARTH_KEY:
                re_ = earth_call(lat, lon)
                classify("geocode.earth", re_)
                absorb("geocode.earth", re_)
                tried.append("geocode.earth")
            if not numbered_street(res) and TOMTOM_KEY:
                tt = tomtom_call(lat, lon)
                classify("tomtom", tt)
                absorb("tomtom", tt)
                tried.append("tomtom")
            if not numbered_street(res) and MAPBOX_KEY:
                mb = mapbox_call(lat, lon)
                classify("mapbox", mb)
                absorb("mapbox", mb)
                tried.append("mapbox")
            if not numbered_street(res) and country == "US" and REPORTALL_KEY:
                rr = reportall_call(lat, lon)
                classify("reportall", rr)
                absorb("reportall", rr)
                tried.append("reportall")
            if not numbered_street(res) and country == "US" and TAMU_KEY:
                tm = tamu_call(lat, lon)
                classify("tamu", tm)
                absorb("tamu", tm)
                tried.append("tamu")
            if not numbered_street(res) and AMBEE_KEY:
                if ambee_quota_take():
                    am = ambee_call(lat, lon)
                    classify("ambee", am)
                    absorb("ambee", am)
                    tried.append("ambee")
            if not numbered_street(res) and POSITIONSTACK_KEY:
                if positionstack_quota_take():
                    ps = positionstack_call(lat, lon)
                    classify("positionstack", ps)
                    absorb("positionstack", ps)
                    tried.append("positionstack")
            if not numbered_street(res) and MAPTILER_KEY:
                mt = maptiler_call(lat, lon)
                classify("maptiler", mt)
                absorb("maptiler", mt)
                tried.append("maptiler")
            if not numbered_street(res) and GEOCODEXYZ_KEY:
                gx = geocodexyz_call(lat, lon)
                classify("geocode.xyz", gx)
                absorb("geocode.xyz", gx)
                tried.append("geocode.xyz")
            if not numbered_street(res) and GEOCODIFY_KEY:
                gd = geocodify_call(lat, lon)
                classify("geocodify", gd)
                absorb("geocodify", gd)
                tried.append("geocodify")
            if not numbered_street(res) and OS_PLACES_KEY and country == "GB":
                op = os_places_call(lat, lon)
                classify("os_places", op)
                absorb("os_places", op)
                tried.append("os_places")
            if not numbered_street(res) and ORS_KEY:
                ors = ors_call(lat, lon)
                classify("ors", ors)
                absorb("ors", ors)
                tried.append("ors")
            # 3) US-only: if still no numbered street, try TAMU as a final
            #    US-specific pass (TAMU has excellent US parcel/TIGER coverage).
            if not numbered_street(res) and country == "US" and TAMU_KEY:
                tm = tamu_call(lat, lon)
                classify("tamu", tm)
                absorb("tamu", tm)
                tried.append("tamu")
        # 4) LOOSE NAME RESCUE: reverse also found nothing — gamble on a
        #    same-name worship-class result up to SEARCH_RADIUS_KM (2 km).
        #    Last resort only; the tight forward pass already tried close range.
        if not numbered_street(res):
            for sname, sfunc in (
                    ("osm_search",
                     lambda: forward_nominatim_search(church_name, eng, lat, lon, country)),
                    ("photon_search",
                     lambda: forward_photon_search(church_name, eng, lat, lon))):
                fres = sfunc()
                classify(sname, fres)
                absorb(sname, fres)
                tried.append(sname)
                if numbered_street(res):
                    break
        if rescued:
            with slock:
                stats["_rescued"]["n"] += 1
        res_q.put((chid, church_name, lat, lon, res, winner, tried, eng))
        work_q.task_done()


def post_result(db, now, chid, name, lat, lon, res, winner, tried, changes, log_rows):
    """Apply one result to the DB (called from the single writer thread).

    geocode_source is set to the WINNING provider; every provider that was
    queried but did not win is logged as an enrichment pass
    (field_name='geocode_pass') so the hunt is fully auditable.

    Retries on database lock errors with exponential backoff.
    """
    import time
    max_retries = 10
    for attempt in range(max_retries):
        try:
            if res:
                dist_m = round(math.sqrt((res["nom_lat"] - lat) ** 2 +
                                         (res["nom_lon"] - lon) ** 2) * 111320.0, 1)
                status = "success" if res["street"] else "no_result"
                comps = {}
                if res["street"]:
                    comps["street"] = res["street"]
                for k in ("city", "state", "postcode", "country"):
                    if res[k]:
                        comps[k] = res[k]
                if comps:
                    set_components(db, chid, comps, update_legacy=False)
                    if winner:
                        db.execute("UPDATE church_addresses SET geocode_source=?, "
                                   "source='nominatim_live' "
                                   "WHERE church_id=? AND is_current=1", (winner, chid))
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
    tdb.execute("PRAGMA busy_timeout=120000")
    tdb.execute("PRAGMA synchronous=NORMAL")
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
    db.execute("PRAGMA busy_timeout=120000")
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
        ph = ",".join("?" for _ in ids)
        rows = db.execute(
            "SELECT c.id, c.name, c.latitude, c.longitude, l.country, c.name_english "
            "FROM churches c LEFT JOIN church_location l ON c.id=l.church_id "
            f"WHERE c.id IN ({ph})", ids).fetchall()
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
    stats["osm_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
    stats["photon_search"] = {"n": 0, "ok": 0, "empty": 0, "err": 0}
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

    # ── single writer thread: drain results -> DB + live globe ─────────
    t0 = time.time()
    done = ok = no_result = err = 0
    changes = []
    log_rows = []
    while done < len(targets):
        chid, name, lat, lon, res, winner, tried, eng = res_q.get()
        done += 1
        status = post_result(db, now, chid, name, lat, lon, res, winner, tried, changes, log_rows)
        print_entry(chid, name, lat, lon, res, winner, status)
        if status == "success":
            ok += 1
            feed_live(chid, name, lat, lon, res, "ok", "all", winner, eng)
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
                  f"err={err}  rescued={stats['_rescued']['n']}  "
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
          f"(ok {ok}, no_address {no_result}, errors {err})")
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

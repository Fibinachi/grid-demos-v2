"""_recover_shared_coords_v2.py — Recover original coordinates + addresses for
churches that share coordinates (many are centroids).

v2 FIX (name-anchored + state-consistency check):
  The v1 approach trusted stored address components as anchors, but those are
  THEMSELVES corrupted in bad merges. Example: church 547 "FIRST BAPTIST CHURCH
  OF WASHINGTON MICHIGAN" had address "109 North Mill Street, Colfax WA" — the
  name says MICHIGAN, the address says WASHINGTON. Trusting the address moved
  the church to the wrong state.

  The church NAME is the most reliable signal. New strategy per church:
    1. Extract a STATE HINT from the name (full state name or abbreviation).
       e.g. "WASHINGTON MICHIGAN" -> MI, "BATTLE CREEK" -> MI, "BAKER CITY" -> OR.
       This is ground truth for the state.
    2. NAME-ANCHORED search (unbounded, country-scoped) via the multi-source
       failover. Finds known POIs like "Baker City SDA Church".
    3. If name search fails, use ADDRESS-ANCHORED search — but ONLY if the
       address's state matches the name's state hint. If they CONFLICT, the
       address is corrupted -> route to a review queue (never blindly apply).
    4. No state hint in name -> fall back to address-anchored as before.

Usage:
  python _recover_shared_coords_v2.py --dry-run        # count + sample only
  python _recover_shared_coords_v2.py --limit 50       # test 50
  python _recover_shared_coords_v2.py --write          # apply changes
  python _recover_shared_coords_v2.py --review         # dump review queue only
"""
import json
import math
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r"E:\grid")
from scripts.grid_address import set_components  # noqa: E402

DB = "E:/grid/churches.db"
SOURCE = "shared_coord_recovery_v2_2026"
UA = "GRID/1.0 (https://github.com/grid; academic research; contact charles@gridataset.com)"
REVIEW_JSON = "E:/grid/data/shared_coord_review_queue.json"
# Minimum distance (km) a recovered result must move the church off its
# centroid before we apply it. Below this, the "recovery" is just centroid
# churn and would overwrite good data with no real improvement.
MIN_MOVE_KM = 0.1  # 100 m

# Reuse helpers + forward-name providers from the round-robin module.
from _geocode_all_roundrobin_fixed_foursquare import (  # noqa: E402
    build_street, extract_city, numbered_street, looks_like_worship,
    _dist_km, _viewbox_around, _get_json_retry, _OSM_LIMITER,
    forward_nominatim_search, forward_photon_search, forward_foursquare_search,
    forward_mapsco_search, forward_earth_search, forward_ban_search,
    forward_vk_search, forward_chibigeo_search, forward_geocodio_search,
    forward_locationiq_search, forward_mapbox_search,
    FOURSQUARE_KEY, CHIBIGEO_KEY, GEOCODIO_KEY, LOCATIONIQ_KEY,
)

WRITE = "--write" in sys.argv
DRY = "--dry-run" in sys.argv
REVIEW_ONLY = "--review" in sys.argv
LIMIT = None
for i, a in enumerate(sys.argv):
    if a.startswith("--limit="):
        LIMIT = int(a.split("=")[1])
    elif a == "--limit" and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])

# ── US state extraction ──────────────────────────────────────────────────────
US_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN',
    'IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH',
    'NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT',
    'VT','VA','WA','WV','WI','WY','AS','GU','MP','PR','VI'
}
# Full state name -> abbreviation
FULL_STATE = {
    'ALABAMA':'AL','ALASKA':'AK','ARIZONA':'AZ','ARKANSAS':'AR','CALIFORNIA':'CA',
    'COLORADO':'CO','CONNECTICUT':'CT','DELAWARE':'DE','FLORIDA':'FL','GEORGIA':'GA',
    'HAWAII':'HI','IDAHO':'ID','ILLINOIS':'IL','INDIANA':'IN','IOWA':'IA',
    'KANSAS':'KS','KENTUCKY':'KY','LOUISIANA':'LA','MAINE':'ME','MARYLAND':'MD',
    'MASSACHUSETTS':'MA','MICHIGAN':'MI','MINNESOTA':'MN','MISSISSIPPI':'MS',
    'MISSOURI':'MO','MONTANA':'MT','NEBRASKA':'NE','NEVADA':'NV','NEW HAMPSHIRE':'NH',
    'NEW JERSEY':'NJ','NEW MEXICO':'NM','NEW YORK':'NY','NORTH CAROLINA':'NC',
    'NORTH DAKOTA':'ND','OHIO':'OH','OKLAHOMA':'OK','OREGON':'OR','PENNSYLVANIA':'PA',
    'RHODE ISLAND':'RI','SOUTH CAROLINA':'SC','SOUTH DAKOTA':'SD','TENNESSEE':'TN',
    'TEXAS':'TX','UTAH':'UT','VERMONT':'VT','VIRGINIA':'VA','WASHINGTON':'WA',
    'WEST VIRGINIA':'WV','WISCONSIN':'WI','WYOMING':'WY'
}
# Sort full names by length desc so "NEW YORK" matches before "NEW"
_FULL_NAMES = sorted(FULL_STATE.keys(), key=len, reverse=True)

# 2-letter tokens that collide with US state codes but are common English
# words / abbreviations in church names — NOT state hints.
_NON_STATE_ABBR = {
    'DE', 'AL', 'OF', 'LA', 'EL', 'DA',   # foreign words (existing)
    'IN', 'MT', 'OR', 'ME', 'OK', 'HI',   # English words: in, Mt., or, me, ok, hi
    'AS', 'AT', 'BE', 'BY', 'DO', 'GO', 'HE', 'IF', 'IS', 'IT', 'NO', 'ON',
    'SO', 'TO', 'UP', 'US', 'WE', 'AM', 'AN', 'DR', 'ST', 'RD', 'AVE',
}


def extract_state_hint(name):
    """Extract a US state abbreviation from a church name, or None.
    Returns the LAST state match in the name — in "X OF CITY STATE" naming
    (e.g. "FIRST BAPTIST CHURCH OF WASHINGTON MICHIGAN") the trailing state is
    the actual location. Checks full state names first, then standalone 2-letter
    abbreviations. Returns (abbr, matched_text) or (None, None).

    Excludes common foreign words/prefixes that appear in church names:
    - DE (German "of", Spanish "of")
    - AL (Arabic "the", Alabama)
    - OF (English "of")
    - LA (Louisiana, but also Spanish "the")
    - EL (Spanish "the")
    - LA (Spanish "the")
    - DA (Portuguese "day")
    """
    if not name:
        return None, None
    up = name.upper()
    # Collect ALL full-state-name matches, keep the LAST one.
    last_full = None
    for full in _FULL_NAMES:
        for m in re.finditer(r'\b' + re.escape(full) + r'\b', up):
            last_full = (FULL_STATE[full], full, m.start())
    if last_full:
        return last_full[0], last_full[1]
    # 2-letter abbreviations as standalone words — keep the LAST one.
    # Exclude common English words / abbreviations that collide with state
    # codes and appear frequently in church names. These are NOT state hints.
    last_ab = None
    for m in re.finditer(r'\b([A-Z]{2})\b', up):
        ab = m.group(1)
        if ab in US_STATES and ab not in _NON_STATE_ABBR:
            last_ab = (ab, ab, m.start())
    if last_ab:
        return last_ab[0], last_ab[1]
    return None, None


def extract_city_state_hint(name):
    """Extract (city, state_abbr, state_text) from a church name when the name
    follows the common "... OF CITY STATE" or "... CITY STATE" pattern.
    Examples:
      'FIRST BAPTIST CHURCH OF WASHINGTON MICHIGAN' -> ('WASHINGTON', 'MI', 'MICHIGAN')
      'SAINT JOSEPH CATHOLIC PARISH CORPUS CHRISTI TEXAS' -> ('CORPUS CHRISTI', 'TX', 'TEXAS')
      'VIENNA PRESBYTERIAN CHURCH' -> ('VIENNA', 'IL', None)  # known city
    Returns (None, None, None) if no state/city is found."""
    if not name:
        return None, None, None
    state_hint, state_text = extract_state_hint(name)
    up = name.upper()
    if state_hint and state_text:
        m = re.search(r'\b' + re.escape(state_text) + r'\b', up)
        if m:
            prefix = up[:m.start()]
            words = prefix.strip().split()
            if words:
                # Try to find the longest known-city match ending at the
                # last word(s) before the state. This handles "CORPUS CHRISTI"
                # and "ORANGE GROVE" correctly.
                for n in range(min(4, len(words)), 0, -1):
                    candidate = ' '.join(words[-n:])
                    if candidate in _CITY_STATE:
                        return candidate, state_hint, state_text
                # Fallback: take all non-connector words immediately before
                # the state as the city. Skip trailing connectors like OF/IN/AT/THE.
                city_words = []
                for w in reversed(words):
                    if w in ('OF', 'IN', 'AT', 'CHURCH', 'THE'):
                        break
                    city_words.insert(0, w)
                if city_words:
                    return ' '.join(city_words), state_hint, state_text
                return None, state_hint, state_text
    # No explicit state in name — check if the name starts with a known city
    # whose state we know (e.g. 'VIENNA PRESBYTERIAN CHURCH' -> Vienna, IL).
    words = up.split()
    for n in range(min(4, len(words)), 0, -1):
        candidate = ' '.join(words[:n])
        if candidate in _CITY_STATE:
            return candidate, _CITY_STATE[candidate], None
    return None, None, None


# ── Shared-coordinate predicate ──────────────────────────────────────────────
SHARED_SQL = """
    (ROUND(c.latitude,5), ROUND(c.longitude,5)) IN (
        SELECT ROUND(latitude,5), ROUND(longitude,5) FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY ROUND(latitude,5), ROUND(longitude,5) HAVING COUNT(*) > 1
    )
"""


def load_targets(db):
    """Load shared-coord churches with their original anchors + log coords."""
    rows = db.execute(f"""
        SELECT
          c.id, c.name, c.latitude, c.longitude, l.country, l.state, l.zip,
          (SELECT ac.component_value FROM church_addresses ca
           JOIN address_components ac ON ac.address_id=ca.address_id
             AND ac.component_type='city'
           WHERE ca.church_id=c.id AND ca.is_current=1 LIMIT 1) AS city,
          (SELECT ac.component_value FROM church_addresses ca
           JOIN address_components ac ON ac.address_id=ca.address_id
             AND ac.component_type='street'
           WHERE ca.church_id=c.id AND ca.is_current=1 LIMIT 1) AS street,
          n.new_lat, n.new_lon, n.street AS log_street
        FROM churches c
        LEFT JOIN church_location l ON c.id = l.church_id
        LEFT JOIN nominatim_geocode_log n ON n.church_id = c.id
        WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
          AND {SHARED_SQL}
          AND EXISTS (
            SELECT 1 FROM church_addresses ca
            WHERE ca.church_id=c.id AND ca.is_current=1
              AND ca.geocode_source IS NULL
          )
    """).fetchall()
    return rows


def strip_html_fragments(s):
    """Remove broken HTML tag fragments and stray whitespace from a field.
    Handles '/>', '<br/>', '<br>', '<p>', '</p>', '<div>', etc. that leak into
    address components from botched merges. Also collapses newlines/tabs."""
    if not s:
        return s
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&amp;', '&', s)
    # Remove self-closing / broken tag fragments: '/>', '<br/>', '<br />', etc.
    s = re.sub(r'<\s*/?\s*[a-zA-Z][^>]*>', ' ', s)  # any <tag ...> or </tag>
    s = re.sub(r'/\s*>', ' ', s)                     # stray '/>' or '/ >'
    s = re.sub(r'[\r\n\t]+', ' ', s)                 # newlines/tabs -> space
    s = re.sub(r'\s+', ' ', s).strip()               # collapse whitespace
    return s


def classify_anchor(row):
    """Return (tier, parts, (street, city, state, zip_, country))."""
    cid, name, lat, lon, country, state, zip_, city, street, nl, no, log_street = row
    street = strip_html_fragments(street)
    city = strip_html_fragments(city)
    state = strip_html_fragments(state)
    zip_ = strip_html_fragments(zip_)
    country = strip_html_fragments(country)

    if street:
        parts = [p for p in [street, city, state, zip_] if p]
        return "street", parts, (street, city, state, zip_, country)
    if zip_:
        parts = [p for p in [name, city, state, zip_] if p]
        return "zip", parts, (None, city, state, zip_, country)
    if city and state:
        parts = [p for p in [name, city, state] if p]
        return "citystate", parts, (None, city, state, None, country)
    return None, None, None


# Well-known US cities whose state is unambiguous — used to detect corrupted
# address anchors where the city belongs to a DIFFERENT state than the stored
# state component (a botched-merge signature), or to pull a city out of the
# church name when the address city is wrong.
_CITY_STATE = {
    'FORT WORTH': 'TX', 'DALLAS': 'TX', 'HOUSTON': 'TX', 'AUSTIN': 'TX',
    'SAN ANTONIO': 'TX', 'EL PASO': 'TX', 'CORPUS CHRISTI': 'TX',
    'CHICAGO': 'IL', 'BOSTON': 'MA',
    'NEW YORK': 'NY', 'LOS ANGELES': 'CA', 'SAN FRANCISCO': 'CA',
    'SAN DIEGO': 'CA', 'SEATTLE': 'WA', 'MIAMI': 'FL', 'ATLANTA': 'GA',
    'DENVER': 'CO', 'PHOENIX': 'AZ', 'PHILADELPHIA': 'PA', 'DETROIT': 'MI',
    'MINNEAPOLIS': 'MN', 'CLEVELAND': 'OH', 'COLUMBUS': 'OH',
    'PAGO PAGO': 'AS', 'HONOLULU': 'HI', 'ANCHORAGE': 'AK',
    'WASHINGTON': 'MI', 'VIENNA': 'IL', 'BUNCOMBE': 'IL',
    'HIGH RIDGE': 'MO', 'SIGNAL MTN': 'TN', 'SANTA CRUZ': 'CA',
    'ROSE BUD': 'AR', 'MEXICO': 'MO', 'GRANT': 'AL',
    'ORANGE GROVE': 'TX', 'ROBSTOWN': 'TX', 'TAFT': 'TX',
    'ALVIN': 'TX', 'GALENA PARK': 'TX', 'NORMAN': 'OK',
    'OKLAHOMA CITY': 'OK', 'EL PASO': 'TX', 'STILLWATER': 'OK',
    'MUSKOGEE': 'OK', 'FORT DAVIS': 'TX', 'LONGMONT': 'CO',
    'PAHRUMP': 'NV', 'MTN RANCH': 'CA', 'ANGELS CAMP': 'CA',
    'LOS ANGELES': 'CA', 'TORRANCE': 'CA',
}


def _street_looks_like_city_state_zip(street):
    """Detect a 'street' component that is actually a CITY + STATE + ZIP blob
    (a botched-merge signature). e.g. 'PAGO PAGO AM 96799'."""
    if not street:
        return False
    up = street.upper()
    # A real street has a number or a street-type word; a city/state/zip blob
    # has a state abbreviation + a 5-digit zip and no street-type word.
    has_zip = bool(re.search(r'\b\d{5}(-\d{4})?\b', up))
    has_state_abbr = bool(re.search(r'\b[A-Z]{2}\b', up))
    street_type = re.search(
        r'\b(ST|STREET|AVE|AVENUE|RD|ROAD|BLVD|BOULEVARD|DR|DRIVE|LN|LANE|'
        r'CT|COURT|PL|PLACE|WAY|HWY|HIGHWAY|PKWY|PARKWAY|CIR|CIRCLE|TER|'
        r'TERRACE|SQ|SQUARE|BLDG|BUILDING|SUITE|UNIT|APT)\b', up)
    has_number = bool(re.search(r'\b\d+\b', up))
    # If it has a zip + state abbr but NO street-type word, it's a city/state/zip
    # blob, not a street.
    return has_zip and has_state_abbr and not street_type


def validate_anchor(street, city, state, zip_):
    """Return (ok, reason). ok=False means the address anchor is internally
    inconsistent (botched merge) and should NOT be geocoded as-is."""
    if not street and not city and not state and not zip_:
        return False, "empty"
    # 1. Street field contains a ZIP code -> it's a full "street, city, state,
    #    zip" blob from a botched merge, not a bare street. A real street
    #    component never has a 5-digit zip.
    if street and re.search(r'\b\d{5}(-\d{4})?\b', street):
        return False, f"street_contains_zip ({street!r})"
    # 2. Street looks like a city/state/zip blob
    if street and _street_looks_like_city_state_zip(street):
        return False, f"street_is_city_state_zip ({street!r})"
    # 3. City belongs to a different state than the stored state
    if city and state:
        known = _CITY_STATE.get(city.upper())
        if known and known != state.upper():
            return False, f"city_state_mismatch ({city!r} is {known}, not {state!r})"
    return True, "ok"


def _name_forward_search(name, country, lat, lon):
    """Name-anchored search via multi-source failover, biased to the church's
    current (centroid) coordinates so the bounded providers can actually find
    nearby POIs. Returns (winner, res_dict) or (None, None)."""
    providers = [
        ("osm_search", lambda: forward_nominatim_search(name, "", lat, lon, country)),
        ("photon_search", lambda: forward_photon_search(name, "", lat, lon)),
        ("foursquare_search", lambda: forward_foursquare_search(name, "", lat, lon)),
        ("mapsco_search", lambda: forward_mapsco_search(name, "", lat, lon)),
        ("earth_search", lambda: forward_earth_search(name, "", lat, lon)),
        ("ban_search", lambda: forward_ban_search(name, "", lat, lon)),
        ("vk_search", lambda: forward_vk_search(name, "", lat, lon)),
        ("geocodio_search", lambda: forward_geocodio_search(name, "", lat, lon)),
        ("locationiq_search", lambda: forward_locationiq_search(name, "", lat, lon)),
        ("mapbox_search", lambda: forward_mapbox_search(name, "", lat, lon)),
    ]
    for winner, fn in providers:
        try:
            res = fn()
        except Exception as e:
            print(f"  [WARN] {winner} name-search error: {e}")
            res = None
        if res and res.get("street"):
            return winner, res
    return None, None


def strip_po_box(query):
    """Remove PO box patterns from address query.
    PO boxes like 'BOX 1336, Odgen, IL, 62863' don't geocode well.
    Returns (stripped_query, was_po_box)."""
    if not query:
        return query, False
    up = query.upper()
    # Detect PO box patterns (longer matches first to avoid partial matches)
    if re.search(r'\b(PO BOX|P\.?O\.?\s*BOX|POB|BOX)\b', up):
        # Remove PO box part, keep city/state/zip
        parts = [p.strip() for p in query.split(',')]
        # Keep parts after the PO box (usually city, state, zip)
        # Find the last 2-3 parts which are typically city, state, zip
        if len(parts) >= 3:
            # Take the last 2-3 parts (city, state, zip)
            kept = ', '.join(parts[-3:])
            return kept, True
    return query, False


def split_address(query):
    """Split semicolon-delimited addresses into individual addresses.
    Examples:
      '3011 S Myers Road; Geneva, OH, 44041; &nbsp;, PLEASANTON, KS, 66075-8239'
      -> ['3011 S Myers Road, Geneva, OH, 44041', 'PLEASANTON, KS, 66075-8239']
      '201 South 15th Street; Duncan, OK, 73533; &nbsp;, CHETOPA, KS, 67336-0745'
      -> ['201 South 15th Street, Duncan, OK, 73533', 'CHETOPA, KS, 67336-0745']
    Returns (address_list, was_split)."""
    if not query:
        return [], False
    
    # Strip HTML entities first
    query = re.sub(r'&nbsp;', ' ', query)
    query = re.sub(r'&lt;', '<', query)
    query = re.sub(r'&gt;', '>', query)
    query = re.sub(r'&amp;', '&', query)
    
    # Split by semicolon
    parts = [p.strip() for p in query.split(';')]
    
    # Clean each part (remove HTML entities, empty parts)
    cleaned_parts = []
    for part in parts:
        if not part:
            continue
        # Skip parts that are just HTML entities
        if re.match(r'^&[a-z]+;$', part):
            continue
        cleaned_parts.append(part)
    
    if len(cleaned_parts) < 2:
        return [], False
    
    return cleaned_parts, True


def clean_address(query):
    """Clean malformed addresses with semicolons, HTML entities, duplicates.
    Examples:
      '3011 S Myers Road; Geneva, OH, 44041; &nbsp;, PLEASANTON, KS, 66075-8239'
      -> '3011 S Myers Road, Geneva, OH, 44041'
      '201 South 15th Street; Duncan, OK, 73533; &nbsp;, CHETOPA, KS, 67336-0745'
      -> '201 South 15th Street, Duncan, OK, 73533'
    Returns (cleaned_query, was_cleaned)."""
    if not query:
        return query, False
    
    # Strip HTML entities
    query = re.sub(r'&nbsp;', ' ', query)
    query = re.sub(r'&lt;', '<', query)
    query = re.sub(r'&gt;', '>', query)
    query = re.sub(r'&amp;', '&', query)
    
    # Split by semicolon and clean each part
    parts = [p.strip() for p in query.split(';')]
    cleaned_parts = []
    
    for part in parts:
        # Skip empty parts
        if not part:
            continue
        # Skip parts that are just HTML entities
        if re.match(r'^&[a-z]+;$', part):
            continue
        cleaned_parts.append(part)
    
    if len(cleaned_parts) < 2:
        return query, False
    
    # Reconstruct address
    cleaned = ', '.join(cleaned_parts)
    
    # Remove duplicate city/state pairs (e.g., "Geneva, OH" and "PLEASANTON, KS")
    # Look for patterns like "CITY, STATE" appearing twice
    # Simple heuristic: if we have 4+ parts and the last 3 match the first 3, remove the last 3
    if len(cleaned_parts) >= 4:
        first_3 = cleaned_parts[:3]
        last_3 = cleaned_parts[-3:]
        if first_3 == last_3:
            cleaned = ', '.join(cleaned_parts[:3])
    
    return cleaned, (cleaned != query)


def _addr_forward_fallback(name, eng, lat, lon, country, query):
    """Address-anchored forward-name search (bounded to centroid)."""
    providers = [
        ("osm_search", lambda: forward_nominatim_search(query, eng, lat, lon, country)),
        ("photon_search", lambda: forward_photon_search(query, eng, lat, lon)),
        ("foursquare_search", lambda: forward_foursquare_search(query, eng, lat, lon)),
        ("mapsco_search", lambda: forward_mapsco_search(query, eng, lat, lon)),
        ("earth_search", lambda: forward_earth_search(query, eng, lat, lon)),
        ("ban_search", lambda: forward_ban_search(query, eng, lat, lon)),
        ("vk_search", lambda: forward_vk_search(query, eng, lat, lon)),
        ("geocodio_search", lambda: forward_geocodio_search(query, eng, lat, lon)),
        ("locationiq_search", lambda: forward_locationiq_search(query, eng, lat, lon)),
        ("mapbox_search", lambda: forward_mapbox_search(query, eng, lat, lon)),
    ]
    for winner, fn in providers:
        try:
            res = fn()
        except Exception as e:
            print(f"  [WARN] {winner} fallback error: {e}")
            res = None
        if res and res.get("street"):
            return winner, res
    return None, None


def apply_result(db, now, row, res_lat, res_lon, res_street, res_city,
                 res_state, res_zip, res_country, winner):
    """Apply a recovered location to the DB. Returns True if applied."""
    cid, name, lat, lon, *_ = row
    if abs(res_lat - lat) < 1e-6 and abs(res_lon - lon) < 1e-6:
        return False
    changes = []
    db.execute("UPDATE churches SET latitude=?, longitude=?, last_updated=? WHERE id=?",
               (res_lat, res_lon, now, cid))
    changes.append((cid, "latitude", lat, res_lat))
    changes.append((cid, "longitude", lon, res_lon))
    comps = {}
    if res_street:
        comps["street"] = res_street
    for k, v in [("city", res_city), ("state", res_state),
                 ("postcode", res_zip), ("country", res_country)]:
        if v:
            comps[k] = v
    if comps:
        set_components(db, cid, comps, update_legacy=False)
        db.execute("UPDATE church_addresses SET geocode_source=?, source=? "
                   "WHERE church_id=? AND is_current=1", (winner, SOURCE, cid))
        for k, v in comps.items():
            changes.append((cid, k, None, v))
    changes.append((cid, "geocode_source", None, winner))
    db.executemany(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, "
        "new_value, change_source, changed_at) VALUES (?,?,?,?,?,?)",
        [(c, f, o, n, SOURCE, now) for c, f, o, n in changes])
    return True


def mark_attempted(db, cid, reason):
    """Mark a church as 'attempted but not recovered' so the resume filter
    (geocode_source IS NULL) skips it on the next run. Uses a sentinel value
    that is clearly not a real geocode source."""
    db.execute(
        "UPDATE church_addresses SET geocode_source=? WHERE church_id=? "
        "AND is_current=1",
        (f"{SOURCE}:{reason}", cid))


def main():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=600000")
    db.execute("PRAGMA cache_size=-1000000")

    print(f"mode: {'WRITE' if WRITE else 'DRY-RUN'}   limit: {LIMIT or 'all'}")
    print("\n[1] Loading shared-coordinate churches...")
    rows = load_targets(db)
    print(f"  {len(rows):,} shared-coord churches loaded")
    if LIMIT:
        rows = rows[:LIMIT]
        print(f"  after limit: {len(rows):,}")

    # State-hint coverage
    hints = Counter(extract_state_hint(r[1])[0] for r in rows)
    print(f"\n  State-hint in name: {sum(1 for h in hints if h)} / {len(rows):,} "
          f"({100*sum(1 for h in hints if h)/max(1,len(rows)):.1f}%)")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    applied = skipped = no_anchor = no_result = conflict = 0
    review_queue = []

    print("\n[2] Recovering...")
    for i, row in enumerate(rows, 1):
        tier, parts, (street, city, state, zip_, country) = classify_anchor(row)
        cid, name, lat, lon, *_ = row
        name_hint, name_hint_txt = extract_state_hint(name)
        addr_state = (state or "").upper()
        anchor_ok, anchor_reason = validate_anchor(street, city, state, zip_)

        if tier is None:
            no_anchor += 1
            print(f"  [SKIP] {cid} | {name[:40]:40} | no anchor")
            if WRITE:
                mark_attempted(db, cid, "no_anchor")
            continue

        # ── Phase 1: NAME-anchored search (unbounded) ──
        winner = None
        res_lat = res_lon = None
        res_street = res_city = res_state = res_zip = res_country = None
        n_winner, n_res = _name_forward_search(name, country, lat, lon)
        if n_res:
            winner = n_winner
            res_lat = float(n_res["nom_lat"])
            res_lon = float(n_res["nom_lon"])
            res_street = n_res.get("street") or ""
            res_city = n_res.get("city") or ""
            res_state = n_res.get("state") or ""
            res_zip = n_res.get("postcode") or ""
            res_country = n_res.get("country") or ""
            # State-consistency: if name has a state hint and the result's
            # state conflicts, the name search hit a wrong-state duplicate.
            res_state_up = (res_state or "").upper()
            if name_hint and res_state_up and res_state_up != name_hint:
                conflict += 1
                review_queue.append({
                    "id": cid, "name": name, "reason": "name_result_state_conflict",
                    "name_hint": name_hint, "result_state": res_state_up,
                    "result_lat": res_lat, "result_lon": res_lon,
                    "winner": winner})
                print(f"  [WARN] {cid} | {name[:40]:40} | name result state "
                      f"{res_state_up} != hint {name_hint} -> review")
                winner = None
                res_lat = res_lon = None

        # ── Phase 1.5: NAME + stripped-ADDRESS combined search ──
        # Name alone failed; address alone (esp. PO box) is too weak. Combine
        # the name with the stripped city/state/zip for a much stronger query.
        # SKIP if the address anchor is internally inconsistent (botched merge).
        if winner is None and not anchor_ok:
            print(f"  [1.5] {cid} | {name[:40]:40} | skip combined: "
                  f"corrupted anchor ({anchor_reason})")
        if winner is None:
            # If the name itself contains a "CITY STATE" pattern, that is the
            # most reliable anchor. Use it when the address is corrupted or
            # conflicts with the name's state hint.
            name_city, name_state, _ = extract_city_state_hint(name)
            if name_city and name_state:
                anchor_parts = [name_city, name_state]
                print(f"  [1.5] {cid} | {name[:40]:40} | name anchor: "
                      f"{name_city}, {name_state}")
            elif anchor_ok:
                # Build stripped address anchor (city/state/zip, no PO box/street)
                # If the name has a state hint that CONFLICTS with the address
                # state, the address is corrupted — the name is ground truth for
                # the state. Drop the corrupted city/zip too and search name +
                # hint state only (the city/zip belong to the wrong state).
                if name_hint and addr_state and addr_state != name_hint:
                    anchor_parts = [name_hint]
                    print(f"  [1.5] {cid} | {name[:40]:40} | addr state {addr_state} "
                          f"!= hint {name_hint} -> name + hint-state only")
                else:
                    anchor_parts = [p for p in (city, state, zip_) if p]
            else:
                anchor_parts = []
            if anchor_parts:
                combined = f"{name}, {', '.join(anchor_parts)}"
                print(f"  [1.5] {cid} | {name[:40]:40} | combined query: "
                      f"{combined[:80]}")
                c_winner, c_res = _name_forward_search(combined, country, lat, lon)
                if c_res:
                    winner = c_winner
                    res_lat = float(c_res["nom_lat"])
                    res_lon = float(c_res["nom_lon"])
                    res_street = c_res.get("street") or ""
                    res_city = c_res.get("city") or ""
                    res_state = c_res.get("state") or ""
                    res_zip = c_res.get("postcode") or ""
                    res_country = c_res.get("country") or ""
                    res_state_up = (res_state or "").upper()
                    if name_hint and res_state_up and res_state_up != name_hint:
                        conflict += 1
                        review_queue.append({
                            "id": cid, "name": name, "reason": "combined_state_conflict",
                            "name_hint": name_hint, "result_state": res_state_up,
                            "result_lat": res_lat, "result_lon": res_lon,
                            "winner": winner})
                        print(f"  [WARN] {cid} | {name[:40]:40} | combined state "
                              f"{res_state_up} != hint {name_hint} -> review")
                        winner = None
                        res_lat = res_lon = None
                    else:
                        print(f"  [1.5] {cid} | {name[:40]:40} | combined "
                              f"name+addr hit via {winner}")
                else:
                    print(f"  [1.5] {cid} | {name[:40]:40} | combined "
                          f"name+addr -> no result")
            else:
                print(f"  [1.5] {cid} | {name[:40]:40} | no city/state/zip "
                      f"anchor -> skip combined")

        # ── Phase 2: ADDRESS-anchored search (with state-consistency) ──
        if winner is None and not anchor_ok:
            # Corrupted address anchor — route to review, don't geocode garbage.
            conflict += 1
            review_queue.append({
                "id": cid, "name": name, "reason": f"corrupted_anchor:{anchor_reason}",
                "addr_street": street, "addr_city": city, "addr_state": state,
                "addr_zip": zip_, "current_lat": lat, "current_lon": lon})
            print(f"  [WARN] {cid} | {name[:40]:40} | corrupted anchor "
                  f"({anchor_reason}) -> review")
            no_result += 1
            if WRITE:
                mark_attempted(db, cid, f"corrupted_anchor:{anchor_reason}")
            continue

        if winner is None:
            # If name has a state hint and the address's state conflicts,
            # the address is corrupted -> route to review, don't geocode it.
            if name_hint and addr_state and addr_state != name_hint:
                conflict += 1
                review_queue.append({
                    "id": cid, "name": name, "reason": "addr_state_conflict",
                    "name_hint": name_hint, "addr_state": addr_state,
                    "addr_street": street, "addr_city": city, "addr_zip": zip_,
                    "current_lat": lat, "current_lon": lon})
                print(f"  [WARN] {cid} | {name[:40]:40} | addr state {addr_state} "
                      f"!= hint {name_hint} -> review (corrupted addr)")
                no_result += 1
                if WRITE:
                    mark_attempted(db, cid, "addr_state_conflict")
                continue

            # Address-anchored: Nominatim structured first, then failover
            # Strip PO box from street if present
            street_stripped, was_po_box = strip_po_box(street or "")
            if was_po_box:
                print(f"  [INFO] {cid} | {name[:40]:40} | stripped PO box from street")
            res = nominatim_structured(street_stripped, city, state, zip_, country)
            if res:
                winner = "nominatim_structured"
                res_lat, res_lon, display = res
                res_street = street or ""
                res_city = city or ""
                res_state = state or ""
                res_zip = zip_ or ""
                res_country = country or ""
            else:
                query = ", ".join(parts)
                # Strip PO box if present (e.g., "BOX 1336, Odgen, IL, 62863")
                query_stripped, was_po_box = strip_po_box(query)
                if was_po_box:
                    print(f"  [INFO] {cid} | {name[:40]:40} | stripped PO box from query")
                fb_winner, fb_res = _addr_forward_fallback(
                    name, "", lat, lon, country, query_stripped)
                if fb_res:
                    winner = fb_winner
                    res_lat = float(fb_res["nom_lat"])
                    res_lon = float(fb_res["nom_lon"])
                    res_street = fb_res.get("street") or ""
                    res_city = fb_res.get("city") or ""
                    res_state = fb_res.get("state") or ""
                    res_zip = fb_res.get("postcode") or ""
                    res_country = fb_res.get("country") or ""
                else:
                    no_result += 1
                    print(f"  [WARN] {cid} | {name[:40]:40} | no result for "
                          f"'{query_stripped}'")
                    if WRITE:
                        mark_attempted(db, cid, "no_result")
                    continue

        if res_lat is None:
            no_result += 1
            if WRITE:
                mark_attempted(db, cid, "no_result")
            continue

        if abs(res_lat - lat) < 1e-6 and abs(res_lon - lon) < 1e-6:
            skipped += 1
            print(f"  [SKIP] {cid} | {name[:40]:40} | result == centroid")
            if WRITE:
                mark_attempted(db, cid, "result_equals_centroid")
            continue

        # Guard: only apply if the result moves the church a MEANINGFUL
        # distance off the centroid (>= MIN_MOVE_KM) AND has a real street.
        # This prevents overwriting good data with a near-identical centroid
        # or a bare city/zip fallback that isn't a real building match.
        move_km = _dist_km(lat, lon, res_lat, res_lon)
        if move_km < MIN_MOVE_KM:
            skipped += 1
            print(f"  [SKIP] {cid} | {name[:40]:40} | move {move_km*1000:.0f}m "
                  f"< {MIN_MOVE_KM*1000:.0f}m (too close to centroid)")
            if WRITE:
                mark_attempted(db, cid, "move_too_small")
            continue
        if not (res_street or "").strip():
            skipped += 1
            print(f"  [SKIP] {cid} | {name[:40]:40} | no street in result "
                  f"(centroid fallback, not a building)")
            if WRITE:
                mark_attempted(db, cid, "no_street_in_result")
            continue

        if WRITE:
            ok = apply_result(db, now, row, res_lat, res_lon, res_street,
                              res_city, res_state, res_zip, res_country, winner)
            if ok:
                applied += 1
                print(f"  [OK] {cid} | {name[:40]:40} | {winner} | "
                      f"({lat:.5f},{lon:.5f}) -> ({res_lat:.5f},{res_lon:.5f}) | "
                      f"{res_street} {res_city} {res_state} {res_zip}")
            else:
                skipped += 1
        else:
            applied += 1
            print(f"  [OK] {cid} | {name[:40]:40} | {winner} | "
                  f"({lat:.5f},{lon:.5f}) -> ({res_lat:.5f},{res_lon:.5f}) | "
                  f"{res_street} {res_city} {res_state} {res_zip}")

        if i % 50 == 0:
            db.commit()

    # Write review queue
    if review_queue:
        os.makedirs(os.path.dirname(REVIEW_JSON), exist_ok=True)
        with open(REVIEW_JSON, "w", encoding="utf-8") as f:
            json.dump(review_queue, f, indent=2, ensure_ascii=False)
        print(f"\n  [REVIEW] {len(review_queue):,} conflicts written to {REVIEW_JSON}")

    if WRITE:
        db.commit()
        db.execute(
            "INSERT INTO provenance_log (source, script_name, started_at, "
            "completed_at, churches_updated, records_attempted, records_matched, "
            "status, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (SOURCE, "_recover_shared_coords_v2.py", now, now, applied,
             len(rows), applied, "completed",
             f"Recovered original coords/addresses for {applied} shared-coordinate "
             f"churches (name-anchored + state-consistency); {conflict} conflicts "
             f"routed to review queue"))
        db.commit()
        print(f"\n  [DONE] applied {applied:,} | skipped {skipped:,} | "
              f"no_anchor {no_anchor:,} | no_result {no_result:,} | conflict {conflict:,}")
        print("  Provenance logged. Run PRAGMA wal_checkpoint(TRUNCATE) after.")
    else:
        print(f"\n  [DRY-RUN] would apply {applied:,} | skipped {skipped:,} | "
              f"no_anchor {no_anchor:,} | no_result {no_result:,} | conflict {conflict:,}")

    db.close()


def nominatim_structured(street, city, state, zip_, country):
    """Nominatim structured /search. Returns (lat, lon, display) or None."""
    params = {"format": "json", "addressdetails": 1, "limit": 1,
              "accept-language": "en"}
    if street:
        params["street"] = street
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    if zip_:
        params["postalcode"] = zip_
    if country and len(country) == 2:
        params["countrycodes"] = country.lower()
    u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    _OSM_LIMITER.wait()
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        data = _get_json_retry(req, limiter=_OSM_LIMITER)
    except Exception as e:
        print(f"  [WARN] structured search error: {e}")
        return None
    if not data:
        return None
    hit = data[0]
    try:
        lat2, lon2 = float(hit["lat"]), float(hit["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return lat2, lon2, hit.get("display_name", "")


if __name__ == "__main__":
    main()

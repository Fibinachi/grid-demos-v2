"""
Import NHL (National Historic Landmark) churches from Wikipedia data.

Reads data/nhl_churches_raw.json, matches against churches.db,
updates matched records with NHL designation, and logs unmatched entries.

Usage:
    python scripts/enrichment/import_nhl_landmarks.py

Outputs:
    - data/nhl_matched.json     — matched entries with church IDs
    - data/nhl_unmatched.json   — entries that couldn't be matched
    - DB updates to churches (is_landmark, heritage_status, heritage_source)
    - Provenance logging
"""

import json
import re
import sys
from pathlib import Path

# Resolve project root (handle both direct run and exec scenarios)
if '__file__' in dir():
    _project_root = Path(__file__).resolve().parent.parent.parent
else:
    # When run via exec(), __file__ is not defined — cwd should be project root
    _project_root = Path.cwd()
sys.path.insert(0, str(_project_root))
from gw_db import connect, Provenance, register_source

JSON_PATH = _project_root / "data" / "nhl_churches_raw.json"
MATCHED_PATH = _project_root / "data" / "nhl_matched.json"
UNMATCHED_PATH = _project_root / "data" / "nhl_unmatched.json"
CHUNK_SIZE = 500
SCRIPT_NAME = "import_nhl_landmarks"

# ── State abbreviation map (US + Canada) ──
STATE_MAP = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
    "alberta": "AB", "british columbia": "BC", "manitoba": "MB",
    "new brunswick": "NB", "newfoundland and labrador": "NL", "nova scotia": "NS",
    "ontario": "ON", "prince edward island": "PE", "quebec": "QC", "saskatchewan": "SK",
}

# ── Helpers ──────────────────────────────────────────────────────────────

def parse_location(loc_str: str) -> tuple:
    """Parse 'City, ST' or 'City, State' into (city, state)."""
    if not loc_str:
        return (None, None)
    parts = [p.strip() for p in loc_str.rsplit(",", 1)]
    if len(parts) == 2:
        city = parts[0]
        state = parts[1].strip()
        state_lower = state.lower().strip()
        if state_lower in STATE_MAP:
            state = STATE_MAP[state_lower]
        if len(state) == 2 and state.isalpha():
            return (city, state.upper())
        return (city, state)
    return (loc_str.strip(), None)


def normalize_name(name: str) -> str:
    """Normalize a church name for matching."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
    name = re.sub(r"\s+", " ", name).strip()
    return name


def build_name_variants(name: str) -> list:
    """Generate name variants for matching, including St.↔Saint normalization."""
    base = normalize_name(name)
    variants = [base]

    # St. ↔ Saint expansion
    if "st " in base or base.startswith("st "):
        saint_v = base.replace(" st ", " saint ")
        if saint_v != base:
            variants.append(saint_v)
        saint_v_start = base.replace("st ", "saint ", 1) if base.startswith("st ") else base
        if saint_v_start != base:
            variants.append(saint_v_start)
    if "saint " in base or base.startswith("saint "):
        st_v = base.replace(" saint ", " st ")
        if st_v != base:
            variants.append(st_v)
        st_v_start = base.replace("saint ", "st ", 1) if base.startswith("saint ") else base
        if st_v_start != base:
            variants.append(st_v_start)

    # "the" variants
    if base.startswith("the "):
        variants.append(base[4:])
    if not base.startswith("the "):
        variants.append(f"the {base}")

    # Strip trailing "church" / "chapel"
    for v in list(variants):
        if v.endswith(" church"):
            variants.append(v[:-8].strip())
        if v.endswith(" chapel"):
            variants.append(v[:-7].strip())

    # Also generate St.↔Saint variants for the stripped versions
    extra = []
    for v in variants:
        if "st " in v or v.startswith("st "):
            extra.append(v.replace(" st ", " saint "))
            if v.startswith("st "):
                extra.append(v.replace("st ", "saint ", 1))
        if "saint " in v or v.startswith("saint "):
            extra.append(v.replace(" saint ", " st "))
            if v.startswith("saint "):
                extra.append(v.replace("saint ", "st ", 1))
    variants.extend(extra)

    return list(set(variants))


# ── In-Memory Church Index ───────────────────────────────────────────────

def build_church_index(db) -> list[dict]:
    """Load all churches into memory for fast matching."""
    c = db.cursor()
    c.execute("SELECT id, name, city, state, country FROM churches ORDER BY id")
    index = []
    for row in c.fetchall():
        ch_id, name, city, state_val, country = row
        index.append({
            "id": ch_id,
            "name": (name or "").strip().lower(),
            "city": (city or "").strip().lower(),
            "state": (state_val or "").strip().lower(),
            "country": (country or "").strip().lower(),
        })
    return index


def match_church_in_memory(index: list[dict], entry: dict) -> int | None:
    """Try to find a matching church using in-memory index. Returns church id or None."""
    church_name = entry.get("Church", "")
    location = entry.get("Location", "")
    city_wiki, state_wiki = parse_location(location)

    if not church_name:
        return None

    name_variants = build_name_variants(church_name)
    city_wiki_lower = (city_wiki or "").strip().lower()
    state_wiki_lower = (state_wiki or "").strip().lower()

    for variant in name_variants:
        # Strategy 1: Exact name + exact city + state
        if city_wiki_lower and state_wiki_lower:
            matches = [r for r in index
                       if r["name"] == variant
                       and r["city"] == city_wiki_lower
                       and r["state"] == state_wiki_lower]
            if len(matches) == 1:
                return matches[0]["id"]
            if len(matches) > 1:
                return matches[0]["id"]

        # Strategy 2: Name starts with + city + state
        if city_wiki_lower and state_wiki_lower:
            matches = [r for r in index
                       if r["name"].startswith(variant)
                       and r["city"] == city_wiki_lower
                       and r["state"] == state_wiki_lower]
            if len(matches) == 1:
                return matches[0]["id"]

        # Strategy 3: Name contains keyword + city + state
        if city_wiki_lower and state_wiki_lower:
            skip_words = {"the", "church", "chapel", "of", "and", "in", "at", "st",
                           "san", "santa", "first", "old", "new", "our", "lady",
                           "mission", "cathedral", "temple", "house", "meeting"}
            words = [w for w in church_name.lower().split()
                     if w not in skip_words and len(w) > 3]
            for word in words[:3]:
                matches = [r for r in index
                           if word in r["name"]
                           and r["city"] == city_wiki_lower
                           and r["state"] == state_wiki_lower]
                if len(matches) == 1:
                    return matches[0]["id"]

        # Strategy 4: Exact name + state only
        if state_wiki_lower and not city_wiki_lower:
            matches = [r for r in index
                       if r["name"] == variant
                       and r["state"] == state_wiki_lower]
            if len(matches) == 1:
                return matches[0]["id"]

    return None


# ── Data Loading ─────────────────────────────────────────────────────────

def load_nhl_data():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def update_church(db, church_id: int, entry: dict, is_former: bool = False):
    """Update a matched church with NHL data."""
    designated = entry.get("Designated", "").strip()
    if is_former:
        heritage_value = "Former National Historic Landmark"
    else:
        heritage_value = "National Historic Landmark"
    heritage_source = f"NHL designated {designated}" if designated else "National Historic Landmark"

    c = db.cursor()
    # Get old values for provenance
    c.execute("SELECT heritage_status, heritage_source, is_landmark FROM churches WHERE id = ?", (church_id,))
    old = c.fetchone()
    old_status, old_source, old_landmark = old if old else (None, None, None)

    c.execute("""
        UPDATE churches
        SET is_landmark = 1,
            heritage_status = ?,
            heritage_source = ?
        WHERE id = ?
    """, (heritage_value, heritage_source, church_id))

    # Log change
    from gw_db import log_change
    if old_status != heritage_value:
        log_change(db, church_id, "heritage_status",
                   old_value=old_status, new_value=heritage_value,
                   source=SCRIPT_NAME)
    if old_source != heritage_source:
        log_change(db, church_id, "heritage_source",
                   old_value=old_source, new_value=heritage_source,
                   source=SCRIPT_NAME)
    if not old_landmark:
        log_change(db, church_id, "is_landmark",
                   old_value=str(old_landmark), new_value="1",
                   source=SCRIPT_NAME)


def main():
    data = load_nhl_data()

    print("Building in-memory church index...")
    raw_conn = __import__("sqlite3").connect("churches.db", timeout=60)
    church_index = build_church_index(raw_conn)
    print(f"Loaded {len(church_index):,} churches into memory")
    raw_conn.close()

    # Main write connection
    db = connect(timeout=60)

    # Register the Wikipedia source
    register_source(db, "wikipedia_nhl", "web_scrape",
                    description="List of churches that are National Historic Landmarks in the United States",
                    url="https://en.wikipedia.org/wiki/List_of_churches_that_are_National_Historic_Landmarks_in_the_United_States",
                    refreshable=True, refresh_url="same",
                    refresh_type="manual", refresh_freq="yearly")

    matched = []
    unmatched = []
    updated_count = 0

    print(f"\nLoaded {len(data)} NHL entries from Wikipedia")
    print(f"{'='*70}")

    with Provenance(db, SCRIPT_NAME, source="wikipedia_nhl",
                     action="enriched", fields="is_landmark,heritage_status,heritage_source",
                     records_attempted=len(data)) as prov:

        for i, entry in enumerate(data):
            church_name = entry.get("Church", "")
            location = entry.get("Location", "")
            designated = entry.get("Designated", "").strip()
            affiliation = entry.get("Affiliation", "")
            built = entry.get("Built", "")

            is_former = (designated == "")

            # Use in-memory matching
            church_id = match_church_in_memory(church_index, entry)

            result = {
                "nhl_name": church_name,
                "location": location,
                "city_state": parse_location(location),
                "designated": designated,
                "built": built,
                "affiliation": affiliation,
                "is_former": is_former,
            }

            if church_id:
                result["church_id"] = church_id
                update_church(db, church_id, entry, is_former)
                updated_count += 1
                prov.churches_updated += 1
                matched.append(result)
                status = "MATCH"
            else:
                unmatched.append(result)
                status = "NO MATCH"

            print(f"  [{status:8s}] {church_name[:60]:60s} | {location[:25]:25s}")

            if (i + 1) % CHUNK_SIZE == 0:
                db.commit()

        db.commit()

    # Write outputs
    with open(MATCHED_PATH, "w", encoding="utf-8") as f:
        json.dump(matched, f, indent=2, ensure_ascii=False)
    with open(UNMATCHED_PATH, "w", encoding="utf-8") as f:
        json.dump(unmatched, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*70}")
    print(f"Results: {len(matched)} matched, {len(unmatched)} unmatched, {updated_count} updated")
    print(f"Matched list:   {MATCHED_PATH}")
    print(f"Unmatched list: {UNMATCHED_PATH}")


if __name__ == "__main__":
    main()

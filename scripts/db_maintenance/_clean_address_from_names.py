"""
Clean up error merges where address data was concatenated into church names.
Loads entire DB into memory, uses Python regex on every row.

Usage:
    python _clean_address_from_names.py              # Show mode
    python _clean_address_from_names.py --apply       # Apply changes
    python _clean_address_from_names.py --tier 1      # Just Tier 1
"""
import sqlite3
import re
import sys
from datetime import datetime, timezone

DB_PATH = r'E:\grid\churches.db'

# â”€â”€ US State abbreviations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
US_STATES = {
    'AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN',
    'IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH',
    'NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT',
    'VT','VA','WA','WV','WI','WY','AS','GU','MP','PR','VI'
}

# Build state alternation for regex (capturing group for state)
_ST_ALT = '(' + '|'.join(sorted(US_STATES)) + ')'

# â”€â”€ Regex patterns â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Street suffixes â€” ST needs \b to avoid matching STREET
_STREET_SUFX = r'(?:STREET|ST\b|AVENUE|AVE|DRIVE|DR|ROAD|RD|BOULEVARD|BLVD|PARKWAY|PKWY|LANE|LN|CIRCLE|CIR|COURT|CT|PLACE|PL|WAY|HWY|HIGHWAY|TRACE|TRAIL|CRESCENT|TERRACE|TER|RIDGE|VIEW|CROSSING|XING|RUN|WALK)'

# Directional prefix
_DIR = r'(?:NORTH\s+WEST|NORTH\s+EAST|SOUTH\s+WEST|SOUTH\s+EAST|N\.?\s*W\.?|N\.?\s*E\.?|S\.?\s*W\.?|S\.?\s*E\.?|NORTH|SOUTH|EAST|WEST|N\.?|S\.?|E\.?|W\.?)'

# Full state name
_FULL_ST = r'(?:ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|NEW\s+HAMPSHIRE|NEW\s+JERSEY|NEW\s+MEXICO|NEW\s+YORK|NORTH\s+CAROLINA|NORTH\s+DAKOTA|OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|RHODE\s+ISLAND|SOUTH\s+CAROLINA|SOUTH\s+DAKOTA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WEST\s+VIRGINIA|WISCONSIN|WYOMING)'

# â”€â”€ TIER 1: Full street address â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# All patterns capture the optional direction as group(2) for inclusion in output.

# Pattern A: Street + city + validated state + optional zip
# "123 N MAIN ST, CITY, ST 12345" or "123 N MAIN ST CITY ST 12345"
_T1A = re.compile(
    r'\s+(\d{1,5})\s+'              # [1] number
    + r'(?:(' + _DIR + r')(?=[.\s]))?'  # [2] direction (captured, lookahead-validated)
    + r'\.?\s*'                     # optional dot + optional space
    + r'([A-Z][A-Za-z.\s\']+?)'     # [3] street name (lazy)
    + r'\s+(' + _STREET_SUFX + r')'  # [4] suffix
    + r'\.?\s*,?\s*'                 # punctuation
    + r'([A-Z][A-Za-z .\'-]+?)'     # [5] city (lazy, REQUIRED)
    + r'\s*,?\s+'
    + _ST_ALT                        # [6] state (VALIDATED)
    + r'(?:\s+(\d{5}(?:-\d{4})?))?'  # [7] optional zip
    + r'\s*$',
    re.IGNORECASE
)

# Pattern B: Street only (no city) at end of name
# "123 N MAIN ST"
_T1B = re.compile(
    r'\s+(\d{1,5})\s+'              # [1] number
    + r'(?:(' + _DIR + r')(?=[.\s]))?'  # [2] direction (captured, lookahead-validated)
    + r'\.?\s*'                     # optional dot + optional space
    + r'([A-Z][A-Za-z.\s\']+?)'     # [3] street name (lazy)
    + r'\s+(' + _STREET_SUFX + r')'  # [4] suffix
    + r'\.?\s*$',                    # end
    re.IGNORECASE
)

# Pattern C: Street + validated state + optional zip (no city)
# "123 N MAIN ST ST 12345"
_T1C = re.compile(
    r'\s+(\d{1,5})\s+'              # [1] number
    + r'(?:(' + _DIR + r')(?=[.\s]))?'  # [2] direction (captured, lookahead-validated)
    + r'\.?\s*'                     # optional dot + optional space
    + r'([A-Z][A-Za-z.\s\']+?)'     # [3] street name (lazy)
    + r'\s+(' + _STREET_SUFX + r')'  # [4] suffix
    + r'\.?\s*,?\s+'
    + _ST_ALT                        # [5] state (VALIDATED)
    + r'(?:\s+(\d{5}(?:-\d{4})?))?'  # [6] optional zip
    + r'\s*$',
    re.IGNORECASE
)


def extract_tier1(name):
    """
    Extract full street address + city/ST/zip from end of name.
    Tries three patterns: A (street+city+ST), B (street only), C (street+ST).
    Only extracts when state is a VALID US state abbreviation.
    Preserves directionals (N, S, E, W) in the extracted address.
    """
    def build_addr(num, direction, street_name, suffix):
        """Rebuild address string with optional directional."""
        parts = [num]
        if direction:
            d = direction.strip().rstrip('.').upper()
            if d in ('N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW',
                     'NORTH', 'SOUTH', 'EAST', 'WEST'):
                parts.append(d[0])  # Use single letter
        parts.append(street_name)
        parts.append(suffix)
        return ' '.join(parts).rstrip('.')

    # Try A: street + city + validated state + optional zip
    m = _T1A.search(name)
    if m:
        num, direction, street_name, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
        city, state, zip_code = m.group(5), m.group(6), m.group(7) or ''
        street_name = street_name.strip()
        
        if len(street_name) <= 60:
            cleaned = name[:m.start()].strip()
            if len(cleaned) < 5:
                return name, None  # church name too short â€” likely false positive
            addr = build_addr(num, direction, street_name, suffix)
            extracted = {'address': addr}
            if city.strip():
                extracted['city'] = city.strip()
            extracted['state'] = state
            if zip_code:
                extracted['zip'] = zip_code
                extracted['zip5'] = zip_code[:5]
            return cleaned, extracted
    
    # Try C: street + validated state (no city)
    m = _T1C.search(name)
    if m:
        num, direction, street_name, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
        state, zip_code = m.group(5), m.group(6) or ''
        street_name = street_name.strip()
        
        if len(street_name) <= 60:
            cleaned = name[:m.start()].strip()
            if len(cleaned) < 5:
                return name, None  # church name too short â€” likely false positive
            addr = build_addr(num, direction, street_name, suffix)
            extracted = {'address': addr}
            extracted['state'] = state
            if zip_code:
                extracted['zip'] = zip_code
                extracted['zip5'] = zip_code[:5]
            return cleaned, extracted
    
    # Try B: street only (no city/ST) â€” simple address at end of name
    m = _T1B.search(name)
    if m:
        num, direction, street_name, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
        street_name = street_name.strip()
        
        if len(street_name) <= 60:
            cleaned = name[:m.start()].strip()
            if len(cleaned) < 10:
                return name, None  # church name too short â€” likely false positive
            addr = build_addr(num, direction, street_name, suffix)
            extracted = {'address': addr}
            return cleaned, extracted
    
    return name, None


# â”€â”€ TIER 2: Clean CITY, ST from name (conservative) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Only strip City, ST when the NAME contains address data that makes
# the City, ST clearly a merge artifact rather than a church name component.
# Strategy: only strip when name has a street number + suffix pattern
# earlier in the string â€” the City, ST after an address is clearly merge junk.

_HAS_STREET_IN_NAME = re.compile(r'\b\d{1,5}\s+(?:NORTH|SOUTH|EAST|WEST|N\.?|S\.?|E\.?|W\.?\.)?\s*[A-Z][A-Za-z]+\s+(?:STREET|ST\b|AVENUE|AVE|ROAD|RD|DRIVE|DR|BOULEVARD|BLVD|LANE|LN|CIRCLE|CIR|COURT|CT|PLACE|PL|WAY|HWY|HIGHWAY)\b', re.IGNORECASE)

_TRAILING_CITY_ST = re.compile(
    r'\s*,?\s+([A-Z][A-Za-z .\'-]+?),?\s+(' + _ST_ALT + r')\s*$'
)


def extract_tier2(name):
    """
    Strip City, ST from end of name ONLY when name also contains
    a street address (number + street name + suffix). Otherwise
    the City, ST is likely a legitimate church name component.
    """
    # Must have a street address pattern somewhere in the name
    if not _HAS_STREET_IN_NAME.search(name):
        return None
    
    m = _TRAILING_CITY_ST.search(name)
    if not m:
        return None
    
    city = m.group(1).strip().rstrip('.')
    state = m.group(2)
    
    # Validate city isn't a junk word
    if city.upper() in {'OF', 'AT', 'THE', 'AND', 'IN', 'FOR', 'ON', 'TO', 'BY', 'A', 'AN', 'INC', 'LLC', 'CORP', 'DBA', 'LTD'}:
        return None
    if len(city) <= 1:
        return None
    
    cleaned = name[:m.start()].strip()
    return cleaned


# â”€â”€ TIER 3: Just ZIP at end (conservative) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Only strip ZIP when name has address data confirming it's a merge.
_TRAILING_ZIP = re.compile(r'\s+(\d{5}(?:-\d{4})?)\s*$')


def extract_tier3(name):
    """
    Strip trailing ZIP when name also has a street address.
    A standalone ZIP at end of church name is usually a merge error.
    """
    if not _HAS_STREET_IN_NAME.search(name):
        return None
    
    m = _TRAILING_ZIP.search(name)
    if not m:
        return None
    
    cleaned = name[:m.start()].strip()
    return cleaned


# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    apply_mode = '--apply' in sys.argv
    only_tier = None
    if '--tier' in sys.argv:
        idx = sys.argv.index('--tier')
        only_tier = int(sys.argv[idx + 1])

    # â”€â”€ Load ALL data into memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print("Loading churches.db into memory...", end=' ', flush=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    
    rows = db.execute(
        "SELECT rowid, name, address, city, state, zip, zip5, source FROM churches"
    ).fetchall()
    print(f"{len(rows):,} rows loaded")

    # â”€â”€ Process tiers (all 3.4M rows, full accuracy) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    tier_stats = {}

    def _reload_rows():
        """Re-fetch all rows after an apply tier modified the DB."""
        nonlocal rows
        rows = db.execute(
            "SELECT rowid, name, address, city, state, zip, zip5, source FROM churches"
        ).fetchall()
        print(f"  [reloaded {len(rows):,} rows after apply]")

    if not only_tier or only_tier == 1:
        changed = process_tier(1, rows, db, apply_mode, tier_stats, extract_tier1,
            header="Full street address in name â†’ extract into columns")
        if apply_mode and changed:
            _reload_rows()

    if not only_tier or only_tier == 2:
        changed = process_tier(2, rows, db, apply_mode, tier_stats, extract_tier2,
            header="City, ST after street address â†’ strip from name",
            extractor_is_simple=True)
        if apply_mode and changed:
            _reload_rows()

    if not only_tier or only_tier == 3:
        process_tier(3, rows, db, apply_mode, tier_stats, extract_tier3,
            header="ZIP after street address â†’ strip from name",
            extractor_is_simple=True)

    # â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print(f"\n{'='*70}")
    if apply_mode:
        total = sum(tier_stats.values())
        print(f"TOTAL APPLIED: {total:,} records cleaned")
        for t, n in sorted(tier_stats.items()):
            if n:
                print(f"  Tier {t}: {n:,}")
        if total:
            db.execute("""INSERT INTO provenance_log(source, script_name, started_at, completed_at,
                churches_updated, churches_inserted, fields_populated, parameters, status, notes)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                ('_clean_address_from_names.py', '_clean_address_from_names.py',
                 datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(),
                 total, 0, 'name,address,city,state,zip', 'apply',
                 'completed', f'Cleaned merge errors from {total:,} records'))
            db.commit()
    else:
        print(f"\nPreview mode â€” run with --apply to write changes")

    db.close()


def process_tier(tier, rows, db, apply_mode, tier_stats, extractor_func,
                 header, extractor_is_simple=False):
    """Process a single tier: scan all rows, collect matches, show or apply."""
    print(f"\n{'='*70}")
    print(f"TIER {tier}: {header}")
    print(f"  Scanning {len(rows):,} rows...", end=' ', flush=True)
    
    candidates = []
    report_every = 200000
    
    for i, r in enumerate(rows):
        name = r['name']
        if not name:
            continue
        
        result = extractor_func(name)
        
        if extractor_is_simple:
            cleaned = result
            if cleaned and cleaned != name:
                candidates.append((r, cleaned))
        else:
            cleaned, extracted = result
            if extracted and cleaned != name:
                candidates.append((r, cleaned, extracted))
        
        if (i + 1) % report_every == 0:
            print(f"\n  [{i+1:,}] {len(candidates):,} found so far...", end=' ', flush=True)
    
    print(f"\n  â”€â”€ {len(candidates):,} candidates found â”€â”€")
    tier_stats[tier] = tier_stats.get(tier, 0)
    
    if not apply_mode and candidates:
        _show_candidates(tier, candidates, extractor_is_simple)
    
    return _apply_candidates(tier, candidates, db, apply_mode, tier_stats, extractor_is_simple)


def _show_candidates(tier, candidates, extractor_is_simple):
    """Display preview of candidates."""
    limit = 20
    for i, cand in enumerate(candidates[:limit]):
        if extractor_is_simple:
            r, cleaned = cand
            old_tail = r['name'][len(cleaned):].strip()
            print(f"\n  [{i+1}] rowid={r['rowid']} ({r['source']})")
            print(f"      ORIGINAL: {r['name'][:110]}")
            print(f"      CLEANED:  {cleaned[:90]}")
            print(f"      REMOVED:  '{old_tail}'")
        else:
            r, cleaned, extracted = cand
            print(f"\n  [{i+1}] rowid={r['rowid']} ({r['source']})")
            print(f"      ORIGINAL: {r['name'][:130]}")
            print(f"      CLEANED:  {cleaned[:90]}")
            for k, v in extracted.items():
                old = r[k] or '(empty)'
                if k in ('city', 'state') and old != '(empty)' and old.upper() != v.upper():
                    print(f"      -> {k}: {v}  (was: {old}) *** CONFLICT ***")
                else:
                    print(f"      -> {k}: {v}  (was: {old})")

    remaining = len(candidates) - limit
    if remaining > 0:
        print(f"\n  ... and {remaining:,} more")

    print(f"\n  Total Tier {tier} candidates: {len(candidates):,}")


def _apply_candidates(tier, candidates, db, apply_mode, tier_stats, extractor_is_simple):
    """Apply changes to DB if in apply_mode."""
    if not candidates:
        return 0

    if apply_mode:
        updated = 0
        db.execute("BEGIN")
        for cand in candidates:
            if extractor_is_simple:
                r, cleaned = cand
                db.execute("UPDATE churches SET name = ? WHERE rowid = ?",
                           (cleaned, r['rowid']))
            else:
                r, cleaned, extracted = cand
                sets = ['name = ?']
                params = [cleaned]
                for col in ['address', 'city', 'state', 'zip', 'zip5']:
                    if col in extracted:
                        sets.append(f'{col} = ?')
                        params.append(extracted[col])
                params.append(r['rowid'])
                db.execute(
                    f"UPDATE churches SET {', '.join(sets)} WHERE rowid = ?",
                    params)
            updated += 1
        db.commit()
        print(f"  APPLIED: {updated:,} records")
        tier_stats[tier] = updated
        return updated
    return 0


if __name__ == '__main__':
    main()
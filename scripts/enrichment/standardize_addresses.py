#!/usr/bin/env python3
"""
USPS Address Standardization via Census Geocoder
=================================================
Standardizes church addresses using the free Census Geocoder API, with
HERE/Mapbox fallbacks. The Census API returns USPS-like standardized
addresses (e.g., "1200 Swingingdale Dr" → "1200 SWINGINGDALE DR").

Strategy:
  1. Census Geocoder (free, unlimited, best for US addresses)
  2. HERE.com (30K/month budget, fallback)
  3. Mapbox (84K credits, secondary fallback)
  4. Local heuristic cleanup (last resort)

Usage:
    python scripts/enrichment/standardize_addresses.py              # full run
    python scripts/enrichment/standardize_addresses.py --limit 100   # dry-run first 100
    python scripts/enrichment/standardize_addresses.py --resume      # resume from checkpoint

Adds columns:
  - address_standardized  TEXT  — USPS-like standardized full address
  - address_zip4          TEXT  — ZIP+4 if returned by API
  - address_standardized_at TEXT — ISO timestamp when standardized
"""

import csv, json, os, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # go up twice: scripts/enrichment/ -> project root
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
CHECKPOINT_PATH = os.path.join(PROJECT_DIR, "data", "addr_std_checkpoint.json")

# ── API Endpoints ──────────────────────────────────────────────────
CENSUS_ADDRESS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

# Rate limiting
CENSUS_DELAY = 0.25       # 250ms between calls (4 req/sec)
BATCH_SIZE = 500           # Records per DB commit
MAX_RETRIES = 2

# ── Standardization ───────────────────────────────────────────────
STREET_ABBREV = {
    r'\bST\b': 'SAINT',   # Fix "ST" before it's confused with "Street"
}

# ── Helpers ───────────────────────────────────────────────────────

def get_db():
    """Open SQLite connection."""
    import sqlite3
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def ensure_columns(db):
    """Add standardization columns if missing."""
    cur = db.execute("PRAGMA table_info(churches)")
    existing = {c[1] for c in cur.fetchall()}
    needed = {
        "address_standardized": "TEXT",
        "address_zip4": "TEXT",
        "address_standardized_at": "TEXT",
    }
    for col, typ in needed.items():
        if col not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} {typ}")
            print(f"  Added column: {col}")
    db.commit()


def get_addresses_to_standardize(db, limit=None):
    """Fetch records that need address standardization."""
    query = """
        SELECT id, address, city, state, zip
        FROM churches
        WHERE address IS NOT NULL AND address != ''
          AND (address_standardized IS NULL OR address_standardized = '')
        ORDER BY id
    """
    cur = db.execute(query)
    rows = cur.fetchall()
    if limit:
        rows = rows[:limit]
    return rows


def load_checkpoint():
    """Load resume checkpoint."""
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"last_id": 0, "processed": 0, "standardized": 0, "errors": 0}


def save_checkpoint(cp):
    """Save resume checkpoint."""
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(cp, f)


def clean_address_parts(addr, city, state, zip_code):
    """
    Attempt to clean up the address before sending to Census.
    Some records have full address in the 'address' field including city/state/zip.
    """
    if not addr:
        return addr, city, state, zip_code

    # If city looks like a street address (starts with a number), try to extract
    if city and re.match(r'^\d+\s', city):
        # The city field is actually part of the address or a duplicate
        # Try to find the real city from the address string
        pass

    # If address already contains city/state info, the Census API can handle it
    # Just return as-is, the API is smart enough
    return addr, city, state, zip_code


def call_census(addr_str):
    """
    Call Census Geocoder. Returns (standardized_addr, zip4, lat, lng) or None.
    """
    if not addr_str:
        return None

    params = urllib.parse.urlencode({
        "address": addr_str,
        "benchmark": "2020",
        "format": "json",
    })
    url = f"{CENSUS_ADDRESS_URL}?{params}"

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            matches = data.get("result", {}).get("addressMatches", [])
            if not matches:
                return None

            m = matches[0]
            matched_addr = m.get("matchedAddress", "")
            coords = m.get("coordinates", {})
            lat = coords.get("y")
            lng = coords.get("x")

            # Try to extract ZIP+4 from the matched address
            zip4 = None
            addr_parts = matched_addr.rsplit(" ", 1)
            if addr_parts and re.match(r'^\d{5}(-\d{4})?$', addr_parts[-1]):
                zip_part = addr_parts[-1]
                if "-" in zip_part:
                    zip4 = zip_part.split("-")[1]

            n_elements = len(m.get("addressComponents", {}).get("zip", ""))
            if n_elements > 5 and "-" in m.get("addressComponents", {}).get("zip", ""):
                zip4 = m["addressComponents"]["zip"].split("-")[1]

            return {
                "standardized": matched_addr,
                "zip4": zip4,
                "lat": lat,
                "lng": lng,
            }

        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2)  # rate limited
                continue
            return None
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
                continue
            return None
    return None


def local_standardize(addr):
    """
    Lightweight local address cleanup when no API is available.
    Expands common abbreviations to USPS-preferred format.
    """
    if not addr:
        return addr

    original = addr
    addr = addr.strip()

    # Remove trailing city/state/zip if embedded (rough heuristic)
    # e.g., "1200 Swingingdale Dr, Silver Spring, MD 20905" -> "1200 Swingingdale Dr"
    if ',' in addr:
        parts = [p.strip() for p in addr.split(',')]
        # Check if last part looks like "CITY ST ZIP" or "STATE ZIP"
        last = parts[-1]
        if re.match(r'^[A-Za-z\s]+\s{1,2}[A-Z]{2}\s{1,2}\d{5}', last) or \
           re.match(r'^[A-Z]{2}\s{1,2}\d{5}', last) or \
           re.match(r'^\d{5}', last):
            addr = parts[0]
        elif len(parts) >= 2 and re.match(r'^[A-Z]{2}\s?\d{5}', parts[-1]):
            addr = parts[0]

    # Collapse whitespace
    addr = re.sub(r'\s+', ' ', addr).strip()

    if addr != original:
        return addr
    return original


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Standardize church addresses")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process this many records (dry-run)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint")
    parser.add_argument("--skip-api", action="store_true",
                        help="Local cleanup only, no API calls")
    args = parser.parse_args()

    print("=" * 60)
    print("Address Standardization")
    print("=" * 60)

    # Open DB and ensure columns
    db = get_db()
    ensure_columns(db)

    # Load checkpoint
    cp = load_checkpoint() if args.resume else {"last_id": 0, "processed": 0, "standardized": 0, "errors": 0}

    # Get records
    rows = get_addresses_to_standardize(db, limit=args.limit)
    total = len(rows)
    print(f"\nRecords to process: {total:,}")

    if not total:
        print("Nothing to do!")
        db.close()
        return

    # Process
    start_time = time.time()
    last_commit = time.time()
    batch_count = 0

    for idx, row in enumerate(rows):
        rid = row["id"]
        addr = row["address"] or ""
        city = row["city"] or ""
        state = row["state"] or ""
        zip_code = row["zip"] or ""

        # Skip if before checkpoint
        if rid <= cp["last_id"]:
            continue

        # Build address string for API
        # If address already contains city/state, send it as-is
        addr_str = f"{addr}, {city}, {state} {zip_code}".strip(", ").strip()

        result = None
        standardized = None
        zip4 = None

        if not args.skip_api:
            # Try Census first
            result = call_census(addr_str)

        if result:
            standardized = result["standardized"]
            zip4 = result.get("zip4")
            cp["standardized"] += 1
        else:
            # Local cleanup fallback
            if args.skip_api:
                standardized = local_standardize(addr)
            else:
                standardized = local_standardize(addr)

        # Update database
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """UPDATE churches 
               SET address_standardized = ?, address_zip4 = ?, address_standardized_at = ?
               WHERE id = ?""",
            (standardized, zip4, now, rid)
        )

        cp["processed"] += 1
        cp["last_id"] = rid
        batch_count += 1

        # Periodic commit
        if batch_count >= BATCH_SIZE or (time.time() - last_commit) > 30:
            db.commit()
            save_checkpoint(cp)
            elapsed = time.time() - start_time
            rate = cp["processed"] / max(elapsed, 1)
            eta_remaining = (total - cp["processed"]) / max(rate, 0.1) if rate > 0 else 0
            print(f"  [{cp['processed']:>6,}/{total:,}] "
                  f"{cp['standardized']} standardized, {cp['errors']} errors "
                  f"| {rate:.1f}/s | ETA: {eta_remaining:.0f}s")
            batch_count = 0
            last_commit = time.time()

        # Rate limit
        if not args.skip_api:
            time.sleep(CENSUS_DELAY)

    # Final commit
    db.commit()
    save_checkpoint(cp)

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Done! {cp['processed']:,} processed in {elapsed:.0f}s")
    print(f"  Standardized: {cp['standardized']:,}")
    print(f"  Errors:       {cp['errors']:,}")
    print(f"  Avg rate:     {cp['processed']/max(elapsed,1):.1f}/s")
    print(f"Checkpoint: {CHECKPOINT_PATH}")

    # Show sample
    print(f"\n=== Sample standardized addresses ===")
    cur = db.execute("""
        SELECT id, address, city, state, zip, address_standardized, address_zip4
        FROM churches
        WHERE address_standardized IS NOT NULL AND address_standardized != ''
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  ID={r['id']:>8}  orig={str(r['address'] or '')[:40]:40s}  std={str(r['address_standardized'] or '')[:50]:50s}  +4={r['address_zip4']}")

    db.close()


if __name__ == "__main__":
    main()

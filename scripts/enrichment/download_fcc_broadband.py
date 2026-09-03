#!/usr/bin/env python3
"""Populate church_broadband with broadband availability data.

Uses multiple sources, from most granular to least:
  1. FCC Form 477 block-level data (2GB download) — tract-level fiber/cable/DSL
  2. Census ACS county-level broadband subscription % — broadband_pct by county

The FCC URL is https://broadbandmap.fcc.gov/data-download/nationwide-data-jun2024.zip
-- may be deprecated under the new BDC system. If unavailable, falls back to
county-level ACS broadband_pct (covers 300K+ US churches via county_fips).

Usage:
    python scripts/enrichment/download_fcc_broadband.py
    python scripts/enrichment/download_fcc_broadband.py --fcc-only
    python scripts/enrichment/download_fcc_broadband.py --acs-only
    python scripts/enrichment/download_fcc_broadband.py --states CA,TX
    python scripts/enrichment/download_fcc_broadband.py --dry-run
"""

import csv
import io
import json
import os
import sqlite3
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, 'data', 'fcc')
os.makedirs(DATA_DIR, exist_ok=True)
from gw_db import connect

# Direct DB path for bulk operations
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

# -- CLI flags --
DRY_RUN = '--dry-run' in sys.argv
FCC_ONLY = '--fcc-only' in sys.argv
ACS_ONLY = '--acs-only' in sys.argv
STATES = None
for a in sys.argv:
    if a.startswith('--states='):
        STATES = set(a.split('=')[1].upper().split(','))

# FCC Form 477 data URL (June 2024 vintage) -- may be deprecated under BDC
FCC_477_URL = 'https://broadbandmap.fcc.gov/data-download/nationwide-data-jun2024.zip'

# Technology code -> label mapping
TECH_MAP = {
    10: 'copper', 40: 'copper', 50: 'copper',        # DSL variants
    11: 'cable', 12: 'cable', 43: 'cable',            # DOCSIS variants
    60: 'fiber', 61: 'fiber',                          # GPON, active Ethernet
    70: 'fixed_wireless', 71: 'fixed_wireless',
    0: 'satellite', 1: 'satellite',
}

# FIPS to state abbreviation
FIPS_TO_STATE = {
    '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA',
    '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL',
    '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN',
    '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME',
    '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS',
    '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH',
    '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND',
    '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI',
    '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT',
    '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI', '56': 'WY',
}

# Census API key from project resources
CENSUS_API_KEY = "2159d6ade3d596371c9333d6118d1ef2f9342cf4"


def log(msg):
    print(f"  {msg}", flush=True)


# ═══════════════════════════════════════════════════════════════════════════
# PART 1: County-level broadband_pct from Census ACS
# ═══════════════════════════════════════════════════════════════════════════

# ACS table B28002: Types of Internet Subscriptions
# B28002_001E = Total households
# B28002_005E = With a broadband internet subscription (cable, fiber, DSL, cellular, satellite, etc.)
CENSUS_BB_VARS = "B28002_001E,B28002_005E"


def fetch_census_county_broadband():
    """Fetch county-level broadband subscription % from Census ACS B28002.
    Returns dict: {county_fips_5: broadband_pct}"""
    log("Fetching county broadband from Census ACS B28002...")
    url = (
        f"https://api.census.gov/data/2022/acs/acs5"
        f"?get=NAME,{CENSUS_BB_VARS}"
        f"&for=county:*&key={CENSUS_API_KEY}"
    )

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode('utf-8')
        rows = json.loads(raw)
    except Exception as e:
        log(f"  Census ACS county query FAILED: {e}")
        return {}

    header = rows[0]
    total_idx = header.index("B28002_001E")
    bb_idx = header.index("B28002_005E")
    state_idx = header.index("state")
    county_idx = header.index("county")

    county_data = {}
    for row in rows[1:]:
        county_fips = row[state_idx] + row[county_idx]  # 5-digit FIPS
        try:
            total = float(row[total_idx])
            bb = float(row[bb_idx])
        except (ValueError, IndexError):
            continue
        if total > 0:
            pct = round(bb / total * 100, 1)
            county_data[county_fips] = pct

    log(f"  Got broadband data for {len(county_data):,} counties")
    return county_data


def apply_county_broadband(county_bb, source='acs_b28002'):
    """Match churches by county_fips_5 and insert broadband_pct.
    Uses direct sqlite3 for reliability with large batch inserts."""
    # Open direct connection for write-heavy workload
    raw = sqlite3.connect(DB_PATH, timeout=120)
    raw.execute("PRAGMA journal_mode=MEMORY")  # no WAL contention
    raw.execute("PRAGMA synchronous=OFF")  # faster for bulk insert
    c = raw.cursor()
    now = datetime.now(timezone.utc).isoformat()

    log("Applying county broadband to churches...")
    c.execute("""
        SELECT id, county_fips_5
        FROM churches
        WHERE country = 'US'
          AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
          AND id IS NOT NULL
    """)
    rows = c.fetchall()
    log(f"  {len(rows):,} US churches with county_fips_5")

    # Prepare insert batch
    inserts = []
    no_data = 0
    for church_id, cfips in rows:
        cfips = cfips.strip().zfill(5)
        pct = county_bb.get(cfips)
        if pct is None:
            no_data += 1
            continue
        inserts.append((church_id, pct, source, now))

    # Bulk insert using executemany
    log(f"  Inserting {len(inserts):,} rows (skipped {no_data:,} no-data)...")
    c.execute("BEGIN TRANSACTION")
    c.executemany("""
        INSERT INTO church_broadband
            (church_id, broadband_pct, data_vintage, source, created_at)
        VALUES (?, ?, '2022-acs5', ?, ?)
    """, inserts)
    raw.commit()
    log(f"  Inserted {len(inserts):,} churches via county broadband")

    # Verify
    c.execute("SELECT COUNT(1) FROM church_broadband")
    total = c.fetchone()[0]
    log(f"  Total rows in church_broadband: {total:,}")

    raw.close()
    return len(inserts)


# ═══════════════════════════════════════════════════════════════════════════
# PART 2: FCC Form 477 block-level data (tract-level fiber/cable/DSL)
# ═══════════════════════════════════════════════════════════════════════════

def download_477():
    """Download and extract FCC 477 broadband data. Returns path to CSV or None."""
    zip_path = os.path.join(DATA_DIR, 'fcc_477_jun2024.zip')
    csv_path = os.path.join(DATA_DIR, 'fcc_477_blocks.csv')

    if os.path.exists(csv_path):
        log(f"  Using cached {csv_path}")
        return csv_path

    if os.path.exists(zip_path):
        log(f"  Using cached {zip_path}, extracting...")
    else:
        log("Downloading FCC Form 477 broadband data (~2GB)...")
        try:
            req = urllib.request.Request(
                FCC_477_URL, headers={'User-Agent': 'GRID/1.0'}
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                with open(zip_path, 'wb') as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            log(f"  Downloaded {os.path.getsize(zip_path):,} bytes")
        except Exception as e:
            log(f"  FCC download FAILED: {e}")
            return None

    log("Extracting ZIP...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.endswith('.csv') and 'broadband' in name.lower():
                    zf.extract(name, DATA_DIR)
                    extracted = os.path.join(DATA_DIR, name)
                    if extracted != csv_path:
                        os.rename(extracted, csv_path)
                    break
        log(f"  Extracted to {csv_path}")
    except Exception as e:
        log(f"  Extraction FAILED: {e}")
        return None

    return csv_path


def process_477(csv_path, db):
    """Process FCC 477 block-level data -> tract-level -> match to churches."""
    c = db.cursor()

    log("Step 1: Aggregating broadband by census tract...")
    tract_data = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i % 1_000_000 == 0:
                log(f"  ... {i:,} rows processed")

            block_fips = row.get('blockcode', row.get('BlockCode', ''))
            if not block_fips or len(block_fips) < 12:
                continue

            tract = block_fips[:11]

            if STATES is not None:
                state_abbr = FIPS_TO_STATE.get(block_fips[:2])
                if state_abbr not in STATES:
                    continue

            try:
                tech_code = int(row.get('techcode', row.get('TechCode', 0)))
                down = float(row.get('maxaddown', row.get('MaxAdDown', 0)))
                up = float(row.get('maxadup', row.get('MaxAdUp', 0)))
            except (ValueError, TypeError):
                continue

            tech = TECH_MAP.get(tech_code, 'other')
            provider = row.get('frn', row.get('FRN', ''))

            if tract not in tract_data:
                tract_data[tract] = {
                    'fiber': 0, 'cable': 0, 'dsl': 0, 'fixed_wireless': 0,
                    'max_down': 0, 'max_up': 0,
                    'providers': set(), 'fiber_providers': set(),
                    'cable_providers': set(),
                }

            td = tract_data[tract]
            td['max_down'] = max(td['max_down'], down)
            td['max_up'] = max(td['max_up'], up)
            td['providers'].add(provider)

            if tech == 'fiber':
                td['fiber'] = 1
                td['fiber_providers'].add(provider)
            elif tech == 'cable':
                td['cable'] = 1
                td['cable_providers'].add(provider)
            elif tech == 'copper':
                td['dsl'] = 1
            elif tech == 'fixed_wireless':
                td['fixed_wireless'] = 1

    log(f"  {len(tract_data):,} tracts with broadband data")

    log("Step 2: Matching to churches by tract_fips via church_enrichment...")
    c.execute("""
        SELECT c.id, e.tract_fips
        FROM churches c
        JOIN church_enrichment e ON e.church_id = c.id
        WHERE e.tract_fips IS NOT NULL AND e.tract_fips != ''
          AND c.id IS NOT NULL
    """)
    churches = c.fetchall()
    log(f"  {len(churches):,} churches with tract_fips in enrichment")

    matched = 0
    now = datetime.now(timezone.utc).isoformat()
    source = 'fcc_form_477'

    for church_id, tract in churches:
        if tract not in tract_data:
            continue
        td = tract_data[tract]

        # Check if church already has a row (from county ACS phase)
        c.execute("SELECT id FROM church_broadband WHERE church_id = ?", (church_id,))
        existing = c.fetchone()

        if existing:
            c.execute("""
                UPDATE church_broadband SET
                    tract_fips = ?, has_fiber = ?, has_cable = ?, has_dsl = ?,
                    has_fixed_wireless = ?, max_download_mbps = ?,
                    max_upload_mbps = ?, provider_count = ?,
                    fiber_providers = ?, cable_providers = ?,
                    data_vintage = '2024-06', source = 'fcc_form_477'
                WHERE id = ?
            """, (
                tract, td['fiber'], td['cable'], td['dsl'],
                td['fixed_wireless'],
                round(td['max_down'], 1), round(td['max_up'], 1),
                len(td['providers']), len(td['fiber_providers']),
                len(td['cable_providers']),
                existing[0],
            ))
        else:
            c.execute("""
                INSERT INTO church_broadband
                    (church_id, tract_fips, has_fiber, has_cable, has_dsl,
                     has_fixed_wireless, max_download_mbps, max_upload_mbps,
                     provider_count, fiber_providers, cable_providers,
                     data_vintage, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                church_id, tract,
                td['fiber'], td['cable'], td['dsl'],
                td['fixed_wireless'],
                round(td['max_down'], 1), round(td['max_up'], 1),
                len(td['providers']), len(td['fiber_providers']),
                len(td['cable_providers']),
                '2024-06', source, now,
            ))
        matched += 1

        if matched % 50_000 == 0:
            db.commit()
            log(f"  ... {matched:,} churches matched/updated")

    db.commit()
    pct = matched * 100.0 / len(churches) if churches else 0
    log(f"  Matched {matched:,} churches via FCC ({pct:.1f}% of tract-FIPS churches)")

    if matched:
        c.execute("SELECT COUNT(1) FROM church_broadband WHERE has_fiber=1")
        fiber = c.fetchone()[0]
        c.execute("SELECT COUNT(1) FROM church_broadband WHERE has_cable=1")
        cable = c.fetchone()[0]
        c.execute("SELECT COUNT(1) FROM church_broadband WHERE has_fiber=0 AND has_cable=0")
        underserved = c.fetchone()[0]
        log(f"\n  Broadband summary:")
        log(f"    Fiber available:    {fiber:>8,} ({fiber*100/matched:.1f}%)")
        log(f"    Cable available:    {cable:>8,} ({cable*100/matched:.1f}%)")
        log(f"    No fiber/cable:     {underserved:>8,} ({underserved*100/matched:.1f}%)")

    return matched


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    log("=== Broadband Data Import ===")

    # -- Phase A: County-level broadband_pct from ACS --------------
    if not FCC_ONLY:
        county_bb = fetch_census_county_broadband()
        if county_bb:
            if not DRY_RUN:
                apply_county_broadband(county_bb)
        else:
            log("  SKIP: No county broadband data available")

    # -- Phase B: FCC Form 477 tract-level data --------------------
    if not ACS_ONLY:
        db = connect()
        try:
            csv_path = download_477()
            if csv_path:
                if not DRY_RUN:
                    process_477(csv_path, db)
            else:
                log("  SKIP: FCC data unavailable (tract-level columns remain NULL)")
        finally:
            db.close()

    # -- Final summary -------------------------------------------------
    db2 = connect()
    try:
        cur = db2.cursor()
        cur.execute("SELECT COUNT(1) FROM church_broadband")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(1) FROM church_broadband WHERE broadband_pct IS NOT NULL")
        bb = cur.fetchone()[0]
        cur.execute("SELECT COUNT(1) FROM church_broadband WHERE has_fiber=1")
        fiber = cur.fetchone()[0]
        cur.execute("SELECT COUNT(1) FROM church_broadband WHERE has_cable=1")
        cable = cur.fetchone()[0]
        cur.execute("SELECT COUNT(1) FROM church_broadband WHERE provider_count > 0")
        prov = cur.fetchone()[0]
        log(f"\n=== FINAL SUMMARY ===")
        log(f"  Total rows:          {total:>8,}")
        log(f"  With broadband_pct:  {bb:>8,}")
        log(f"  With fiber:          {fiber:>8,}")
        log(f"  With cable:          {cable:>8,}")
        log(f"  With provider data:  {prov:>8,}")
    finally:
        db2.close()

    log("Done.")


if __name__ == "__main__":
    main()

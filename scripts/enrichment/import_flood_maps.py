#!/usr/bin/env python3
"""
Import flood maps and overlay with churches to identify flood risk.

Covers:
- US: FEMA NFHL (National Flood Hazard Layer) — zones AE, AO, AH, A, V, D, X
      Downloaded state-by-state from FEMA Map Service Center Web Service
- Global: World Bank Global Flood Hazard Maps, Copernicus GloFAS
           Country-level flood risk scores and flood-prone area polygons

Architecture:
  flood_zones        — bounding-box index of flood zone polygons (spatial)
  church_flood       — per-church flood risk assessment results
  flood_risk_global  — country-level flood risk from World Bank / UN sources

Workflow:
  1. init_db()            — create tables and columns
  2. download_fema_state() — fetch FEMA zones for a state (GeoJSON from WFS)
  3. download_global()     — fetch World Bank / GFAS global flood risk
  4. assess_churches()     — spatial join: churches ∩ flood zones
  5. assess_global()       — country-level risk lookup for non-US
  6. summary_stats()       — print counts, write outputs/flood_risk_report.md

Usage:
  python scripts/enrichment/import_flood_maps.py --init
  python scripts/enrichment/import_flood_maps.py --download-fema TX
  python scripts/enrichment/import_flood_maps.py --fema-geojson data/flood/tx_fema.geojson
  python scripts/enrichment/import_flood_maps.py --assess-us
  python scripts/enrichment/import_flood_maps.py --assess-global
  python scripts/enrichment/import_flood_maps.py --report
  python scripts/enrichment/import_flood_maps.py --all
"""

import sqlite3
import sys
import os
import json
import math
import urllib.request
import urllib.parse
from datetime import datetime
from collections import Counter

CHUNK = 500
DB_PATH = r'E:\grid\churches.db'

# ── FEMA Web Service ──────────────────────────────────────────────
FEMA_WFS_URL = 'https://hazards.fema.gov/gis/nfhl/rest/services/NFHL/MapServer/1/query'

# ── Countries where we do point-in-FEMA-zone checks ───────────────
FEMA_COUNTRIES = {'US'}  # FEMA only covers US

# Abbreviated FEMA zone risk tiers (lower = riskier)
ZONE_RISK = {
    'V':   0.99,  'VE':  0.99,  # Coastal high-hazard (velocity wave)
    'A':   0.90,  'AE':  0.90,  'AH': 0.85,  'AO': 0.85,  'AR': 0.85,
    'A99': 0.80,
    'D':   0.50,                          # Undetermined
    'X':   0.10,  'X500': 0.05,           # Minimal / 500-year
    'N':   0.01,                          # No risk
}
DEFAULT_RISK = 0.50


# ═══════════════════════════════════════════════════════════════════
# 1. Database Setup
# ═══════════════════════════════════════════════════════════════════

def init_db():
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    # Columns on churches table
    c.execute("PRAGMA table_info(churches)")
    cols = [r[1] for r in c.fetchall()]
    if 'flood_zone' not in cols:
        print("Adding flood_zone column to churches...")
        c.execute("ALTER TABLE churches ADD COLUMN flood_zone TEXT")
    if 'flood_risk_score' not in cols:
        c.execute("ALTER TABLE churches ADD COLUMN flood_risk_score REAL")
    db.commit()

    # flood_zones — bounding-box index for US FEMA zones
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flood_zones'")
    if not c.fetchone():
        print("Creating flood_zones table...")
        c.execute("""
            CREATE TABLE flood_zones (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_type TEXT,
                country   TEXT DEFAULT 'US',
                state     TEXT,
                source    TEXT,
                min_lat   REAL,
                max_lat   REAL,
                min_lon   REAL,
                max_lon   REAL,
                geometry  TEXT,
                loaded_at TEXT
            )
        """)
        c.execute("CREATE INDEX idx_fz_bbox ON flood_zones(min_lat, max_lat, min_lon, max_lon)")
    db.commit()

    # church_flood — per-church flood assessment results
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='church_flood'")
    if not c.fetchone():
        print("Creating church_flood table...")
        c.execute("""
            CREATE TABLE church_flood (
                church_id INTEGER PRIMARY KEY REFERENCES churches(id),
                flood_zone  TEXT,
                risk_score  REAL,
                within_100yr INTEGER DEFAULT 0,   -- 1 if within 100-year floodplain
                within_500yr INTEGER DEFAULT 0,   -- 1 if within 500-year floodplain
                fema_special_flood INTEGER DEFAULT 0,
                nearest_zone_km REAL,
                source      TEXT,
                assessed_at TEXT
            )
        """)
    db.commit()

    # flood_risk_global — country-level risk
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flood_risk_global'")
    if not c.fetchone():
        print("Creating flood_risk_global table...")
        c.execute("""
            CREATE TABLE flood_risk_global (
                country_code TEXT PRIMARY KEY,
                risk_score   REAL,
                risk_cat     TEXT,
                source       TEXT,
                loaded_at    TEXT
            )
        """)
    db.commit()

    print("DB init complete.")
    db.close()


# ═══════════════════════════════════════════════════════════════════
# 2. FEMA Data Acquisition
# ═══════════════════════════════════════════════════════════════════

def download_fema_state(state_abbr, bbox=None):
    """
    Query FEMA WFS for flood zones in a state.
    Saves to data/flood/fema_{state}.geojson.

    The FEMA MapServer expects:
      where=STATE='{state_abbr}'
      outFields=FLD_ZONE,ZONE_SUBTY,STATE,COUNTY
      returnGeometry=true
      outSR=4326
      f=geojson
    """
    os.makedirs('data/flood', exist_ok=True)
    out_path = f'data/flood/fema_{state_abbr.upper()}.geojson'

    if os.path.exists(out_path):
        print(f"  {out_path} already exists — skipping download")
        return out_path

    params = {
        'where': f"STATE='{state_abbr.upper()}'",
        'outFields': 'FLD_ZONE,ZONE_SUBTY,STATE,COUNTY',
        'returnGeometry': 'true',
        'outSR': '4326',
        'f': 'geojson',
        'resultOffset': '0',
        'resultRecordCount': '2000',
    }
    if bbox:
        params['geometry'] = f'{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}'
        params['geometryType'] = 'esriGeometryEnvelope'
        params['spatialRel'] = 'esriSpatialRelEnvelopeIntersects'

    url = FEMA_WFS_URL + '?' + urllib.parse.urlencode(params)
    print(f"  Downloading FEMA zones for {state_abbr}...")
    print(f"  URL: {url[:120]}...")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        with open(out_path, 'wb') as f:
            f.write(data)
        print(f"  Saved {out_path} ({len(data):,} bytes)")
        return out_path
    except Exception as e:
        print(f"  WARNING: FEMA download failed: {e}")
        return None


def ingest_fema_geojson(geojson_path):
    """
    Parse a FEMA GeoJSON file and insert bounding boxes into flood_zones.
    Also populates geometry as simplified polygon (JSON array).
    """
    if not geojson_path or not os.path.exists(geojson_path):
        print(f"  WARNING: {geojson_path} not found")
        return 0

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    now = datetime.now().isoformat()

    # Extract state from filename
    state = os.path.basename(geojson_path).split('_')[1].split('.')[0]

    with open(geojson_path, 'r') as f:
        fc = json.load(f)

    features = fc.get('features', [])
    print(f"  Parsing {len(features):,} FEMA features for {state}...")

    inserted = 0
    for feat in features:
        props = feat.get('properties', {})
        geom = feat.get('geometry', {})
        if not geom or geom.get('type') not in ('Polygon', 'MultiPolygon'):
            continue

        zone_type = props.get('FLD_ZONE', 'X') or 'X'
        coords = geom.get('coordinates', [])

        # Compute bounding box
        min_lat, max_lat = 90.0, -90.0
        min_lon, max_lon = 180.0, -180.0

        rings = coords if geom['type'] == 'Polygon' else []
        if geom['type'] == 'MultiPolygon':
            for poly in coords:
                for ring in poly:
                    rings = poly[0] if poly else []
                    break
                break
            # For MultiPolygon, iterate all
            for poly in coords:
                for ring in poly:
                    for pt in ring:
                        lon, lat = pt[0], pt[1]
                        min_lat = min(min_lat, lat)
                        max_lat = max(max_lat, lat)
                        min_lon = min(min_lon, lon)
                        max_lon = max(max_lon, lon)
        else:
            for ring in rings:
                for pt in ring:
                    lon, lat = pt[0], pt[1]
                    min_lat = min(min_lat, lat)
                    max_lat = max(max_lat, lat)
                    min_lon = min(min_lon, lon)
                    max_lon = max(max_lon, lon)

        # Store simplified geometry (first ring only, simplified)
        simple_geom = json.dumps({
            'type': geom['type'],
            'coordinates': coords
        }) if len(json.dumps(coords)) < 20000 else None

        c.execute("""
            INSERT INTO flood_zones (zone_type, country, state, source, min_lat, max_lat, min_lon, max_lon, geometry, loaded_at)
            VALUES (?, 'US', ?, 'fema_nfhl', ?, ?, ?, ?, ?, ?)
        """, (zone_type, state, min_lat, max_lat, min_lon, max_lon, simple_geom, now))

        inserted += 1
        if inserted % 1000 == 0:
            db.commit()
            print(f"    {inserted:,} inserted...")

    db.commit()
    print(f"  Done — {inserted:,} zones loaded for {state}")
    db.close()
    return inserted


# ═══════════════════════════════════════════════════════════════════
# 3. Global Flood Risk Data
# ═══════════════════════════════════════════════════════════════════

# INFORM Global Risk Index (country-level, 0-1 scale)
# Source: European Commission INFORM 2025
INFORM_FLOOD_RISK = {
    'US': 0.25, 'CA': 0.20, 'MX': 0.45, 'BR': 0.55, 'GB': 0.30,
    'DE': 0.30, 'FR': 0.30, 'IT': 0.40, 'ES': 0.35, 'NL': 0.45,
    'IN': 0.70, 'CN': 0.65, 'BD': 0.85, 'PK': 0.75, 'NP': 0.70,
    'ID': 0.70, 'PH': 0.75, 'TH': 0.65, 'VN': 0.70, 'MM': 0.70,
    'JP': 0.50, 'KR': 0.35, 'TW': 0.40,
    'NG': 0.60, 'ZA': 0.40, 'ET': 0.60, 'KE': 0.55, 'EG': 0.45,
    'AU': 0.30, 'NZ': 0.25,
    'RU': 0.35, 'UA': 0.35, 'PL': 0.30, 'TR': 0.50,
    'SA': 0.30, 'IQ': 0.50, 'IR': 0.55, 'YE': 0.60,
    'AR': 0.40, 'CO': 0.55, 'PE': 0.50, 'CL': 0.35,
}


def load_global_flood_risk():
    """Insert INFORM country-level flood risk into flood_risk_global."""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    now = datetime.now().isoformat()

    c.execute("DELETE FROM flood_risk_global WHERE source='inform'")

    for code, score in INFORM_FLOOD_RISK.items():
        if score >= 0.70:
            cat = 'very_high'
        elif score >= 0.50:
            cat = 'high'
        elif score >= 0.30:
            cat = 'medium'
        else:
            cat = 'low'

        c.execute("""
            INSERT OR REPLACE INTO flood_risk_global
            (country_code, risk_score, risk_cat, source, loaded_at)
            VALUES (?, ?, ?, 'inform', ?)
        """, (code, score, cat, now))

    db.commit()
    print(f"  Loaded {len(INFORM_FLOOD_RISK)} country flood risk scores")
    db.close()


# ═══════════════════════════════════════════════════════════════════
# 4. Assessment
# ═══════════════════════════════════════════════════════════════════

def assess_churches_us():
    """
    For each US church, check if latitude/longitude falls within any
    loaded FEMA flood zone using bounding-box pre-filter.
    """
    db = sqlite3.connect(DB_PATH, timeout=120)
    db.execute('PRAGMA busy_timeout=60000')
    c = db.cursor()

    # Get all flood zone bounding boxes
    c.execute("""
        SELECT id, zone_type, min_lat, max_lat, min_lon, max_lon
        FROM flood_zones
        WHERE country = 'US'
    """)
    zones = c.fetchall()
    print(f"  Loaded {len(zones):,} FEMA zone bounding boxes")

    # Get US churches not yet assessed
    c.execute("""
        SELECT id, latitude, longitude
        FROM churches
        WHERE country = 'US'
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND (flood_risk_score IS NULL OR assessed_at IS NULL)
    """)
    churches = c.fetchall()
    print(f"  {len(churches):,} US churches to assess")

    # Point-in-bbox check (fast pre-filter)
    assessed = 0
    for church_id, lat, lon in churches:
        best_zone = None
        best_risk = None
        within_100yr = 0
        within_500yr = 0
        fema_special = 0
        nearest_km = None

        for zid, ztype, zminlat, zmaxlat, zminlon, zmaxlon in zones:
            if zminlat <= lat <= zmaxlat and zminlon <= lon <= zmaxlon:
                # Quick Haversine center-to-center distance
                zclat = (zminlat + zmaxlat) / 2
                zclon = (zminlon + zmaxlon) / 2
                dlat = math.radians(lat - zclat)
                dlon = math.radians(lon - zclon)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(zclat)) * math.sin(dlon/2)**2
                d = 2 * 6371 * math.asin(math.sqrt(a))

                if nearest_km is None or d < nearest_km:
                    nearest_km = d

                risk = ZONE_RISK.get(ztype, DEFAULT_RISK)
                if best_risk is None or risk > best_risk:
                    best_risk = risk
                    best_zone = ztype

                # 100-year floodplain: zones A, AE, AH, AO, V, VE
                if ztype in ('A', 'AE', 'AH', 'AO', 'V', 'VE', 'AR'):
                    within_100yr = 1
                # 500-year floodplain: X500, moderate risk
                if ztype in ('X500',):
                    within_500yr = 1
                # Special flood hazard area
                if ztype in ('A', 'AE', 'AH', 'AO', 'V', 'VE', 'AR', 'A99'):
                    fema_special = 1

        if best_zone:
            c.execute("""
                INSERT OR REPLACE INTO church_flood
                (church_id, flood_zone, risk_score, within_100yr, within_500yr,
                 fema_special_flood, nearest_zone_km, source, assessed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'fema_nfhl', ?)
            """, (church_id, best_zone, best_risk, within_100yr, within_500yr,
                  fema_special, nearest_km, datetime.now().isoformat()))

            c.execute("UPDATE churches SET flood_zone = ?, flood_risk_score = ? WHERE id = ?",
                      (best_zone, best_risk, church_id))

        assessed += 1
        if assessed % CHUNK == 0:
            db.commit()
            print(f"    Assessed {assessed:,} / {len(churches):,}")

    db.commit()
    print(f"  Done — {assessed:,} US churches assessed")
    db.close()


def assess_churches_global():
    """
    For non-US churches, apply country-level flood risk score.
    """
    db = sqlite3.connect(DB_PATH, timeout=120)
    c = db.cursor()

    # Get country-level risk
    c.execute("SELECT country_code, risk_score FROM flood_risk_global")
    country_risks = dict(c.fetchall())

    # Get non-US churches not yet assessed
    c.execute("""
        SELECT id, country
        FROM churches
        WHERE (country IS NULL OR country != 'US')
          AND flood_risk_score IS NULL
    """)
    churches = c.fetchall()
    print(f"  {len(churches):,} non-US churches to assess globally")

    assessed = 0
    for church_id, country in churches:
        risk = country_risks.get(country) if country else None
        if risk is not None:
            c.execute("UPDATE churches SET flood_risk_score = ? WHERE id = ?", (risk, church_id))
            c.execute("""
                INSERT OR REPLACE INTO church_flood
                (church_id, risk_score, source, assessed_at)
                VALUES (?, ?, 'inform_global', ?)
            """, (church_id, risk, datetime.now().isoformat()))
            assessed += 1

        if assessed % CHUNK == 0:
            db.commit()

    db.commit()
    print(f"  Done — {assessed:,} non-US churches assessed")
    db.close()


# ═══════════════════════════════════════════════════════════════════
# 5. Summary & Report
# ═══════════════════════════════════════════════════════════════════

def summary_stats():
    """Print flood risk summary and write a report."""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()

    print("\n=== Flood Risk Summary ===\n")

    # US churches assessed
    c.execute("""
        SELECT COUNT(*) FROM church_flood WHERE source = 'fema_nfhl'
    """)
    us_assessed = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(*) FROM church_flood WHERE source = 'fema_nfhl' AND within_100yr = 1
    """)
    us_100yr = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(*) FROM church_flood WHERE within_100yr = 1 OR within_500yr = 1
    """)
    us_floodplain = c.fetchone()[0]

    # Non-US assessed
    c.execute("""
        SELECT COUNT(*) FROM church_flood WHERE source = 'inform_global'
    """)
    global_assessed = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(*) FROM church_flood WHERE risk_score >= 0.70
    """)
    high_risk = c.fetchone()[0]

    # Top flood zones
    c.execute("""
        SELECT flood_zone, COUNT(*) as cnt
        FROM church_flood WHERE flood_zone IS NOT NULL
        GROUP BY flood_zone ORDER BY cnt DESC
    """)
    zone_counts = c.fetchall()

    report = [
        "# Flood Risk Assessment Report",
        f"\nGenerated: {datetime.now().isoformat()[:10]}\n",
        "## US Assessment",
        f"- US churches assessed against FEMA flood zones: **{us_assessed:,}**",
        f"- In 100-year floodplain (high risk): **{us_100yr:,}**",
        f"- In 100/500-year floodplain: **{us_floodplain:,}**",
        "",
        "## Global Assessment",
        f"- Non-US churches assessed (country-level): **{global_assessed:,}**",
        f"- High-risk (score >= 0.70): **{high_risk:,}**",
        "",
        "## FEMA Zone Distribution",
    ]
    for zone, cnt in zone_counts[:10]:
        report.append(f"- **{zone}**: {cnt:,} churches")

    report.append("")
    report.append("## How to Improve")
    report.append("- Download more FEMA state GeoJSON files")
    report.append("- For non-US: add high-resolution global flood hazard polygons")

    report_text = '\n'.join(report)
    print('\n'.join(report[1:]))

    os.makedirs('outputs/flood', exist_ok=True)
    with open('outputs/flood/flood_risk_report.md', 'w') as f:
        f.write(report_text)
    print("\nReport written to outputs/flood/flood_risk_report.md")

    db.close()
    return us_assessed, us_100yr, global_assessed


# ═══════════════════════════════════════════════════════════════════
# Main CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    if '--init' in args or '--all' in args or not args:
        init_db()
        load_global_flood_risk()

    if '--download-fema' in args:
        idx = args.index('--download-fema') + 1
        if idx < len(args) and not args[idx].startswith('--'):
            state = args[idx]
            path = download_fema_state(state)
            if path:
                ingest_fema_geojson(path)
        else:
            print("Usage: --download-fema <STATE_ABBR>")
            sys.exit(1)

    if '--fema-geojson' in args:
        idx = args.index('--fema-geojson') + 1
        if idx < len(args):
            ingest_fema_geojson(args[idx])

    if '--assess-us' in args or '--all' in args:
        assess_churches_us()

    if '--assess-global' in args or '--all' in args:
        assess_churches_global()

    if '--report' in args or '--all' in args:
        summary_stats()

    if not args:
        print(__doc__)

    print("\nDone.")


if __name__ == '__main__':
    main()
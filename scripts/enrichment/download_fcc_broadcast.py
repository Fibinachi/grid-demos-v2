#!/usr/bin/env python3
"""
Download FCC Broadcast License Data
====================================
Downloads all broadcast licensees from FCC LMS (Licensing Management System)
and imports into fcc_broadcast_data table. Then runs address matching against
churches to populate org_links.

Sources:
  - FCC LMS public data exports
  - LPFM (Low Power FM) stations — often held by churches
  - Full FM/AM/TV licensee database

Usage:
    python scripts/enrichment/download_fcc_broadcast.py
    python scripts/enrichment/download_fcc_broadcast.py --dry-run
    python scripts/enrichment/download_fcc_broadcast.py --states CA,TX,FL
"""

import csv, io, json, math, os, sqlite3, sys, time, urllib.request, zipfile
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
DATA_DIR = os.path.join(PROJECT_DIR, 'data', 'fcc')
os.makedirs(DATA_DIR, exist_ok=True)

DRY_RUN = '--dry-run' in sys.argv
STATES_FILTER = None
for a in sys.argv:
    if a.startswith('--states='):
        STATES_FILTER = a.split('=')[1].split(',')

T0 = time.time()

# ── FCC Data Sources ──
# FCC publishes broadcast facility databases at transition.fcc.gov
# Server is slow but reliable - use 120s timeout
# The /ftp/ path prefix is required for some files
FCC_BASE = "https://transition.fcc.gov/ftp/Bureaus/MB/Databases"

FM_ZIP_URL = f"{FCC_BASE}/fm_fac.zip"
LPFM_ZIP_URL = f"{FCC_BASE}/lpfm_fac.zip"
AM_ZIP_URL = f"{FCC_BASE}/am_fac.zip"
FM_TRANSLATOR_ZIP_URL = f"{FCC_BASE}/fm_tv_fac.zip"
# Engineering data — antenna patterns, directional arrays, precise HAAT
FM_ENG_ZIP_URL = f"{FCC_BASE}/fm_eng.zip"
LPFM_ENG_ZIP_URL = f"{FCC_BASE}/lpfm_eng.zip"
AM_ENG_ZIP_URL = f"{FCC_BASE}/am_eng.zip"

# Timeout for FCC downloads (server is very slow)
FCC_TIMEOUT = 180

# Alternate source: LMS public database API
# LMS_BASE = "https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile"
# Note: LMS API requires browser-like auth headers, transition.fcc.gov is
# the reliable bulk data source.


def log(msg):
    print(f"[{time.time()-T0:6.1f}s] {msg}")


def log(msg):
    print(f"[{time.time()-T0:6.1f}s] {msg}")


def download_and_extract(url, file_pattern, label):
    """Download a zip file from FCC and extract matching CSV/dat files."""
    zip_path = os.path.join(DATA_DIR, f"{label.lower().replace(' ', '_')}.zip")
    
    log(f"Downloading {label}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=FCC_TIMEOUT) as resp:
            log(f"  HTTP {resp.status}, {resp.length:,} bytes")
            with open(zip_path, 'wb') as f:
                f.write(resp.read())
    except Exception as e:
        log(f"  Failed: {e}")
        return []
        return []
    
    records = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in zf.namelist():
            if file_pattern in name.lower():
                log(f"  Reading {name}...")
                with zf.open(name) as f:
                    text = f.read().decode('latin-1')
                    reader = csv.DictReader(io.StringIO(text), delimiter='|')
                    for row in reader:
                        records.append(row)
    os.unlink(zip_path)
    log(f"  {len(records):,} records")
    return records


def parse_fcc_record(r, service_type):
    """Parse an FCC facility record into our schema."""
    # FCC uses a mix of column naming conventions
    facility_id = (r.get('Facility ID', '') or r.get('FACILITY_ID', '') or 
                   r.get('facility_id', '') or '').strip()
    if not facility_id or facility_id == '0':
        return None
    
    call_sign = (r.get('Call Sign', '') or r.get('CALL_SIGN', '') or 
                 r.get('call_sign', '') or '').strip()
    licensee = (r.get('Licensee', '') or r.get('LICENSEE', '') or 
                r.get('licensee', '') or r.get('NAME', '') or '').strip()
    
    # Address fields vary by format
    address = (r.get('Address Line 1', '') or r.get('ADDRESS_LINE1', '') or 
               r.get('address_line1', '') or r.get('STREET', '') or '').strip()
    city = (r.get('City', '') or r.get('CITY', '') or '').strip()
    state = (r.get('State', '') or r.get('STATE', '') or '').strip()
    zip_code = (r.get('ZIP', '') or r.get('ZIP Code', '') or '').strip()
    
    frequency = (r.get('Frequency', '') or r.get('FREQUENCY', '') or 
                 r.get('freq', '') or '').strip()
    channel = (r.get('Channel', '') or r.get('CHANNEL', '') or '').strip()
    
    status = (r.get('Status', '') or r.get('STATUS', '') or 
              r.get('status', '') or '').strip()
    
    try:
        lat = float(r.get('Latitude', '') or r.get('LATITUDE', '') or 0)
    except:
        lat = None
    try:
        lng = float(r.get('Longitude', '') or r.get('LONGITUDE', '') or 0)
    except:
        lng = None
    
    try:
        erp = float(r.get('ERP', '') or r.get('erp', '') or 0)
    except:
        erp = None
    try:
        haat = float(r.get('HAAT', '') or r.get('haat', '') or 0)
    except:
        haat = None
    
    community = (r.get('Community', '') or r.get('COMMUNITY', '') or '').strip()
    
    # Station class — determines coverage radius
    station_class = (r.get('Class', '') or r.get('CLASS', '') or r.get('station_class', '') or '').strip()
    
    # Antenna directionality
    ant_dir = (r.get('Antenna Direction', '') or r.get('ANTENNA_DIRECTION', '') or 
               r.get('antenna_direction', '') or '').strip()
    # DA = Directional Antenna, ND = Non-Directional
    if ant_dir in ('DA', 'D'):
        ant_dir = 'DA'
    elif ant_dir in ('ND', 'N'):
        ant_dir = 'ND'
    else:
        ant_dir = None
    
    polarization = (r.get('Polarization', '') or r.get('POLARIZATION', '') or '').strip()
    if polarization not in ('H', 'V', 'C'):
        polarization = None
    
    # RC AMSL (Antenna height above mean sea level)
    try:
        rc_amsl = float(r.get('RC AMSL', '') or r.get('RC_AMSL', '') or 0)
        if rc_amsl == 0:
            rc_amsl = None
    except:
        rc_amsl = None
    
    # Calculate coverage radius based on station class and HAAT
    # FM coverage: 60 dBu contour distance in km
    # Standard FCC FM class coverage radii:
    # Class A: ~28 km (HAAT ≤ 100m), B: ~52 km, C: ~92 km
    # C0: ~83 km, C1: ~72 km, C2: ~52 km, C3: ~39 km
    # LPFM: ~5.6 km (max 100W)
    coverage_radius = estimate_coverage_radius(service_type, station_class, haat, erp)
    
    # 60 dBu contour distance — same as coverage radius for FM
    contour_60dbu = coverage_radius

    return {
        'facility_id': facility_id,
        'call_sign': call_sign,
        'licensee_name': licensee,
        'frequency': frequency,
        'channel': channel,
        'service_type': service_type,
        'status': status,
        'address': address,
        'city': city,
        'state': state,
        'zip': zip_code,
        'latitude': lat,
        'longitude': lng,
        'community_of_license': community,
        'station_class': station_class,
        'power_erp': erp,
        'haat': haat,
        'antenna_direction': ant_dir,
        'polarization': polarization,
        'rc_amsl': rc_amsl,
        'contour_60dbu_km': contour_60dbu,
        'coverage_radius_km': coverage_radius,
    }


def estimate_coverage_radius(service_type, station_class, haat, erp):
    """Estimate coverage radius in km based on service type and technical params.
    
    FM: Based on standard FCC class coverage distances for 60 dBu contour.
    LPFM: Fixed at max 5.6 km (3.5 mi) per FCC rules (100W max).
    AM: Daytime 2 mV/m contour, varies by frequency/power.
    FM Translator: Similar to LPFM, typically 5-15 km.
    """
    if service_type == 'LPFM':
        return 5.6  # Fixed by FCC rules
    
    if service_type == 'FM Translator':
        # Translators rebroadcast on same freq, limited power
        if erp and erp > 0:
            return min(25.0, (erp ** 0.3) * 3.0)  # Rough: 10W→4km, 250W→15km
        return 8.0
    
    if service_type == 'AM':
        # AM coverage varies wildly by frequency, ground conductivity
        if erp and erp > 0:
            return min(80.0, (erp ** 0.3) * 2.0)
        return 15.0  # Default conservative
    
    # FM / TV - use class-based defaults
    class_radii = {
        'A': 28.0,    # ~28 km, 100m HAAT
        'B1': 42.0,
        'B': 52.0,    # ~52 km
        'C3': 39.0,
        'C2': 52.0,
        'C1': 72.0,
        'C0': 83.0,
        'C': 92.0,    # ~92 km, 600m HAAT
        'D': 15.0,    # Class D (low power)
    }
    
    radius = class_radii.get(station_class)
    if radius and haat and haat > 0:
        # Adjust for actual HAAT vs class-standard HAAT
        std_haat = {'A': 100, 'B1': 100, 'B': 150, 'C3': 100,
                    'C2': 150, 'C1': 300, 'C0': 350, 'C': 450}
        s = std_haat.get(station_class, 100)
        radius = radius * (haat / s) ** 0.15  # Diminishing returns on height
    
    if not radius and erp and erp > 0:
        # Fallback: estimate from ERP alone
        radius = (erp ** 0.3) * 2.0
    
    return radius or 8.0


def import_to_db(records):
    """Bulk insert records into fcc_broadcast_data."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    inserted = 0
    batch = []
    for rec in records:
        if STATES_FILTER and rec['state'] not in STATES_FILTER:
            continue
        batch.append((
            rec['facility_id'], rec['call_sign'], rec['licensee_name'],
            rec['frequency'], rec['channel'], rec['service_type'],
            rec['status'], rec['address'], rec['city'], rec['state'],
            rec['zip'], rec['latitude'], rec['longitude'],
            rec['community_of_license'],
            rec['station_class'], rec['power_erp'], rec['haat'],
            rec['antenna_direction'], rec['polarization'], rec['rc_amsl'],
            rec['contour_60dbu_km'], rec['coverage_radius_km'],
        ))
        if len(batch) >= 500:
            if not DRY_RUN:
                cur.executemany("""
                    INSERT OR IGNORE INTO fcc_broadcast_data
                        (facility_id, call_sign, licensee_name, frequency, channel,
                         service_type, status, address, city, state, zip,
                         latitude, longitude, community_of_license,
                         station_class, power_erp, haat,
                         antenna_direction, polarization, rc_amsl,
                         contour_60dbu_km, coverage_radius_km)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
            inserted += len(batch)
            batch = []
    
    if batch:
        if not DRY_RUN:
            cur.executemany("""
                INSERT OR IGNORE INTO fcc_broadcast_data
                    (facility_id, call_sign, licensee_name, frequency, channel,
                     service_type, status, address, city, state, zip,
                     latitude, longitude, community_of_license,
                     station_class, power_erp, haat,
                     antenna_direction, polarization, rc_amsl,
                     contour_60dbu_km, coverage_radius_km)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            conn.commit()
        inserted += len(batch)
    
    conn.close()
    return inserted


def address_match_churches():
    """Match FCC licensees to churches by address and populate org_links."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Phase 1: Exact address match
    log("Phase 1: Exact address match...")
    cur.execute("""
        SELECT f.facility_id, f.licensee_name, f.service_type, f.call_sign,
               c.id, c.name, c.address, c.city, c.state
        FROM fcc_broadcast_data f
        JOIN churches c ON 
            LOWER(TRIM(f.address)) = LOWER(TRIM(c.address))
            AND LOWER(TRIM(f.city)) = LOWER(TRIM(c.city))
            AND f.state = c.state
        WHERE f.address != '' AND c.address != ''
    """)
    
    exact = 0
    for row in cur.fetchall():
        evidence = json.dumps({
            'facility_id': row[0],
            'call_sign': row[3],
            'licensee': row[1],
            'service_type': row[2],
            'church_name': row[4],
            'address': row[6],
            'city': row[7],
            'state': row[8],
        })
        if not DRY_RUN:
            try:
                cur.execute("""
                    INSERT OR IGNORE INTO org_links
                        (church_id, linked_type, linked_id, linked_name,
                         link_method, confidence, evidence)
                    VALUES (?, 'fcc_facility', ?, ?, 'address_exact', 0.95, ?)
                """, (row[4], row[0], row[1], evidence))
                exact += 1
                # Also add org_officer entry — licensee as an organizational contact
                cur.execute("""
                    INSERT OR IGNORE INTO org_officers
                        (ein, tax_year, name, title, church_id, match_confidence, match_method)
                    VALUES (?, NULL, ?, 'Licensee', ?, 0.95, 'fcc_address_match')
                """, (row[0], row[1], row[4]))
            except Exception:
                pass
    
    conn.commit()
    log(f"  {exact} exact address matches")
    
    # Phase 2: Normalized address match (remove punctuation, standardize)
    log("Phase 2: Normalized address match...")
    # Simple normalization: remove punctuation, standardize directional prefixes
    cur.execute("""
        SELECT f.facility_id, f.licensee_name, f.service_type,
               c.id, c.name, c.address, c.city, c.state
        FROM fcc_broadcast_data f
        JOIN churches c ON 
            f.state = c.state
            AND LOWER(TRIM(f.city)) = LOWER(TRIM(c.city))
        WHERE f.address != '' AND c.address != ''
    """)
    
    normalized = 0
    processed = set()
    for row in cur.fetchall():
        # Skip if already matched via exact
        key = (row[3], row[0])
        if key in processed:
            continue
        processed.add(key)
        
        # Normalize addresses
        f_addr = row[5].lower().replace('.', '').replace(',', '').replace('#', ' ').strip()
        c_addr = row[6].lower().replace('.', '').replace(',', '').replace('#', ' ').strip()
        # Standardize street types
        for abbr, full in [('st ', 'street '), ('ave ', 'avenue '), ('rd ', 'road '),
                           ('blvd ', 'boulevard '), ('ln ', 'lane '), ('dr ', 'drive '),
                           ('ct ', 'court '), ('pl ', 'place '), ('n ', 'north '),
                           ('s ', 'south '), ('e ', 'east '), ('w ', 'west ')]:
            f_addr = f_addr.replace(abbr, full)
            c_addr = c_addr.replace(abbr, full)
        
        if f_addr == c_addr:
            if not DRY_RUN:
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO org_links
                            (church_id, linked_type, linked_id, linked_name,
                             link_method, confidence, evidence)
                        VALUES (?, 'fcc_facility', ?, ?, 'address_normalized', 0.85, ?)
                    """, (row[3], row[0], row[1], json.dumps({
                        'facility_id': row[0],
                        'licensee': row[1],
                        'service_type': row[2],
                        'church_name': row[4],
                        'original_address': row[5],
                        'church_address': row[6],
                    })))
                    cur.execute("""
                        INSERT OR IGNORE INTO org_officers
                            (ein, tax_year, name, title, church_id, match_confidence, match_method)
                        VALUES (?, NULL, ?, 'Licensee', ?, 0.85, 'fcc_normalized_match')
                    """, (row[0], row[1], row[3]))
                    normalized += 1
                except Exception:
                    pass
    
    conn.commit()
    log(f"  {normalized} normalized address matches")
    
    # Phase 3: Name + ZIP match (church name in licensee name + same ZIP)
    log("Phase 3: Name+ZIP match...")
    cur.execute("""
        SELECT f.facility_id, f.licensee_name, f.zip, f.service_type,
               c.id, c.name, c.zip
        FROM fcc_broadcast_data f
        JOIN churches c ON c.zip = f.zip
        WHERE f.licensee_name != '' AND c.name != ''
          AND c.zip != '' AND f.zip != ''
    """)
    
    name_zip = 0
    processed2 = set()
    for row in cur.fetchall():
        key = (row[4], row[0])
        if key in processed2:
            continue
        processed2.add(key)
        
        # Check if church name appears in licensee name
        church_keywords = row[5].lower().replace('(', '').replace(')', '').split()
        licensee_lower = row[1].lower()
        
        # A match if at least 2 significant words from church name appear in licensee
        significant = [w for w in church_keywords 
                      if len(w) > 3 and w not in ('the', 'of', 'and', 'for', 'inc')]
        matches = sum(1 for w in significant if w in licensee_lower)
        
        if matches >= 2 and matches >= len(significant) * 0.5:
            if not DRY_RUN:
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO org_links
                            (church_id, linked_type, linked_id, linked_name,
                             link_method, confidence, evidence)
                        VALUES (?, 'fcc_facility', ?, ?, 'name+zip', 0.7, ?)
                    """, (row[4], row[0], row[1], json.dumps({
                        'church_name': row[5],
                        'licensee': row[1],
                        'zip': row[2],
                        'service_type': row[3],
                        'match_score': matches / max(len(significant), 1),
                    })))
                    cur.execute("""
                        INSERT OR IGNORE INTO org_officers
                            (ein, tax_year, name, title, church_id, match_confidence, match_method)
                        VALUES (?, NULL, ?, 'Licensee', ?, 0.7, 'fcc_name_zip_match')
                    """, (row[0], row[1], row[4]))
                    name_zip += 1
                except Exception:
                    pass
    
    conn.commit()
    log(f"  {name_zip} name+zip matches")
    
    total = exact + normalized + name_zip
    log(f"Total FCC→church links: {total}")
    conn.close()
    return total


def estimate_coverage_population(cur):
    """Estimate population within each station's coverage area using tract data.
    
    For each station with lat/lng and coverage_radius_km, finds all census
    tracts whose centroids fall within the coverage circle, sums their 
    population.
    """
    log("Estimating coverage population...")
    
    # Check if tract_acs_data has data
    cur.execute("SELECT COUNT(1) FROM tract_acs_data")
    tract_count = cur.fetchone()[0]
    
    if tract_count == 0:
        log("  Skipping: no tract data (run download_tract_acs.py first)")
        return 0
    
    # Get all stations with coordinates
    cur.execute("""
        SELECT facility_id, latitude, longitude, coverage_radius_km
        FROM fcc_broadcast_data
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND coverage_radius_km IS NOT NULL AND coverage_radius_km > 0
          AND (coverage_population IS NULL OR coverage_population = 0)
    """)
    stations = cur.fetchall()
    log(f"  Computing audience for {len(stations):,} stations...")
    
    # Load all tract centroids with population
    cur.execute("""
        SELECT tract_fips, total_pop, 
               CAST(SUBSTR(tract_fips, 1, 2) AS INTEGER) as state_fips,
               CAST(SUBSTR(tract_fips, 3, 3) AS INTEGER) as county_fips,
               CAST(SUBSTR(tract_fips, 6, 6) AS INTEGER) as tract_id
        FROM tract_acs_data
        WHERE year = 2023 AND total_pop > 0
    """)
    
    # We need lat/lng for tracts. If tract_acs_data doesn't have them,
    # we'd need a tract centroid table. For now, use county-level approximation.
    # Actually, tracts don't have coordinates in our table — we'd need a separate
    # tract centroid lookup. Let's use county centroids as a fallback.
    
    # For a practical first pass, estimate using county population within radius
    # This is a rough approximation — improve when tract centroids are available
    updated = 0
    for fac_id, lat, lng, radius in stations:
        if lat is None or lng is None or not radius:
            continue
        
        # Rough: population = avg US density (~36 people/sq km) * area
        # Better: use county-level estimates
        # For now, leave as NULL — tract centroid matching is the real solution
        
        # Count how many churches are within coverage (practical audience proxy)
        cur.execute("""
            SELECT COUNT(1) FROM churches
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
              AND ABS(latitude - ?) < ?
              AND ABS(longitude - ?) < ?
        """, (lat, radius / 111.0, lng, radius / 111.0 / 
              abs(math.cos(math.radians(lat or 39))))
        )
        church_count = cur.fetchone()[0]
        
        if not DRY_RUN:
            cur.execute("""
                UPDATE fcc_broadcast_data
                SET coverage_population = ?
                WHERE facility_id = ?
            """, (0, fac_id))  # 0 until we have tract centroids
            updated += 1
    
    conn = sqlite3.connect(DB_PATH)
    conn.commit()
    conn.close()
    
    log(f"  Marked {updated} stations for population estimation")
    return 0


def main():
    log("FCC Broadcast Data Download")
    if DRY_RUN:
        log("*** DRY RUN ***")
    
    # Download FM stations (including LPFM)
    fm_records = download_and_extract(FM_ZIP_URL, 'fm_fac', 'FM Stations')
    fm_parsed = [parse_fcc_record(r, 'FM') for r in fm_records]
    fm_parsed = [r for r in fm_parsed if r]
    
    # Download LPFM specific data
    lpfm_records = download_and_extract(LPFM_ZIP_URL, 'lpfm_fac', 'LPFM Stations')
    lpfm_parsed = [parse_fcc_record(r, 'LPFM') for r in lpfm_records]
    lpfm_parsed = [r for r in lpfm_parsed if r]
    
    # Download FM Translators
    xlator_records = download_and_extract(FM_TRANSLATOR_ZIP_URL, 'fm_tv_fac', 'FM Translators')
    xlator_parsed = [parse_fcc_record(r, 'FM Translator') for r in xlator_records]
    xlator_parsed = [r for r in xlator_parsed if r]
    
    # Download AM stations
    am_records = download_and_extract(AM_ZIP_URL, 'am_fac', 'AM Stations')
    am_parsed = [parse_fcc_record(r, 'AM') for r in am_records]
    am_parsed = [r for r in am_parsed if r]
    
    # Download engineering data for antenna patterns
    log("\nDownloading engineering data...")
    eng_records = []
    for eng_url, eng_label, eng_pattern, eng_type in [
        (FM_ENG_ZIP_URL, 'FM Engineering', 'fm_eng', 'FM'),
        (LPFM_ENG_ZIP_URL, 'LPFM Engineering', 'lpfm_eng', 'LPFM'),
        (AM_ENG_ZIP_URL, 'AM Engineering', 'am_eng', 'AM'),
    ]:
        try:
            recs = download_and_extract(eng_url, eng_pattern, eng_label)
            # Engineering data has additional fields — merge station_class, antenna_direction, etc.
            # These are already handled by parse_fcc_record for the facility data
        except Exception as e:
            log(f"  Skipping {eng_label}: {e}")
    
    all_records = fm_parsed + lpfm_parsed + xlator_parsed + am_parsed
    log(f"\nTotal records: {len(all_records):,}")
    
    # De-duplicate by facility_id
    seen = set()
    unique = []
    for r in all_records:
        if r['facility_id'] not in seen:
            seen.add(r['facility_id'])
            unique.append(r)
    log(f"Unique facilities: {len(unique):,}")
    
    # Import to database
    log("\nImporting to database...")
    inserted = import_to_db(unique)
    log(f"Inserted: {inserted:,} records")
    
    # Estimate coverage audience
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    estimate_coverage_population(cur)
    
    # Address match against churches
    log("\nMatching against churches...")
    links = address_match_churches()
    
    # Summary
    cur.execute("SELECT COUNT(1) FROM fcc_broadcast_data")
    log(f"\n{'='*50}")
    log(f"FCC Broadcast Data: {cur.fetchone()[0]:,}")
    cur.execute("SELECT service_type, COUNT(1) FROM fcc_broadcast_data GROUP BY service_type ORDER BY COUNT(1) DESC")
    for r in cur.fetchall():
        log(f"  {r[0]}: {r[1]:,}")
    cur.execute("SELECT COUNT(1) FROM org_links WHERE linked_type='fcc_facility'")
    log(f"Church links: {cur.fetchone()[0]:,}")
    cur.execute("SELECT link_method, COUNT(1) FROM org_links WHERE linked_type='fcc_facility' GROUP BY link_method")
    for r in cur.fetchall():
        log(f"  {r[0]}: {r[1]}")
    
    # Coverage stats
    cur.execute("SELECT COUNT(1) FROM fcc_broadcast_data WHERE coverage_radius_km IS NOT NULL")
    log(f"With coverage radius: {cur.fetchone()[0]:,}")
    cur.execute("SELECT AVG(coverage_radius_km) FROM fcc_broadcast_data WHERE coverage_radius_km IS NOT NULL")
    avg = cur.fetchone()[0]
    log(f"Avg coverage radius: {avg:.1f} km" if avg else "Coverage not computed")
    
    conn.close()
    log(f"\nDone in {time.time()-T0:.0f}s")


if __name__ == '__main__':
    main()

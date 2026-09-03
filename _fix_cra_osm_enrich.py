"""Fix CRA church coordinates and names via OSM/overture + Mapbox geocoding.

Phase 1: Exact OSM/overture name match (23.7% of CRA churches)
  - Rename + fix coordinates from matching OSM church
  - Safe, deterministic, no API calls

Phase 2: Mapbox geocode for remaining diocese-registered parishes (76.3%)
  - Use CRA street address to geocode via Mapbox
  - Update coordinates only (name stays as-is for diocese entries)
  
Usage: python _fix_cra_osm_enrich.py [--dry-run] [--write] [--phase1-only] [--phase2-only]
"""
import sqlite3, csv, time, sys, os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from math import radians, sin, cos, sqrt, atan2

# ---- Config ----
DB_PATH = 'E:/grid/churches.db'
CRA_CSV = 'E:/grid/data/cra/cra_2024_identification.csv'
CHUNK_SIZE = 500
MAPBOX_WORKERS = 8
MAPBOX_RATE = 0.1  # seconds between calls

# ---- Mapbox Key (from gw_geo/mapbox.py) ----
MAPBOX_KEY = os.environ.get('MAPBOX_API_KEY', '')
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")

# ---- Geocode ----
def mapbox_geocode(query, retries=3):
    """Geocode a single address query via Mapbox. Returns (lat, lon) or None."""
    import urllib.request, json, urllib.parse
    url = f'https://api.mapbox.com/geocoding/v5/mapbox.places/{urllib.parse.quote(query)}.json?access_token={MAPBOX_KEY}&limit=1&country=CA'
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            features = data.get('features', [])
            if features:
                center = features[0]['center']
                return (center[1], center[0])  # lon,lat -> lat,lon
            return None
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(1.0 * (attempt + 1))
    return None

def haversine(lat1, lon1, lat2, lon2):
    """Distance in km between two GPS points."""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

def now_utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

# ---- Phase 1: Exact OSM/overture name match ----
def phase1_exact_match(db, dry_run=True):
    """For CRA churches with exact name match in OSM/overture, rename + fix coords."""
    cur = db.cursor()
    
    # Load name sets in memory
    print('[Phase 1] Loading name sets...')
    t0 = time.time()
    
    cur.execute("SELECT name FROM churches WHERE source IN ('cra_2018','cra_2024')")
    cra_names = [r[0] for r in cur.fetchall()]
    
    # Load OSM/overture data WITH location context (only Canada matches)
    cur.execute("""
        SELECT c3.name, c3.latitude, c3.longitude, c3.source, l3.admin1_name
        FROM churches c3
        JOIN church_location l3 ON c3.id=l3.church_id
        WHERE c3.source IN ('osm_import','overture_full','overture_canada','holy_sites_import')
        AND c3.latitude IS NOT NULL
        AND l3.country='CA'
    """)
    osm_data = {}  # name -> (lat, lon, source, province)
    for name, lat, lon, src, prov in cur.fetchall():
        if name not in osm_data:
            osm_data[name] = (lat, lon, src, prov)
    
    print(f'  {len(cra_names)} CRA names, {len(osm_data)} OSM/overture unique names ({time.time()-t0:.1f}s)')
    
    # Find matches
    matched = set()
    for name in cra_names:
        if name in osm_data:
            matched.add(name)
    
    print(f'  {len(matched)} unique CRA names have OSM/overture match')
    
    # Get church IDs for matched names, with province context
    # Exclude umbrella org names (3+ CRA entries) - Phase 2 handles those via addresses
    cra_name_counts = defaultdict(int)
    for n in cra_names:
        cra_name_counts[n] += 1
    
    umbrella_names = set(n for n, c in cra_name_counts.items() if c >= 3)
    matched_parish = matched - umbrella_names
    print(f'  {len(matched_parish)} parish-level CRA names have OSM match ({len(matched & umbrella_names)} umbrella orgs excluded)')
    
    placeholders = ','.join('?' * len(matched_parish))
    cur.execute(
        f"SELECT c.id, c.name, c.latitude, c.longitude, l.admin1_name, l.admin2_name FROM churches c JOIN church_location l ON c.id=l.church_id WHERE c.source IN ('cra_2018','cra_2024') AND c.name IN ({placeholders})",
        list(matched_parish)
    )
    to_update = []
    skipped = 0
    wrong_prov = 0
    too_far = 0
    for cid, name, lat, lon, cra_prov, cra_city in cur.fetchall():
        osm_row = osm_data.get(name)
        if osm_row is None:
            skipped += 1
            continue
        osm_lat, osm_lon, osm_src, osm_prov = osm_row
        
        # Province guard
        if cra_prov and osm_prov and cra_prov.upper() != osm_prov.upper():
            wrong_prov += 1
            continue
        
        # Distance guard: skip if >50km (wrong city match)
        if lat and lon and osm_lat and osm_lon:
            dist = haversine(lat, lon, osm_lat, osm_lon)
            if dist > 50:
                too_far += 1
                continue
            if dist < 0.1:
                skipped += 1
                continue
        
        to_update.append((cid, name, osm_lat, osm_lon, osm_src, osm_prov, lat, lon, cra_prov))
    
    print(f'  {len(to_update)} churches to update, {skipped} already close, {wrong_prov} wrong province, {too_far} too far (>50km)')
    
    if dry_run:
        print('  [DRY RUN] Would update these. Examples:')
        for row in to_update[:10]:
            cid, name, new_lat, new_lon, osm_src, osm_prov, old_lat, old_lon, cra_prov = row
            dist = haversine(old_lat or 0, old_lon or 0, new_lat, new_lon) if old_lat else 999
            print(f'    id={cid} | {name[:40]} | {cra_prov} | {old_lat},{old_lon} -> {new_lat},{new_lon} ({dist:.1f}km) [{osm_src}/{osm_prov}]')
        return len(to_update)
    
    # Apply updates
    print(f'  Applying {len(to_update)} updates...')
    done = 0
    for i in range(0, len(to_update), CHUNK_SIZE):
        chunk = to_update[i:i+CHUNK_SIZE]
        cur.execute('BEGIN')
        for row in chunk:
            cid, name, new_lat, new_lon, osm_src, osm_prov, old_lat, old_lon, cra_prov = row
            cur.execute(
                "UPDATE churches SET latitude=?, longitude=?, last_updated=?, notes=CASE WHEN notes IS NULL THEN ? ELSE notes || '; ' || ? END WHERE id=?",
                (new_lat, new_lon, now_utc(), f'cra_osm_match:{osm_src}', f'cra_osm_match:{osm_src}', cid)
            )
            # Log change
            cur.execute(
                "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?,?,?,?,?,?)",
                (cid, 'latitude', str(old_lat), str(new_lat), 'cra_osm_enrich_phase1', now_utc())
            )
            cur.execute(
                "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?,?,?,?,?,?)",
                (cid, 'longitude', str(old_lon), str(new_lon), 'cra_osm_enrich_phase1', now_utc())
            )
        db.commit()
        done += len(chunk)
        if done % 2000 == 0:
            print(f'    {done}/{len(to_update)}')
    
    # Log provenance
    cur.execute(
        "INSERT INTO provenance_log (source, script_name, started_at, completed_at, records_attempted, records_matched, status, notes) VALUES (?,?,?,?,?,?,?,?)",
        ('cra_osm_enrich_phase1', '_fix_cra_osm_enrich.py', now_utc(), now_utc(), len(to_update), len(to_update), 'completed', f'Exact OSM/overture name match: {len(to_update)} churches updated')
    )
    db.commit()
    print(f'  [DONE] Phase 1: {len(to_update)} churches updated')
    return len(to_update)

# ---- Phase 2: Mapbox geocode for diocese/umbrella entries ----
def phase2_mapbox(db, dry_run=True):
    """Geocode CRA churches using address from CRA CSV via temp table join."""
    cur = db.cursor()
    
    # Create temp table with CRA addresses
    print('\n[Phase 2] Loading CRA addresses into temp table...')
    t0 = time.time()
    
    cur.execute('DROP TABLE IF EXISTS _cra_addrs')
    cur.execute('CREATE TEMP TABLE _cra_addrs (name TEXT PRIMARY KEY, address TEXT)')
    
    count = 0
    with open(CRA_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = (row.get('Legal Name') or '').strip().upper()
            addr1 = (row.get('Address Line 1') or '').strip()
            addr2 = (row.get('Address Line 2') or '').strip()
            city = (row.get('City') or '').strip()
            prov = (row.get('Province') or '').strip()
            postal = (row.get('Postal Code') or '').strip()
            parts = [addr1]
            if addr2: parts.append(addr2)
            parts.append(f'{city}, {prov} {postal}')
            full_addr = ', '.join(p for p in parts if p)
            if name and full_addr:
                cur.execute('INSERT OR IGNORE INTO _cra_addrs VALUES (?,?)', (name, full_addr))
                count += 1
    
    db.commit()
    print(f'  {count} CRA addresses loaded ({time.time()-t0:.1f}s)')
    
    # Join churches with CRA addresses - only get unmatched ones (not already fixed by Phase 1)
    cur.execute("""
        SELECT c.id, c.name, c.latitude, c.longitude, a.address
        FROM churches c
        JOIN _cra_addrs a ON UPPER(c.name) = a.name
        WHERE c.source IN ('cra_2018','cra_2024')
    """)
    
    to_geocode = []
    po_box_skip = 0
    for cid, name, lat, lon, addr in cur.fetchall():
        # Skip PO Box / RR addresses
        addr_upper = addr.upper()
        if 'PO BOX' in addr_upper or 'P.O. BOX' in addr_upper or addr_upper.startswith('RR ') or 'RURAL ROUTE' in addr_upper:
            po_box_skip += 1
            continue
        to_geocode.append((cid, name, addr, lat, lon))
    
    print(f'  {len(to_geocode)} churches to geocode via Mapbox ({po_box_skip} PO Box/RR skipped)')
    
    if dry_run:
        print('  [DRY RUN] Would geocode these. Sample addresses:')
        for cid, name, addr, lat, lon in to_geocode[:15]:
            print(f'    id={cid} | {name[:40]} | {addr[:60]}')
        return len(to_geocode)
    
    # Actually geocode
    print(f'  Geocoding {len(to_geocode)} addresses via Mapbox ({MAPBOX_WORKERS} workers)...')
    geocoded = []
    failed = 0
    done = 0
    
    def geocode_one(item):
        cid, name, addr, old_lat, old_lon = item
        result = mapbox_geocode(addr)
        return (cid, name, result, old_lat, old_lon, addr)
    
    with ThreadPoolExecutor(max_workers=MAPBOX_WORKERS) as pool:
        futures = {pool.submit(geocode_one, item): item for item in to_geocode}
        for future in as_completed(futures):
            cid, name, result, old_lat, old_lon, addr = future.result()
            done += 1
            if result:
                new_lat, new_lon = result
                # Guard: skip if >50km from old coords (probably wrong address)
                if old_lat and old_lon and haversine(old_lat, old_lon, new_lat, new_lon) > 50:
                    failed += 1
                    if done % 500 == 0:
                        print(f'    [{done}/{len(to_geocode)}] {done-failed} ok, {failed} failed (>50km)')
                    continue
                geocoded.append((cid, name, new_lat, new_lon, old_lat, old_lon, addr))
            else:
                failed += 1
            if done % 500 == 0:
                print(f'    [{done}/{len(to_geocode)}] {len(geocoded)} ok, {failed} failed')
    
    print(f'  Geocoded: {len(geocoded)} ok, {failed} failed ({len(geocoded)/len(to_geocode)*100:.1f}% success)')
    
    if not geocoded:
        print('  Nothing to apply.')
        return 0
    
    # Apply updates in chunks
    print(f'  Applying {len(geocoded)} updates...')
    applied = 0
    for i in range(0, len(geocoded), CHUNK_SIZE):
        chunk = geocoded[i:i+CHUNK_SIZE]
        cur.execute('BEGIN')
        for cid, name, new_lat, new_lon, old_lat, old_lon, addr in chunk:
            cur.execute(
                "UPDATE churches SET latitude=?, longitude=?, last_updated=? WHERE id=?",
                (new_lat, new_lon, now_utc(), cid)
            )
            cur.execute(
                "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?,?,?,?,?,?)",
                (cid, 'latitude', str(old_lat), str(new_lat), 'cra_osm_enrich_phase2', now_utc())
            )
            cur.execute(
                "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?,?,?,?,?,?)",
                (cid, 'longitude', str(old_lon), str(new_lon), 'cra_osm_enrich_phase2', now_utc())
            )
        db.commit()
        applied += len(chunk)
        if applied % 2000 == 0:
            print(f'    {applied}/{len(geocoded)}')
    
    # Log provenance
    cur.execute(
        "INSERT INTO provenance_log (source, script_name, started_at, completed_at, records_attempted, records_matched, status, notes) VALUES (?,?,?,?,?,?,?,?)",
        ('cra_osm_enrich_phase2', '_fix_cra_osm_enrich.py', now_utc(), now_utc(), len(geocoded), len(geocoded), 'completed', f'Mapbox geocode: {len(geocoded)} churches updated, {failed} failed')
    )
    db.commit()
    print(f'  [DONE] Phase 2: {len(geocoded)} churches updated, {failed} failed')
    return len(geocoded)

# ---- Main ----
if __name__ == '__main__':
    dry_run = '--write' not in sys.argv
    phase1_only = '--phase1-only' in sys.argv
    phase2_only = '--phase2-only' in sys.argv
    
    mode = 'DRY RUN' if dry_run else 'WRITE MODE'
    print(f'=== CRA OSM Enrichment Fix ({mode}) ===')
    if dry_run:
        print('Add --write to apply changes.')
    print()
    
    db = sqlite3.connect(DB_PATH)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=30000')
    
    try:
        if not phase2_only:
            n1 = phase1_exact_match(db, dry_run=dry_run)
        else:
            n1 = 0
        
        if not phase1_only:
            n2 = phase2_mapbox(db, dry_run=dry_run)
        else:
            n2 = 0
        
        print(f'\n=== SUMMARY ===')
        print(f'Phase 1 (OSM name match): {n1} churches')
        print(f'Phase 2 (Mapbox geocode): {n2} churches')
        print(f'Total: {n1+n2} churches')
        
        if not dry_run:
            # Checkpoint WAL
            db.commit()
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            print('\nWAL checkpointed.')
    finally:
        db.close()

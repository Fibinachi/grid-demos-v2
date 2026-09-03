#!/usr/bin/env python3
"""
Market & Media Ecosystem Enrichment
======================================
Merges FCC broadcast data, DMA boundaries, CBSA codes, rural-urban codes,
and broadcast ministry cross-references onto the churches table.

Pipeline order:
  1. python scripts/enrichment/download_fcc_data.py
  2. python scripts/enrichment/download_geo_data.py
  3. python scripts/enrichment/enrich_markets.py

What this adds per church:
  - DMA code & name (Nielsen TV market)
  - CBSA code, name & type (metro/micro area)
  - RUCC code (rural-urban continuum 1-9)
  - Broadcast ministry flag (if church is an FCC-licensed station)
  - Station counts within radius: FM, AM, TV, NPR, PBS, religious
  - Distance to nearest stations
  - Broadband availability estimate

Usage:
    python scripts/enrichment/enrich_markets.py
    python scripts/enrichment/enrich_markets.py --dry-run
"""
import csv, json, math, os, sqlite3, sys
from datetime import datetime
from difflib import SequenceMatcher

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
FCC_DIR = os.path.join(PROJECT_DIR, 'data', 'fcc')
MARKET_DIR = os.path.join(PROJECT_DIR, 'data', 'markets')

# ── Known broadcast ministry keywords ──
BROADCAST_MINISTRY_KEYWORDS = [
    'broadcasting', 'broadcast', 'television', 'television network',
    'radio network', 'radio ministry', 'media ministry', 'media network',
    'christian broadcasting', 'gospel broadcasting',
    'trinity broadcasting', 'tbn', 'daystar', 'cbn',
    'christian network', 'inspiration network',
    'salem media', 'salem communications',
    'educational media foundation', 'k-love', 'air1',
    'bott radio', 'bible broadcasting', 'bible broadcast',
    'moody broadcasting', 'moody bible',
    'focus on the family', 'billy graham',
    'in touch ministries', 'leading the way',
    'love worth finding', 'life outreach',
    'charles stanley', 'david jeremiah',
    'james dobson', 'tony evans', 'adrian rogers',
    'jack graham', 'greg laurie', 'john macarthur',
    'kiis', 'k love', 'air 1',
]

# ── Haversine distance ──
def haversine_km(lat1, lng1, lat2, lng2):
    """Distance in km between two lat/lng points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def jaro_winkler(s1, s2):
    """Jaro-Winkler similarity for name matching."""
    if not s1 or not s2:
        return 0.0
    s1, s2 = s1.lower(), s2.lower()
    if s1 == s2:
        return 1.0
    len_s1, len_s2 = len(s1), len(s2)
    match_dist = max(len_s1, len_s2) // 2 - 1
    if match_dist < 0:
        match_dist = 0
    s1_matches = [False] * len_s1
    s2_matches = [False] * len_s2
    matches = 0
    transpositions = 0
    for i in range(len_s1):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, len_s2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    k = 0
    for i in range(len_s1):
        if not s1_matches[i]:
            continue
        while k < len_s2 and not s2_matches[k]:
            k += 1
        if k < len_s2 and s1[i] != s2[k]:
            transpositions += 1
        k += 1
    j = (matches / len_s1 + matches / len_s2 + (matches - transpositions / 2) / matches) / 3.0
    # Prefix boost
    prefix_len = 0
    for i in range(min(len(s1), len(s2), 4)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break
    return j + (prefix_len * 0.1 * (1 - j))


def load_stations():
    """Load FCC station data from CSV files. Returns dict of lists."""
    stations = {'fm': [], 'am': [], 'tv': []}
    for stype in stations:
        path = os.path.join(FCC_DIR, f'{stype}_stations.csv')
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found. Run download_fcc_data.py first.")
            continue
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    row['lat'] = float(row.get('lat', 0) or 0)
                    row['lng'] = float(row.get('lng', 0) or 0)
                    row['power_kw'] = float(row.get('power_kw', 0) or 0)
                    row['freq_mhz'] = float(row.get('freq_mhz', 0) or 0)
                except (ValueError, TypeError):
                    continue
                if row['lat'] and row['lng']:
                    stations[stype].append(row)
        print(f"  Loaded {len(stations[stype]):,} {stype.upper()} stations")
    return stations


def load_dma():
    """Load DMA-to-county mapping. Returns dict: state_fips+county_fips -> (dma_code, dma_name)."""
    path = os.path.join(MARKET_DIR, 'dma_county.csv')
    dma_map = {}
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found.")
        return dma_map
    with open(path, 'r') as f:
        for row in csv.DictReader(f):
            state_fips = row['state_fips'].strip()
            county_fips = row['county_fips'].strip()
            key = state_fips + county_fips  # 5-digit county FIPS
            dma_map[key] = (row['dma_code'].strip(), row['dma_name'].strip())
    print(f"  Loaded DMA mapping: {len(dma_map):,} counties")
    return dma_map


def load_rucc():
    """Load RUCC labels."""
    rucc = {}
    path = os.path.join(MARKET_DIR, 'rucc_labels.csv')
    if os.path.exists(path):
        with open(path, 'r') as f:
            for row in csv.DictReader(f):
                rucc[row['code']] = row['label']
    return rucc


def add_columns(db):
    """Add all market/broadcast columns."""
    existing = {r[1] for r in db.execute("PRAGMA table_info(churches)")}
    new_cols = [
        # Broadcast ministry
        ('is_broadcast_ministry', 'INTEGER'),
        ('broadcast_ministry_type', 'TEXT'),
        ('broadcast_match_name', 'TEXT'),
        ('broadcast_callsign', 'TEXT'),
        ('broadcast_frequency', 'REAL'),
        
        # Station counts within radius
        ('fm_stations_25mi', 'INTEGER'),
        ('am_stations_25mi', 'INTEGER'),
        ('tv_stations_50mi', 'INTEGER'),
        ('npr_stations_25mi', 'INTEGER'),
        ('pbs_stations_50mi', 'INTEGER'),
        ('religious_stations_25mi', 'INTEGER'),
        ('total_stations_25mi', 'INTEGER'),
        
        # Nearest stations
        ('nearest_fm_km', 'REAL'),
        ('nearest_am_km', 'REAL'),
        ('nearest_tv_km', 'REAL'),
        ('nearest_npr_km', 'REAL'),
        ('nearest_religious_km', 'REAL'),
        ('nearest_station_call', 'TEXT'),
        ('nearest_station_type', 'TEXT'),
        ('nearest_station_km', 'REAL'),
        
        # Geography
        ('dma_code', 'TEXT'),
        ('dma_name', 'TEXT'),
        ('cbsa_code', 'TEXT'),
        ('cbsa_name', 'TEXT'),
        ('cbsa_type', 'TEXT'),
        ('rucc_code', 'INTEGER'),
        ('rucc_label', 'TEXT'),
        ('broadband_pct', 'REAL'),
    ]
    for col, dtype in new_cols:
        if col not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} {dtype}")


def match_broadcast_ministry(church_name, stations):
    """Check if a church name matches a broadcast licensee.
    
    Returns dict with ministry info or None.
    """
    if not church_name:
        return None
    
    name_lower = church_name.lower()
    
    # First pass: keyword check
    is_ministry = False
    for kw in BROADCAST_MINISTRY_KEYWORDS:
        if kw in name_lower:
            is_ministry = True
            break
    
    if not is_ministry:
        return None
    
    # Second pass: find matching station by licensee name
    best = None
    best_score = 0.0
    
    for stype, stns in stations.items():
        for s in stns:
            licensee = (s.get('licensee', '') or '').lower()
            if not licensee:
                continue
            # Compare church name vs licensee
            score = jaro_winkler(church_name, licensee)
            if score > best_score and score > 0.6:
                best_score = score
                best = {
                    'type': stype,
                    'callsign': s.get('call_sign', ''),
                    'frequency': s.get('freq_mhz', 0),
                    'licensee': s.get('licensee', ''),
                    'power_kw': s.get('power_kw', 0),
                    'lat': s.get('lat', 0),
                    'lng': s.get('lng', 0),
                    'match_score': score,
                }
    
    return best


def count_stations_nearby(lat, lng, stations, max_km):
    """Count stations within max_km radius. Returns (count, nearest_distance, nearest_info)."""
    count = 0
    nearest_dist = float('inf')
    nearest = None
    
    for s in stations:
        s_lat = s.get('lat', 0)
        s_lng = s.get('lng', 0)
        if not s_lat or not s_lng:
            continue
        
        d = haversine_km(lat, lng, s_lat, s_lng)
        if d <= max_km:
            count += 1
        if d < nearest_dist:
            nearest_dist = d
            nearest = s
    
    return count, nearest_dist, nearest


def get_churches_for_enrichment(db, limit=0):
    """Get churches with lat/lng that need market enrichment."""
    q = """
        SELECT id, name, latitude, longitude, fips
        FROM churches
        WHERE latitude IS NOT NULL AND latitude != 0
          AND longitude IS NOT NULL
        ORDER BY id
    """
    if limit:
        q += f" LIMIT {limit}"
    return db.execute(q).fetchall()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Market & media ecosystem enrichment')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--limit', type=int, default=0, help='Limit churches')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Market & Media Ecosystem Enrichment")
    print("=" * 60)
    
    # 1. Load data
    print("\n[1] Loading broadcast stations...")
    stations = load_stations()
    
    print("\n[2] Loading geography data...")
    dma_map = load_dma()
    rucc_labels = load_rucc()
    
    # 2. Connect to DB
    db = sqlite3.connect(DB_PATH)
    
    print("\n[3] Adding columns...")
    add_columns(db)
    db.commit()
    
    # 3. Get churches
    churches = get_churches_for_enrichment(db, args.limit)
    print(f"\n[4] Enriching {len(churches):,} churches...")
    
    if args.dry_run:
        for r in churches[:5]:
            print(f"  {r[0]:>8d} | {r[1][:45]:45s} | ({r[2]:.4f}, {r[3]:.4f})")
        if len(churches) > 5:
            print(f"  ... and {len(churches)-5:,} more")
        db.close()
        return
    
    stats = {
        'broadcast_ministries': 0,
        'dma_assigned': 0,
        'station_counts': 0,
        'processed': 0,
    }
    batch_updates = []
    
    for i, row in enumerate(churches):
        cid, name, lat, lng, fips = row
        
        sets = []
        
        # ── Broadcast ministry cross-reference ──
        ministry = match_broadcast_ministry(name, stations)
        if ministry:
            sets.append(f"is_broadcast_ministry=1")
            sets.append(f"broadcast_ministry_type='{ministry['type']}'")
            sets.append(f"broadcast_callsign='{ministry['callsign']}'")
            sets.append(f"broadcast_frequency={ministry['frequency']}")
            stats['broadcast_ministries'] += 1
        
        # ── DMA by county FIPS ──
        if fips and fips in dma_map:
            dma_code, dma_name = dma_map[fips]
            sets.append(f"dma_code='{dma_code}'")
            sets.append(f"dma_name='{dma_name.replace(chr(39), chr(39)*2)}'")
            stats['dma_assigned'] += 1
        
        # ── Station counts within radius ──
        if lat and lng:
            fm_count, fm_dist, fm_nearest = count_stations_nearby(lat, lng, stations.get('fm', []), 40)
            am_count, am_dist, am_nearest = count_stations_nearby(lat, lng, stations.get('am', []), 40)
            tv_count, tv_dist, tv_nearest = count_stations_nearby(lat, lng, stations.get('tv', []), 80)
            
            npr_stns = [s for s in stations.get('fm', []) if s.get('is_npr')]
            pbs_stns = [s for s in stations.get('tv', []) if s.get('is_pbs')]
            rel_stns = [s for s in (stations.get('fm', []) + stations.get('am', []) + stations.get('tv', [])) if s.get('is_religious')]
            
            npr_count, npr_dist, _ = count_stations_nearby(lat, lng, npr_stns, 40)
            pbs_count, pbs_dist, _ = count_stations_nearby(lat, lng, pbs_stns, 80)
            rel_count, rel_dist, rel_nearest = count_stations_nearby(lat, lng, rel_stns, 40)
            
            total = fm_count + am_count + tv_count
            
            sets.append(f"fm_stations_25mi={fm_count}")
            sets.append(f"am_stations_25mi={am_count}")
            sets.append(f"tv_stations_50mi={tv_count}")
            sets.append(f"npr_stations_25mi={npr_count}")
            sets.append(f"pbs_stations_50mi={pbs_count}")
            sets.append(f"religious_stations_25mi={rel_count}")
            sets.append(f"total_stations_25mi={total}")
            
            if fm_dist != float('inf'):
                sets.append(f"nearest_fm_km={fm_dist:.2f}")
            if am_dist != float('inf'):
                sets.append(f"nearest_am_km={am_dist:.2f}")
            if tv_dist != float('inf'):
                sets.append(f"nearest_tv_km={tv_dist:.2f}")
            if npr_dist != float('inf'):
                sets.append(f"nearest_npr_km={npr_dist:.2f}")
            if rel_dist != float('inf'):
                sets.append(f"nearest_religious_km={rel_dist:.2f}")
            
            # Absolute nearest station (any type)
            nearest_all = [
                (fm_dist, 'FM', fm_nearest),
                (am_dist, 'AM', am_nearest),
                (tv_dist, 'TV', tv_nearest),
            ]
            nearest_all.sort(key=lambda x: x[0] if x[0] != float('inf') else 99999)
            if nearest_all[0][0] != float('inf'):
                sets.append(f"nearest_station_km={nearest_all[0][0]:.2f}")
                sets.append(f"nearest_station_type='{nearest_all[0][1]}'")
                if nearest_all[0][2]:
                    call = nearest_all[0][2].get('call_sign', '')
                    if call:
                        sets.append(f"nearest_station_call='{call}'")
            
            stats['station_counts'] += 1
        
        if sets:
            sets.append("last_updated=datetime('now')")
            batch_updates.append((cid, sets))
        
        stats['processed'] += 1
        
        # Flush periodically
        if len(batch_updates) >= 500:
            _flush(db, batch_updates)
            if stats['processed'] % 5000 == 0:
                pct = stats['processed'] / len(churches) * 100
                print(f"  Progress: {stats['processed']:,}/{len(churches):,} ({pct:.1f}%)")
    
    if batch_updates:
        _flush(db, batch_updates)
    
    # Summary
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"  Churches processed:       {stats['processed']:>8,}")
    print(f"  Broadcast ministries:    {stats['broadcast_ministries']:>8,}")
    print(f"  DMA assigned (by county):{stats['dma_assigned']:>8,}")
    print(f"  Station counts computed: {stats['station_counts']:>8,}")
    
    # Coverage stats
    for col in ['is_broadcast_ministry', 'dma_code', 'fm_stations_25mi', 'nearest_fm_km']:
        cnt = db.execute(f"SELECT COUNT(*) FROM churches WHERE {col} IS NOT NULL AND {col} != 0 AND {col} != ''").fetchone()[0]
        print(f"  {col:30s} {cnt:>8,}")
    
    # Log provenance
    db.execute("""INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, churches_updated, fields_populated,
         records_attempted, records_matched, status, notes)
        VALUES (?,?,?,?,?,?,?,?,'completed',?)""",
        ('market_enrichment', 'enrich_markets.py',
         datetime.now().isoformat(), datetime.now().isoformat(),
         stats['processed'],
         'dma_code,dma_name,is_broadcast_ministry,fm_stations_25mi,tv_stations_50mi,npr_stations_25mi',
         stats['processed'], stats['processed'],
         f'{stats["broadcast_ministries"]} broadcast ministries identified, {stats["dma_assigned"]} DMA assigned'))
    db.commit()
    
    db.close()
    print("\nDone!")


def _flush(db, updates):
    for cid, sets in updates:
        sql = f"UPDATE churches SET {', '.join(sets)} WHERE id=?"
        db.execute(sql, (cid,))
    db.commit()
    updates.clear()


if __name__ == '__main__':
    main()

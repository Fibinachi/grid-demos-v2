"""
Step 3 only: Spatial proximity matching.
fcc_facilities table + indexes already exist.
"""
import sqlite3, math, json

DB = 'E:/grid/churches.db'

# Haversine distance in km
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Radius thresholds by service type (km)
SVC_RADIUS = {
    'FL': 1.0, 'FM': 3.0, 'AM': 5.0, 'FX': 1.5, 'FB': 3.0,
    'FS': 3.0, 'FA': 3.0, 'LPA': 1.0, 'LPD': 1.0, 'LPT': 1.0, 'LPX': 1.0,
}

def main():
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=OFF')
    db.execute('PRAGMA temp_store=MEMORY')
    
    # Clear existing matches
    db.execute('DELETE FROM church_fcc')
    db.commit()
    
    # Load all facilities
    facilities = db.execute(
        'SELECT facility_id, callsign, service_code, lat, lon FROM fcc_facilities'
    ).fetchall()
    print(f"Facilities to match: {len(facilities):,}")
    
    total_matched = 0
    total_fac_uniq = 0
    batch = []
    
    for idx, (fid, callsign, svc, flat, flon) in enumerate(facilities):
        radius = SVC_RADIUS.get(svc, 2.0)
        dlat = radius / 111.0
        dlon = radius / (111.0 * math.cos(math.radians(flat))) if abs(flat) < 80 else radius / 111.0
        
        lat_min = flat - dlat
        lat_max = flat + dlat
        lon_min = flon - dlon
        lon_max = flon + dlon
        
        rows = db.execute('''
            SELECT id, latitude, longitude
            FROM churches
            WHERE latitude BETWEEN ? AND ?
              AND longitude BETWEEN ? AND ?
              AND latitude IS NOT NULL AND latitude != 0
              AND longitude IS NOT NULL AND longitude != 0
            LIMIT 20
        ''', (lat_min, lat_max, lon_min, lon_max)).fetchall()
        
        for ch_id, ch_lat, ch_lon in rows:
            if ch_id is None:
                continue
            dist = haversine_km(flat, flon, ch_lat, ch_lon)
            if dist <= radius:
                batch.append((ch_id, str(fid), callsign, svc, f'lms_proximity_{dist:.3f}km'))
        
        # Commit every 2000 facilities
        if (idx + 1) % 2000 == 0:
            if batch:
                try:
                    db.executemany(
                        'INSERT INTO church_fcc (church_id, facility_id, call_sign, service_type, source) VALUES (?,?,?,?,?)',
                        batch
                    )
                    db.commit()
                    fac_in_batch = len(set(b[1] for b in batch))
                    total_matched += len(batch)
                    total_fac_uniq += fac_in_batch
                    batch = []
                except Exception as e:
                    print(f"  ERROR at facility {idx+1}: {e}")
                    db.rollback()
                    # Retry with smaller batch
                    smaller = batch[:500]
                    db.executemany(
                        'INSERT INTO church_fcc (church_id, facility_id, call_sign, service_type, source) VALUES (?,?,?,?,?)',
                        smaller
                    )
                    db.commit()
                    total_matched += len(smaller)
                    total_fac_uniq += len(set(b[1] for b in smaller))
                    batch = batch[500:]
            print(f"  Processed {idx+1:,}/{len(facilities):,}, {total_matched:,} matches so far...")
    
    # Final flush
    if batch:
        try:
            db.executemany(
                'INSERT INTO church_fcc (church_id, facility_id, call_sign, service_type, source) VALUES (?,?,?,?,?)',
                batch
            )
            db.commit()
            total_matched += len(batch)
            total_fac_uniq += len(set(b[1] for b in batch))
        except Exception as e:
            print(f"  ERROR on final flush: {e}")
            db.rollback()
            # Try smaller batches
            for i in range(0, len(batch), 500):
                sub = batch[i:i+500]
                db.executemany(
                    'INSERT INTO church_fcc (church_id, facility_id, call_sign, service_type, source) VALUES (?,?,?,?,?)',
                    sub
                )
                db.commit()
                total_matched += len(sub)
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"  Total matches: {total_matched:,}")
    cur = db.execute('SELECT service_type, COUNT(*) FROM church_fcc GROUP BY service_type ORDER BY COUNT(*) DESC')
    for svc, cnt in cur:
        print(f"    {svc:6s}: {cnt:,}")
    cur = db.execute('SELECT COUNT(DISTINCT church_id) FROM church_fcc')
    print(f"  Unique churches matched: {cur.fetchone()[0]:,}")
    cur = db.execute('SELECT COUNT(DISTINCT facility_id) FROM church_fcc')
    print(f"  Unique facilities linked: {cur.fetchone()[0]:,}")
    
    db.close()
    print("\nDone!")

if __name__ == '__main__':
    main()

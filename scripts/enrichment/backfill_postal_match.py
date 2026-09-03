"""
Phase 2+3: Match churches without address to nearest postal code and backfill.

For each church with GPS in a country with postal data:
1. Find nearest postal code point within 25km
2. Backfill: address = best available, city = place_name, state = admin1_name
3. Track match distance for quality assessment
"""
import sqlite3, math, time
from collections import defaultdict

DB = r'e:\grid\churches.db'

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def build_postal_spatial_index(db, country):
    """Load all postal codes for a country into bucketed spatial index."""
    rows = db.execute("""
        SELECT id, place_name, admin1_name, admin2_name, postal_code, latitude, longitude
        FROM geonames_postal
        WHERE country_code = ?
        AND latitude != 0 AND longitude != 0
    """, (country,)).fetchall()
    
    if not rows:
        return None, 0
    
    buckets = defaultdict(list)
    for pc_id, place, admin1, admin2, postal, lat, lon in rows:
        bucket = (round(lat, 1), round(lon, 1))
        buckets[bucket].append((pc_id, place, admin1, admin2, postal, lat, lon))
    
    return buckets, len(rows)

def backfill_country(db, country):
    """Backfill churches in one country using postal code spatial matching."""
    
    # Count churches needing backfill
    needs_addr = db.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE country=? AND latitude IS NOT NULL AND latitude != 0
        AND (address IS NULL OR address = '' OR city IS NULL OR city = '' OR state IS NULL OR state = '')
    """, (country,)).fetchone()[0]
    
    if needs_addr == 0:
        print(f"  {country}: all churches have address/city/state — skipping")
        return 0, 0
    
    # Build spatial index
    buckets, total_pc = build_postal_spatial_index(db, country)
    if buckets is None:
        print(f"  {country}: no postal codes with coordinates — skipping")
        return 0, 0
    
    # Get churches needing help
    churches = db.execute("""
        SELECT id, latitude, longitude, address, city, state
        FROM churches 
        WHERE country=? AND latitude IS NOT NULL AND latitude != 0
        AND (address IS NULL OR address = '' OR city IS NULL OR city = '' OR state IS NULL OR state = '')
    """, (country,)).fetchall()
    
    if not churches:
        return 0, 0
    
    MAX_DIST_KM = 25  # Maximum distance to consider a postal code match valid
    
    updates_addr = []
    updates_city = []  # city-only
    updates_state = []  # state-only
    matched = 0
    too_far = 0
    
    for ch_id, clat, clon, addr, city, state in churches:
        # Find nearest postal code
        best_dist = float('inf')
        best = None
        
        cbucket = (round(clat, 1), round(clon, 1))
        
        for dlat in (-0.1, 0, 0.1):
            for dlon in (-0.1, 0, 0.1):
                nb = (cbucket[0] + dlat, cbucket[1] + dlon)
                for pc_id, place, admin1, admin2, postal, plat, plon in buckets.get(nb, []):
                    dist = haversine_km(clat, clon, plat, plon)
                    if dist < best_dist:
                        best_dist = dist
                        best = (pc_id, place, admin1, admin2, postal, plat, plon)
        
        if best is None or best_dist > MAX_DIST_KM:
            too_far += 1
            continue
        
        pc_id, place, admin1, admin2, postal, plat, plon = best
        
        # Build address string if missing
        # For postal code data, the address is typically: place_name, postal_code, admin2, admin1
        need_addr = not addr or addr == ''
        need_city = not city or city == ''
        need_state = not state or state == ''
        
        if need_addr:
            # Build an address from postal code components
            addr_parts = []
            if place:
                addr_parts.append(place)
            if postal:
                addr_parts.append(postal)
            if admin2 and admin2 != place:
                addr_parts.append(admin2)
            if admin1:
                addr_parts.append(admin1)
            
            new_addr = ', '.join(addr_parts) if addr_parts else place or postal
            updates_addr.append((new_addr, ch_id))
        
        if need_city and place:
            updates_city.append((place, ch_id))
        
        if need_state and admin1:
            updates_state.append((admin1, ch_id))
        
        matched += 1
    
    # Apply updates in batches
    CHUNK = 500
    addr_updated = 0
    city_updated = 0
    state_updated = 0
    
    for i in range(0, len(updates_addr), CHUNK):
        batch = updates_addr[i:i+CHUNK]
        for new_addr, ch_id in batch:
            c = db.execute("UPDATE churches SET address=? WHERE id=? AND (address IS NULL OR address='')", (new_addr, ch_id))
            addr_updated += c.rowcount
    
    for i in range(0, len(updates_city), CHUNK):
        batch = updates_city[i:i+CHUNK]
        for new_city, ch_id in batch:
            c = db.execute("UPDATE churches SET city=? WHERE id=? AND (city IS NULL OR city='')", (new_city, ch_id))
            city_updated += c.rowcount
    
    for i in range(0, len(updates_state), CHUNK):
        batch = updates_state[i:i+CHUNK]
        for new_state, ch_id in batch:
            c = db.execute("UPDATE churches SET state=? WHERE id=? AND (state IS NULL OR state='')", (new_state, ch_id))
            state_updated += c.rowcount
    
    db.commit()
    
    if addr_updated or city_updated or state_updated:
        print(f"  {country}: {matched:,} matched ({too_far:,} too far >25km) | "
              f"addr +{addr_updated:,} city +{city_updated:,} state +{state_updated:,} "
              f"({total_pc:,} postal codes)")
    else:
        print(f"  {country}: {matched:,} potential matches, {too_far:,} too far — nothing to update")
    
    return matched, addr_updated + city_updated + state_updated

def main():
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    
    # Get countries with postal data
    countries = [r[0] for r in db.execute("""
        SELECT DISTINCT country_code FROM geonames_postal 
        WHERE country_code != 'US' 
        ORDER BY country_code
    """).fetchall()]
    
    print(f"Processing {len(countries)} countries with postal code data...\n")
    
    total_matched = 0
    total_updated = 0
    
    for country in countries:
        matched, updated = backfill_country(db, country)
        total_matched += matched
        total_updated += updated
    
    print(f"\n{'='*60}")
    print(f"TOTAL: {total_matched:,} churches matched, {total_updated:,} fields updated")
    
    # Final stats
    print(f"\nPost-backfill address coverage (countries with postal data, non-US):")
    for country in sorted(countries):
        total = db.execute("SELECT COUNT(*) FROM churches WHERE country=?", (country,)).fetchone()[0]
        addr = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND address IS NOT NULL AND address != ''", (country,)).fetchone()[0]
        city = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND city IS NOT NULL AND city != ''", (country,)).fetchone()[0]
        state = db.execute("SELECT COUNT(*) FROM churches WHERE country=? AND state IS NOT NULL AND state != ''", (country,)).fetchone()[0]
        if total >= 1000:
            print(f"  {country}: addr {100*addr/total:.0f}% ({addr:,}) | city {100*city/total:.0f}% | state {100*state/total:.0f}%")
    
    db.close()

if __name__ == '__main__':
    main()

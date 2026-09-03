#!/usr/bin/env python3
"""
Geocode LOC phone directory churches against GRID.
Strategy: forward geocode addresses using Census batch API (US only),
then match to existing GRID churches by proximity.
"""
import json, sqlite3, requests, time, sys
from pathlib import Path
from urllib.parse import quote

IN_FILE = Path("E:/grid/data/loc_phone_dirs/results/loc_churches_matched_20260709_094416.json")
DB_PATH = Path("E:/grid/churches.db")
BATCH_SIZE = 100
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

def geocode_census(addresses):
    """Batch geocode using Census API. Returns list of (lat, lon, match_type)."""
    # Format: unique_id, street, city, state, zip
    payload = []
    for i, addr in enumerate(addresses):
        payload.append(f'{i},"{addr["address"]}","{addr["city"]}","{addr["state"]}",""')
    
    body = '\n'.join(payload)
    
    resp = requests.post(
        CENSUS_URL,
        data={'benchmark': 'Public_AR_Current', 'vintage': 'Current_Current'},
        files={'addressFile': ('addresses.csv', body.encode('utf-8'))},
        timeout=60
    )
    
    results = []
    for line in resp.text.strip().split('\n'):
        parts = line.strip().split(',')
        if len(parts) >= 5:
            try:
                iid = int(parts[0].strip('"'))
                addr = parts[1].strip('"')
                match = parts[2].strip('"')
                lat = float(parts[4].strip('"')) if parts[4].strip('"') else None
                lon = float(parts[5].strip('"')) if parts[5].strip('"') else None
                results.append((iid, lat, lon, match))
            except:
                results.append((None, None, None, 'parse_error'))
    
    return results


def proximity_match(lat, lon, max_km=0.5):
    """Find GRID churches within max_km of given coordinates."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    # Find nearest church using simple bounding box then haversine
    # Bounding box: ~0.005 degrees per km
    delta = max_km * 0.01
    rows = conn.execute("""
        SELECT id, name, address, city, state, latitude, longitude,
               (6371 * acos(cos(radians(?)) * cos(radians(latitude)) * 
                cos(radians(longitude) - radians(?)) + sin(radians(?)) * 
                sin(radians(latitude)))) AS distance_km
        FROM churches
        WHERE latitude BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
          AND latitude != 0
        ORDER BY distance_km
        LIMIT 3
    """, (lat, lon, lat, lat - delta, lat + delta, lon - delta, lon + delta))
    
    matches = [dict(r) for r in rows.fetchall()]
    conn.close()
    return matches


def main():
    data = json.loads(IN_FILE.read_text(encoding='utf-8'))
    
    # Filter geocodable US entries
    geocodable = [c for c in data if c.get('address') and c.get('city') and c.get('state')
                  and c.get('country', 'US') in ('US', 'United States', '')]
    
    print(f"Geocodable: {len(geocodable)} out of {len(data)}")
    
    geocoded = 0
    proximity_matched = 0
    
    for batch_start in range(0, len(geocodable), BATCH_SIZE):
        batch = geocodable[batch_start:batch_start + BATCH_SIZE]
        
        print(f"  Batch {batch_start//BATCH_SIZE + 1}/{(len(geocodable)-1)//BATCH_SIZE + 1} "
              f"({len(batch)} addresses)...", end=' ', flush=True)
        
        try:
            results = geocode_census(batch)
        except Exception as e:
            print(f"API error: {e}")
            time.sleep(2)
            continue
        
        success = 0
        for iid, lat, lon, match_type in results:
            if iid is not None and lat and lon:
                geocodable[batch_start + iid]['_geo_lat'] = lat
                geocodable[batch_start + iid]['_geo_lon'] = lon
                geocodable[batch_start + iid]['_geo_match'] = match_type
                success += 1
                geocoded += 1
                
                # Proximity match to GRID
                nearby = proximity_match(lat, lon, max_km=0.5)
                if nearby and nearby[0]['distance_km'] <= 0.3:
                    best = nearby[0]
                    geocodable[batch_start + iid]['_grid_prox_match_id'] = best['id']
                    geocodable[batch_start + iid]['_grid_prox_match_name'] = best['name']
                    geocodable[batch_start + iid]['_grid_prox_match_dist'] = round(best['distance_km'], 3)
                    geocodable[batch_start + iid]['_grid_prox_match_city'] = best['city']
                    proximity_matched += 1
        
        print(f"{success} geocoded")
        time.sleep(0.5)  # Rate limit
    
    # Save results
    out_file = Path("E:/grid/data/loc_phone_dirs/results/loc_churches_geocoded.json")
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    
    print(f"\n✅ Geocoded: {geocoded}/{len(geocodable)} ({100*geocoded/max(1,len(geocodable)):.0f}%)")
    print(f"📍 Proximity-matched to GRID (≤300m): {proximity_matched}")
    print(f"📁 Saved: {out_file}")


if __name__ == '__main__':
    main()

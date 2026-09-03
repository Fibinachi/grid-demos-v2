#!/usr/bin/env python3
"""
Mapbox Geocoding — Direct DB writes
====================================
Geocodes remaining ~28K churches via Mapbox API, writes lat/lng directly to DB.

Usage:
    python scripts/enrichment/mapbox_db.py --limit 1000
    python scripts/enrichment/mapbox_db.py --full
"""
import csv, json, os, sqlite3, sys, time, urllib.request, urllib.parse

DB = r'E:\grid\churches.db'
KEY = os.environ.get('MAPBOX_API_KEY', '')
if not KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
URL = 'https://api.mapbox.com/geocoding/v5/mapbox.places/{q}.json?access_token={k}&limit=1&country=US'

def geocode(query):
    try:
        q = urllib.parse.quote(query[:200])
        req = urllib.request.Request(URL.format(q=q, k=KEY),
            headers={"User-Agent":"GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
        features = data.get('features',[])
        if features:
            c = features[0].get('center',[])
            if len(c)==2:
                return c[1], c[0], features[0].get('relevance',0.5)
    except:
        pass
    return None, None, None

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    
    db = sqlite3.connect(DB)
    
    # Get churches needing geocoding, prioritized
    rows = db.execute("""
        SELECT id, name, address, city, state, zip,
               CASE WHEN website!='' AND phone!='' THEN 1
                    WHEN website!='' THEN 2
                    WHEN phone!='' THEN 3
                    ELSE 4 END as priority
        FROM churches 
        WHERE latitude IS NULL
        ORDER BY priority, id
    """).fetchall()
    
    total = len(rows)
    if args.full or args.limit==0:
        args.limit = total
    
    todo = rows[:args.limit]
    print(f"Geocoding {len(todo):,} / {total:,} churches via Mapbox (free tier)...")
    
    done = found = 0
    start = time.time()
    
    for cid, name, addr, city, state, zipc, pri in todo:
        # Build query
        parts = [p for p in [addr, city, state, zipc] if p]
        query = ", ".join(parts) if parts else name[:100]
        
        lat, lng, conf = geocode(query)
        time.sleep(0.05)  # 20 req/sec
        
        done += 1
        if lat:
            db.execute("UPDATE churches SET latitude=?, longitude=?, geocode_source='mapbox', geocode_confidence=?, geocode_last_verified=datetime('now') WHERE id=?", (lat, lng, conf, cid))
            found += 1
        
        if done % 500 == 0:
            db.commit()
            elapsed = time.time()-start
            print(f"  {done:,}/{len(todo):,} ({done/elapsed:.0f}/s) — found {found:,}")
    
    db.commit()
    elapsed = time.time()-start
    print(f"\nDone! {done:,} in {elapsed:.0f}s, found {found:,}")
    
    has = db.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL").fetchone()[0]
    print(f"Total with lat/lng: {has:,} / 263,712")
    db.close()

if __name__ == '__main__':
    main()

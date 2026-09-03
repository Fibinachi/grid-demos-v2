"""
Reverse geocode US entries: robust sequential. Gets county_fips, tract_fips,
block_fips, city, state from Census API. ~1 req/sec, runs until done.
Logs provenance on completion.
"""
import sqlite3, requests, time, sys
from datetime import datetime, timezone

DB = 'churches.db'
URL = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

c.execute("""SELECT c.rowid, c.latitude, c.longitude FROM churches c 
LEFT JOIN church_enrichment ce ON c.rowid = ce.church_id
WHERE c.country='US' AND c.latitude IS NOT NULL AND (ce.county_fips IS NULL OR ce.county_fips = '')""")
rows = c.fetchall()
total = len(rows)
print(f"US entries needing county FIPS: {total:,}")
if total == 0: print("Done!"); db.close(); sys.exit(0)

session = requests.Session()
session.headers.update({'User-Agent': 'GRID/1.0 (academic research)'})
updated = failed = 0; start = time.time()

for i, (rowid, lat, lon) in enumerate(rows):
    try:
        r = session.get(URL, params={'x':str(lon),'y':str(lat),'benchmark':'4','vintage':'4','format':'json'}, timeout=8)
        if r.status_code != 200: failed += 1; continue
        g = r.json().get('result',{}).get('geographies',{})
        if not g: failed += 1; continue
        
        ct = g.get('Counties',[])
        cf = f"{ct[0]['STATE']}{ct[0]['COUNTY']}" if ct else None
        cn = ct[0].get('NAME','') if ct else None
        tr = g.get('Census Tracts',[])
        tf = f"{tr[0]['STATE']}{tr[0]['COUNTY']}{tr[0]['TRACT']}" if tr else None
        pl = g.get('Incorporated Places',[]) or g.get('Census Places',[])
        city = pl[0].get('NAME','') if pl else None
        st = g.get('States',[]); state = st[0].get('STUSAB','') if st else None
        
        c.execute("INSERT OR IGNORE INTO church_enrichment (church_id) VALUES (?)", (rowid,))
        c.execute("UPDATE church_enrichment SET county_fips=?,county_name=?,tract_fips=? WHERE church_id=?", (cf, cn, tf, rowid))
        if city or state:
            c.execute("UPDATE churches SET city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END, state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END WHERE rowid=?", (city, state, rowid))
        updated += 1
    except: failed += 1
    
    if (i+1) % 500 == 0:
        db.commit()
        e = time.time()-start; rate = (i+1)/e
        print(f'\r  {i+1:,}/{total:,} ({(i+1)/total*100:.1f}%) rate={rate:.0f}/s upd={updated:,} ETA={(total-i-1)/rate/3600:.1f}h', end='', flush=True)

db.commit()
e = time.time()-start
print(f'\r  {total:,}/{total:,} (100%) upd={updated:,} failed={failed:,} {e/3600:.1f}h')

c.execute("SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND ce.county_fips IS NOT NULL AND ce.county_fips!=''")
print(f"US with county_fips: {c.fetchone()[0]:,}")

c.execute("INSERT INTO provenance_log (source,script_name,started_at,completed_at,churches_updated,fields_populated,status,notes) VALUES (?,?,?,?,?,?,?,?)",
    ('census_reverse_geocoder','reverse_geocode_us_census.py',NOW,datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
     updated,'county_fips,county_name,tract_fips,city,state','completed',
     f'Census API sequential. {updated:,} enriched, {failed:,} failed. {e/3600:.1f}h.'))
db.commit(); db.close()
print("Provenance logged.")

"""
Live-updating Catholic geocoder: county/tract FIPS + diocese expansion.
Shows every 10 updates with %, failure rate, rate, ETA.
"""
import sqlite3, requests, time
from datetime import datetime, timezone

DB = 'churches.db'
URL = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
CATH = "(LOWER(COALESCE(c.faith_tradition,'')) LIKE '%cath%' OR LOWER(COALESCE(c.faith,'')) LIKE '%cath%' OR LOWER(COALESCE(c.denomination,'')) LIKE '%cath%')"

db = sqlite3.connect(DB); db.execute("PRAGMA journal_mode=WAL"); c = db.cursor()

c.execute(f"SELECT c.rowid,c.latitude,c.longitude FROM churches c LEFT JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND c.latitude IS NOT NULL AND {CATH} AND (ce.county_fips IS NULL OR ce.county_fips='')")
rows = c.fetchall(); total = len(rows)
print(f"Catholic needing county/tract: {total:,}")
if total==0: print("Done!"); db.close(); exit()

s = requests.Session(); s.headers.update({'User-Agent':'GRID/1.0'})
ok = fail = 0; t0 = time.time()
failures = []  # track what failed

for i, (rid, lat, lon) in enumerate(rows):
    err = None
    try:
        r = s.get(URL, params={'x':str(lon),'y':str(lat),'benchmark':'4','vintage':'4','format':'json'}, timeout=8)
        if r.status_code!=200: err=f'HTTP {r.status_code}'; fail+=1
        else:
            g = r.json().get('result',{}).get('geographies',{})
            if not g: err='no geographies'; fail+=1
            else:
                ct=g.get('Counties',[]); cf=f"{ct[0]['STATE']}{ct[0]['COUNTY']}" if ct else None; cn=ct[0].get('NAME','') if ct else None
                tr=g.get('Census Tracts',[]); tf=f"{tr[0]['STATE']}{tr[0]['COUNTY']}{tr[0]['TRACT']}" if tr else None
                pl=g.get('Incorporated Places',[]) or g.get('Census Places',[]); city=pl[0].get('NAME','') if pl else None
                st=g.get('States',[]); state=st[0].get('STUSAB','') if st else None
                c.execute("INSERT OR IGNORE INTO church_enrichment (church_id) VALUES (?)",(rid,))
                c.execute("UPDATE church_enrichment SET county_fips=?,county_name=?,tract_fips=? WHERE church_id=?",(cf,cn,tf,rid))
                if city or state: c.execute("UPDATE churches SET city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END, state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END WHERE rowid=?",(city,state,rid))
                ok+=1
    except Exception as e: err=str(e)[:80]; fail+=1
    
    if err: 
        failures.append((rid, lat, lon, err))
        print(f'  ⚠ rowid={rid} ({lat:.4f},{lon:.4f}): {err}', flush=True)
    
    if (i+1)%10==0:
        db.commit(); pct=(i+1)/total*100; rate=(i+1)/(time.time()-t0)
        fp=fail/(ok+fail)*100 if ok+fail else 0
        print(f'\r  {i+1:>6,}/{total:,} ({pct:5.1f}%) ok={ok:,} fail={fail} ({fp:.1f}%) {rate:.0f}/s ETA={(total-i-1)/rate/3600:.1f}h', end='', flush=True)

db.commit(); print()

# Expand county_diocese_map
print("\nExpanding county→diocese map...")
c.execute(f"INSERT OR IGNORE INTO county_diocese_map (county_fips,diocese,source,confidence) SELECT DISTINCT ce.county_fips,ce.diocese,'census',3 FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND ce.diocese IS NOT NULL AND ce.diocese!='' AND ce.county_fips IS NOT NULL AND ce.county_fips!='' AND {CATH}")
new=c.rowcount
c.execute("SELECT COUNT(*) FROM county_diocese_map"); print(f"  Map: {c.fetchone()[0]} counties (+{new})")

# Sync
c.execute("UPDATE church_enrichment SET diocese=(SELECT cdm.diocese FROM county_diocese_map cdm WHERE cdm.county_fips=church_enrichment.county_fips) WHERE county_fips IN (SELECT county_fips FROM county_diocese_map) AND (diocese IS NULL OR diocese='')")
print(f"  Synced: {c.rowcount:,}")

# Stats
c.execute(f"SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND {CATH} AND ce.diocese IS NOT NULL AND ce.diocese!=''")
d=c.fetchone()[0]
c.execute(f"SELECT COUNT(*) FROM churches WHERE country='US' AND {CATH}")
t=c.fetchone()[0]
print(f"\nUS Catholic diocese: {d:,}/{t:,} ({d/t*100:.0f}%)")
c.execute("SELECT COUNT(*) FROM churches c JOIN church_enrichment ce ON c.rowid=ce.church_id WHERE c.country='US' AND ce.tract_fips IS NOT NULL")
print(f"US tract_fips: {c.fetchone()[0]:,}")

c.execute("INSERT INTO provenance_log (source,script_name,started_at,completed_at,churches_updated,fields_populated,status,notes) VALUES (?,?,?,?,?,?,?,?)",
    ('census_catholic_tracts','geocode_catholic_tracts.py',NOW,NOW,ok,'county_fips,tract_fips,diocese','completed',f'{ok:,} enriched. Map expanded to {c.execute("SELECT COUNT(*) FROM county_diocese_map").fetchone()[0]} counties.'))
db.commit(); db.close()
print("Provenance logged.")

"""Dead-simple elevation pipeline — inline loop pattern proven to work."""
import sqlite3, rasterio, time, math
from rasterio.windows import Window
from datetime import datetime
import warnings; warnings.filterwarnings("ignore")

db = sqlite3.connect('churches.db')
db.execute("PRAGMA journal_mode=WAL")

COG = 'https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com'

def tk(lat,lon):
    ns='N'if lat>=0 else'S';ew='E'if lon>=0 else'W'
    return(ns,abs(int(math.floor(lat))),ew,abs(int(math.floor(lon))))

def url(tile):
    ns,la,ew,lo=tile
    n=f'Copernicus_DSM_COG_10_{ns}{la:02d}_00_{ew}{lo:03d}_00_DEM'
    return f'{COG}/{n}/{n}.tif'

db.executescript("""CREATE TABLE IF NOT EXISTS church_elevation(
    church_id INTEGER PRIMARY KEY, elevation_m REAL, source TEXT, fetched_at TEXT);
    CREATE TABLE IF NOT EXISTS tract_elevation(
    tract_fips TEXT PRIMARY KEY, elevation_m REAL, source TEXT, fetched_at TEXT);""")
db.commit()
now=datetime.now().isoformat()

def run(label, query, table, idcol, commit_every=5000):
    items=db.execute(query).fetchall()
    if not items: print(f'{label}: nothing to do.'); return
    print(f'{label}: {len(items):,} items, sorting...',end='',flush=True)
    items.sort(key=lambda r:tk(r[1],r[2]))
    print('done.')
    
    cur_tile=None; src=None; tiles=0; ok=0; skip=0; t0=time.time()
    for i,(oid,lat,lon) in enumerate(items):
        tile=tk(lat,lon)
        if tile!=cur_tile:
            if src: src.close()
            try:
                src=rasterio.open(url(tile))
                cur_tile=tile; tiles+=1
                if tiles<=3 or tiles%100==0:
                    print(f'\n  [tile {tiles}] {tile} opened', flush=True)
            except Exception as e:
                print(f'\n  [tile FAIL] {tile}: {e}', flush=True)
                cur_tile=tile; src=None; skip+=1; continue
        if src is None: skip+=1; continue
        try:
            r,c=src.index(lon,lat)
            if 0<=r<src.height and 0<=c<src.width:
                e=src.read(1,window=Window(c,r,1,1))
                v=float(e[0,0])
                if v>-100:
                    db.execute(f"INSERT OR REPLACE INTO {table} VALUES(?,?,'copernicus-dem-30m',?)",(oid,v,now))
                    ok+=1
                else: skip+=1
            else: skip+=1
        except: skip+=1
        
        if (i+1)%commit_every==0 or (i+1)==len(items):
            db.commit()
            e=time.time()-t0; rate=(i+1)/e if e>0 else 0
            sys.stdout.write(f'\r  {i+1:,}/{len(items):,} | {rate:.0f}/s | ok={ok:,} skip={skip:,} tiles={tiles} | ETA {(len(items)-i-1)/max(rate,0.001)/60:.0f}m')
            sys.stdout.flush()
    
    if src: src.close()
    db.commit()
    print(f'\n  DONE: {ok:,} ok, {skip:,} skip, {tiles} tiles in {(time.time()-t0)/60:.1f}m')
    return ok

import sys
# US Tracts
run('US TRACTS',"""SELECT t.tract_fips,t.intpt_lat,t.intpt_lon FROM tract_centroids_us t
    LEFT JOIN tract_elevation te ON t.tract_fips=te.tract_fips WHERE te.tract_fips IS NULL""",
    'tract_elevation','tract_fips', commit_every=100)

# US Churches
run('US CHURCHES',"""SELECT c.id,c.latitude,c.longitude FROM churches c
    LEFT JOIN church_elevation ce ON c.id=ce.church_id
    WHERE c.country='US' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL""",'church_elevation','church_id')

# BD
run('BANGLADESH',"""SELECT c.id,c.latitude,c.longitude FROM churches c
    LEFT JOIN church_elevation ce ON c.id=ce.church_id
    WHERE c.country='BD' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL""",'church_elevation','church_id')

# PH
run('PHILIPPINES',"""SELECT c.id,c.latitude,c.longitude FROM churches c
    LEFT JOIN church_elevation ce ON c.id=ce.church_id
    WHERE c.country='PH' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL""",'church_elevation','church_id')

# Stats
for label,q in [('US tracts','SELECT COUNT(*) FROM tract_elevation'),
    ('US churches',"SELECT COUNT(*) FROM church_elevation ce JOIN churches c ON c.id=ce.church_id WHERE c.country='US'"),
    ('BD churches',"SELECT COUNT(*) FROM church_elevation ce JOIN churches c ON c.id=ce.church_id WHERE c.country='BD'"),
    ('PH churches',"SELECT COUNT(*) FROM church_elevation ce JOIN churches c ON c.id=ce.church_id WHERE c.country='PH'")]:
    print(f'{label}: {db.execute(q).fetchone()[0]:,}')
db.close()

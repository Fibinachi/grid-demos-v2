"""Fix Russia — numpy vectorized bbox + name classification. 32GB RAM.""" 
import sqlite3, numpy as np, time
from datetime import datetime, timezone
from shapely import wkb
from shapely.geometry import Point

DB = 'E:/grid/churches.db'
GEO = 'E:/grid/data/natural_earth/world_borders.db'
t0 = time.time()

NEIGHBORS = ["NO","FI","EE","LV","LT","PL","BY","UA","GE","AZ","KZ","CN","MN","KP","US","JP","TR","IR"]

print("Loading polygons...")
gconn = sqlite3.connect(GEO); gc = gconn.cursor()
cpolys = {}
for iso in NEIGHBORS:
    gc.execute("SELECT geometry_wkb FROM world_borders WHERE iso_a2=?", (iso,))
    r = gc.fetchone()
    if r:
        try: cpolys[iso] = (wkb.loads(r[0]), wkb.loads(r[0]).bounds)
        except: pass
gconn.close()
print(f"  {len(cpolys)} neighbor polygons")

print("Loading RU records...")
conn = sqlite3.connect(DB); conn.execute("PRAGMA busy_timeout=30000")
c = conn.cursor()
c.execute("""SELECT rowid, name, latitude, longitude, faith, denomination 
    FROM churches WHERE country='RU' AND source_primary='openstreetmap' AND latitude IS NOT NULL""")
rows = c.fetchall()
print(f"  {len(rows):,} records in {time.time()-t0:.1f}s")

rids = np.array([r[0] for r in rows], dtype=np.int64)
names = [r[1] for r in rows]
lats = np.array([r[2] for r in rows], dtype=np.float64)
lons = np.array([r[3] for r in rows], dtype=np.float64)
faiths = [r[4] for r in rows]
denoms = [r[5] for r in rows]

# ── Border fix ──
print("\nVectorized border check...")
reassign = np.full(len(rows), None, dtype=object)

for iso, (poly, (minx, miny, maxx, maxy)) in cpolys.items():
    if iso == 'RU': continue
    mask = (lats >= miny) & (lats <= maxy) & (lons >= minx) & (lons <= maxx)
    cand = np.where(mask)[0]
    if len(cand) == 0: continue
    n_checked = 0
    for idx in cand:
        if reassign[idx] is not None: continue
        n_checked += 1
        try:
            if poly.contains(Point(lons[idx], lats[idx])):
                reassign[idx] = iso
        except: pass
    print(f"  {iso}: {len(cand):,} candidates")

rc = {}
updates = [(reassign[i], int(rids[i])) for i in range(len(rows)) if reassign[i] is not None]
for iso, _ in updates: rc[iso] = rc.get(iso, 0) + 1
if updates:
    c.executemany("UPDATE churches SET country=? WHERE rowid=?", updates)
print(f"Reassigned: {len(updates):,}")
for iso, cnt in sorted(rc.items(), key=lambda x: -x[1]):
    print(f"  RU → {iso}: {cnt:,}")

# ── Name classification ──
print("\nClassifying...")
ORTH = ["правос","церковь","собо","храм","богоро","свят","троиц",
    "спас","преображ","воскрес","вознес","успен","благовещ","крестовоздв",
    "покро","никол","георг","михайл","александр","андре","петро",
    "иоан","алексе","серги","казанс","владимир","монаст","лавра","скит","пустын","подвор"]
MUS = ["мечет","мече","masjid","mosque","джами","ислам"]
BUD = ["дацан","хурул","buddhist","буддий"]
PROT = ["кирх","kirche","лютеран","luther","евангел","баптист","методист","адвентист","пятидесят","пресвитер","reform"]
CATH = ["костёл","костел","католич","kosciol","katolick"]

ff=0; dd=0; batch=[]
for i in range(len(rows)):
    nl = (names[i] or "").lower()
    f, d = faiths[i] or "", denoms[i] or ""
    nf, nd = f, d
    
    if not f:
        if any(w in nl for w in ORTH): nf,nd='Christian','Russian Orthodox'; ff+=1;dd+=1
        elif any(w in nl for w in MUS): nf,nd='Islam','Sunni Islam'; ff+=1;dd+=1
        elif any(w in nl for w in BUD): nf,nd='Buddhist','Buddhist'; ff+=1;dd+=1
        elif any(w in nl for w in PROT): nf,nd='Christian','Protestant'; ff+=1;dd+=1
        elif any(w in nl for w in CATH): nf,nd='Christian','Roman Catholic'; ff+=1;dd+=1
    elif f=='Christian' and not d:
        if any(w in nl for w in ORTH): nd='Russian Orthodox'; dd+=1
        elif any(w in nl for w in PROT): nd='Protestant'; dd+=1
        elif any(w in nl for w in CATH): nd='Roman Catholic'; dd+=1
    
    if nf!=f or nd!=d:
        batch.append((nf,nd or None,int(rids[i])))
        if len(batch)>=10000:
            c.executemany("UPDATE churches SET faith=?, denomination=? WHERE rowid=?", batch)
            batch=[]
if batch: c.executemany("UPDATE churches SET faith=?, denomination=? WHERE rowid=?", batch)

conn.commit()

# ── Summary ──
c.execute("SELECT COUNT(*) FROM churches WHERE country='RU'")
ru=c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE country='RU' AND denomination IS NOT NULL AND denomination != ''")
d=c.fetchone()[0]
c.execute("SELECT denomination, COUNT(*) FROM churches WHERE country='RU' AND denomination IS NOT NULL AND denomination != '' GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 10")
print(f"\nRussia: {ru:,} total, {d:,} denomination-tagged")
for dn,cnt in c.fetchall(): print(f"  {dn:30s}: {cnt:>8,}")

ts=datetime.now(timezone.utc).isoformat()
c.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_updated,fields_populated,status,notes)
    VALUES(?,?,?,?,?,?,?,?)""",
    ("manual","fix_ru.py",ts,ts,len(updates)+ff+dd,"country,faith,denomination","completed",
     f"RU: {len(updates)} border, {ff} faith, {dd} denom"))
conn.commit(); conn.close()
print(f"\nDone in {(time.time()-t0):.0f}s")

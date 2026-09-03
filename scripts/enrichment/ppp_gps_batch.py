"""GPS match PPP→churches via Census BATCH geocoder (500/batch, retry+resume)."""
import requests, io, csv, time, sys, os, json
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
db = connect()

CACHE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sba", "ppp_geocoded.json")
CACHE = os.path.abspath(CACHE)
os.makedirs(os.path.dirname(CACHE), exist_ok=True)

geocoded = {}
if os.path.exists(CACHE):
    with open(CACHE) as f:
        for k, v in json.load(f).items(): geocoded[int(k)] = v
    print(f"Resume: {len(geocoded):,} cached")

cur = db.execute("""SELECT p.id, p.borrower_address, p.borrower_city, p.borrower_state, p.borrower_zip
    FROM sba_ppp_loans p WHERE p.church_id IS NULL AND p.borrower_address IS NOT NULL
    AND p.borrower_address != '' AND p.naics_code LIKE '813%'""")
all_u = {r[0]: r for r in cur.fetchall()}
todo = {k: v for k, v in all_u.items() if k not in geocoded}
print(f"Total: {len(all_u):,}  To geocode: {len(todo):,}")

if todo:
    cur = db.execute("SELECT id, name, latitude, longitude FROM churches WHERE country='US' AND latitude IS NOT NULL")
    hm = defaultdict(list)
    for cid, nm, lat, lon in cur.fetchall():
        try: hm[(int(float(lat)*100), int(float(lon)*100))].append((cid, float(lat), float(lon)))
        except: pass

    ids = list(todo.keys())
    B = 500
    for bn in range(0, len(ids), B):
        chunk_ids = ids[bn:bn+B]
        buf = io.StringIO()
        w = csv.writer(buf)
        for ppp_id in chunk_ids:
            _, addr, city, st, zip5 = todo[ppp_id]
            w.writerow([ppp_id, addr or "", city or "", st or "", (zip5 or "")[:5]])

        n = bn//B + 1
        tot = (len(ids)+B-1)//B
        ok = False
        for at in range(3):
            try:
                r = requests.post("https://geocoding.geo.census.gov/geocoder/locations/addressbatch",
                    files={"addressFile": ("a.csv", buf.getvalue().encode("utf-8"))},
                    data={"benchmark": "4"}, timeout=60)
                for p in csv.reader(io.StringIO(r.text)):
                    if len(p) >= 6 and p[2].strip().lower() == "match":
                        try:
                            c = p[5].split(",")
                            geocoded[int(p[0])] = [float(c[0]), float(c[1]), p[4]]
                        except: pass
                with open(CACHE, "w") as f: json.dump({str(k): v for k, v in geocoded.items()}, f)
                sys.stdout.write(f"\r  Batch {n}/{tot} ({B} addr) geo={len(geocoded):,}   "); sys.stdout.flush()
                time.sleep(0.3); ok = True; break
            except: time.sleep(5)
        if not ok: print(f"\n  Batch {n} failed"); break

print(f"\n  Geocoded: {len(geocoded):,}")

# Match GPS
print("  Matching GPS...")
m = 0; t0 = time.time()
for i, (pid, (lon, lat, _)) in enumerate(geocoded.items()):
    b = (int(lat*100), int(lon*100))
    best_d = 999; best_c = None
    for dl in range(b[0]-1, b[0]+2):
        for dg in range(b[1]-1, b[1]+2):
            for cid, clat, clon in hm.get((dl, dg), []):
                d = ((lat-clat)**2 + (lon-clon)**2)**0.5
                if d < 0.0005 and d < best_d: best_d = d; best_c = cid
    if best_c:
        db.execute("UPDATE sba_ppp_loans SET church_id=?, match_method='gps_proximity', match_confidence=0.95 WHERE id=?", (best_c, pid))
        m += 1
    if (i+1)%10000 == 0:
        db.commit()
        sys.stdout.write(f"\r    {i+1:,}/{len(geocoded):,} ({100*(i+1)/len(geocoded):.0f}%) m={m:,}"); sys.stdout.flush()

db.commit()
print(f"\r    {len(geocoded):,}/{len(geocoded):,} (100%) matched={m:,} in {time.time()-t0:.0f}s")

for r in db.execute("SELECT match_method, COUNT(*) FROM sba_ppp_loans WHERE church_id IS NOT NULL GROUP BY match_method"):
    print(f"  {r[0]:25s} {r[1]:,}")
db.close()
print("Done!")

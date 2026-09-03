"""Tag religious broadcasters from NTEE codes + attempt FCC facility lookups."""
import sqlite3, json, time, urllib.request, urllib.parse, re

DB = "E:/grid/churches.db"
NOW = __import__('datetime').datetime.utcnow().isoformat()
t0 = time.time()

def log(msg):
    print(f"[{time.time()-t0:5.1f}s] {msg}", flush=True)

# NTEE broadcast codes
NTEE_BROADCAST = ('A32', 'A33', 'A34', 'X82', 'X83', 'X84')

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")

# Check for broadcaster columns — add if needed
cols = [c[1] for c in db.execute("PRAGMA table_info(churches)")]
if "is_broadcaster" not in cols:
    db.execute("ALTER TABLE churches ADD COLUMN is_broadcaster INTEGER DEFAULT 0")
    log("Added is_broadcaster column")
if "fcc_facility_id" not in cols:
    db.execute("ALTER TABLE churches ADD COLUMN fcc_facility_id TEXT")
    log("Added fcc_facility_id column")
if "fcc_call_sign" not in cols:
    db.execute("ALTER TABLE churches ADD COLUMN fcc_call_sign TEXT")
    log("Added fcc_call_sign column")
if "fcc_service_type" not in cols:
    db.execute("ALTER TABLE churches ADD COLUMN fcc_service_type TEXT")
    log("Added fcc_service_type column")
db.commit()

# Tag broadcasters from NTEE
db.execute(f"""
    UPDATE churches SET is_broadcaster = 1
    WHERE substr(ntee_code, 1, 3) IN {NTEE_BROADCAST}
      AND is_broadcaster = 0
""")
tagged = db.execute("SELECT total_changes()").fetchone()[0]
db.commit()
log(f"Tagged {tagged} broadcasters from NTEE codes")

# Show breakdown
for row in db.execute("""
    SELECT CASE substr(ntee_code,1,3) 
        WHEN 'A32' THEN 'Television'
        WHEN 'A33' THEN 'Publishing'  
        WHEN 'A34' THEN 'Radio'
        WHEN 'X82' THEN 'Religious TV'
        WHEN 'X83' THEN 'Religious Publishing'
        WHEN 'X84' THEN 'Religious Radio'
    END as type, COUNT(*) n
    FROM churches WHERE is_broadcaster = 1
    GROUP BY substr(ntee_code,1,3) ORDER BY n DESC
"""):
    log(f"  {row[0]:25s}: {row[1]:3d}")

# Attempt FCC FM Query lookups for radio broadcasters
radio = db.execute("""
    SELECT id, name, city, state FROM churches 
    WHERE is_broadcaster = 1 AND substr(ntee_code,1,3) IN ('A34','X84')
    AND fcc_call_sign IS NULL
    LIMIT 20
""").fetchall()

log(f"\nLooking up {len(radio)} radio broadcasters on FCC FM Query...")
fcc_hits = 0
for cid, name, city, state in radio:
    clean = re.sub(r'[^\w\s]', '', name)[:50]
    try:
        # FCC FM Query by organization name
        url = f"https://transition.fcc.gov/fcc-bin/fmq?call=&serv=FM&name={urllib.parse.quote(clean)}&state={state or ''}&city=&list=1&size=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        
        # Extract facility ID, call sign from results
        fac_match = re.search(r'Facility ID[:\s]*(\d+)', html)
        call_match = re.search(r'Call Sign[:\s]*<[^>]*>(\w+)<', html)
        
        if fac_match:
            fid = fac_match.group(1)
            call = call_match.group(1) if call_match else ""
            db.execute("""
                UPDATE churches SET fcc_facility_id=?, fcc_call_sign=?, fcc_service_type='FM'
                WHERE id=?
            """, (fid, call, cid))
            fcc_hits += 1
            log(f"  {name[:40]:40s} → {call:6s} (FID: {fid})")
    except Exception:
        pass
    time.sleep(0.3)

db.commit()
log(f"\nFCC lookups: {fcc_hits}/{len(radio)} matched")

total = db.execute("SELECT COUNT(*) FROM churches WHERE is_broadcaster = 1").fetchone()[0]
with_fcc = db.execute("SELECT COUNT(*) FROM churches WHERE is_broadcaster = 1 AND fcc_facility_id IS NOT NULL").fetchone()[0]
db.close()

log(f"\nBroadcasters: {total:,} tagged | {with_fcc} with FCC facility IDs")
log("Done")

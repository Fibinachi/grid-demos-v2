"""Insert unmatched PPP orgs as new churches — name+ZIP grouped."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect

db = connect()
db._conn.execute("PRAGMA busy_timeout=10000")
db.execute("CREATE INDEX IF NOT EXISTS idx_churches_name_zip ON churches(UPPER(name), zip5)")
db.execute("CREATE INDEX IF NOT EXISTS idx_ppp_name_zip ON sba_ppp_loans(UPPER(borrower_name), borrower_zip)")
db.commit()

cur = db.execute("""
    SELECT borrower_name, borrower_address, borrower_city,
           borrower_state, borrower_zip,
           CAST(SUM(loan_amount) AS INTEGER), SUM(jobs_reported)
    FROM sba_ppp_loans
    WHERE church_id IS NULL AND naics_code='813110' AND borrower_name IS NOT NULL
    GROUP BY UPPER(borrower_name), borrower_zip, borrower_state
    ORDER BY SUM(loan_amount) DESC
""")
candidates = cur.fetchall()
total = len(candidates)
max_id = db.execute("SELECT MAX(id) FROM churches").fetchone()[0] or 0
print(f"Candidates: {total:,} | Max ID: {max_id:,}")

new = late = 0
t0 = time.time()

for i, (name, addr, city, state, zip5, loan, jobs) in enumerate(candidates):
    cur = db.execute("SELECT id FROM churches WHERE UPPER(name)=UPPER(?) AND zip5=? AND country='US'", (name or "", zip5))
    ex = cur.fetchone()
    
    if ex:
        db.execute("UPDATE sba_ppp_loans SET church_id=?, match_method='late' WHERE UPPER(borrower_name)=UPPER(?) AND borrower_zip=? AND church_id IS NULL", (ex[0], name, zip5))
        late += 1
    else:
        max_id += 1
        db.execute("INSERT INTO churches (id,name,address,city,state,zip5,country,faith,source,landmark_type,taxonomy_id) VALUES (?,?,?,?,?,?,'US','Christian','sba_ppp','church',2)", (max_id, name, addr, city, state, zip5))
        db.execute("UPDATE sba_ppp_loans SET church_id=?, match_method='new' WHERE UPPER(borrower_name)=UPPER(?) AND borrower_zip=? AND church_id IS NULL", (max_id, name, zip5))
        new += 1

    if (i+1) % 250 == 0 or i == total-1:
        db.commit()
        elapsed = time.time()-t0
        pct = (i+1)/total*100
        rate = (i+1)/elapsed if elapsed>0 else 0
        eta = (total-i-1)/rate/60 if rate>0 else 0
        bar = chr(0x2588)*int(30*(i+1)/total) + chr(0x2591)*(30-int(30*(i+1)/total))
        sys.stdout.write(f"\r{bar} {i+1:>5}/{total} ({pct:>4.0f}%) new={new:<6} late={late:<5} {rate:>4.0f}/s ETA={eta:>3.0f}m")
        sys.stdout.flush()

db.commit()
elapsed = time.time()-t0
print(f"\n\nDone in {elapsed:.0f}s — {new:,} new churches, {late:,} late-matched")

cur = db.execute("SELECT match_method, COUNT(*), COUNT(DISTINCT church_id) FROM sba_ppp_loans WHERE church_id IS NOT NULL GROUP BY match_method")
print("\nAll matches:")
for r in cur.fetchall(): print(f"  {r[0]:25s} {r[1]:8,} loans  {r[2]:,} churches")

cur = db.execute("SELECT COUNT(*) FROM churches WHERE source='sba_ppp'")
print(f"\nTotal PPP churches: {cur.fetchone()[0]:,}")
db.close()

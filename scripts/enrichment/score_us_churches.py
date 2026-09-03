"""
score_us_churches.py — Per-church scoring for US slice (optimized).

Scores:
  1. political_lean (0-100): County vote × denomination baseline
  2. financial_health (0-100): PPP + IRS ZIP composite
  3. size_tier (1-5): Building footprint
  4. contact_score (0-100): Website/phone/email completeness

All JOIN-based, no correlated subqueries. Batch commits.
"""
import sqlite3, sys, os, time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
from gw_db import connect as get_db

CHUNK = 5000

def progress(msg):
    print(f'  {msg}...', end=' ', flush=True)

def elapsed(t0):
    return f'({time.time()-t0:.0f}s)'

print('=' * 70)
print('US CHURCH SCORING PIPELINE (optimized)')
print('=' * 70)

db = get_db()
c = db.cursor()
t_total = time.time()

# ── STEP 0: Drop and create ──
t0 = time.time()
progress('Creating church_scores_us')
c.execute('DROP TABLE IF EXISTS church_scores_us')
c.execute('''
    CREATE TABLE church_scores_us (
        church_id INTEGER PRIMARY KEY,
        name TEXT, city TEXT, state TEXT, faith TEXT, tradition TEXT,
        county_fips TEXT, latitude REAL, longitude REAL,
        political_lean INTEGER, political_confidence REAL,
        denom_political_baseline REAL,
        financial_health INTEGER,
        ppp_loan_amount REAL, ppp_forgiveness_pct REAL, ppp_jobs_reported INTEGER,
        zip_agi_avg_k REAL, zip_charitable_pct REAL,
        building_sqft REAL, parking_estimate INTEGER, size_tier INTEGER,
        has_website INTEGER, has_phone INTEGER, has_email INTEGER, contact_score INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    )
''')
db.commit()
print(f'done {elapsed(t0)}')

# ── STEP 1: Load US churches with building data ──
print('\n── STEP 1: Load base data ──')
t0 = time.time()
progress('Inserting US churches + building sqft')
c.execute('''
    INSERT INTO church_scores_us (church_id, name, city, state, faith, tradition, 
                                   county_fips, latitude, longitude, building_sqft, parking_estimate)
    SELECT c.id, c.name, c.city, c.state, c.faith, c.tradition,
           c.county_fips_5, c.latitude, c.longitude,
           b.building_area_sqft, b.parking_estimate_spots
    FROM churches c
    LEFT JOIN church_building_sqft_us b ON c.id = b.church_id
    WHERE c.country = 'US' AND c.latitude IS NOT NULL
''')
db.commit()
c.execute('SELECT COUNT(*) FROM church_scores_us')
n = c.fetchone()[0]
print(f'done {elapsed(t0)}  |  {n:,} churches')

# ── STEP 2: Political Lean ──
print('\n── STEP 2: Political Lean Scoring ──')
t0 = time.time()

# 2a: County-level GOP share (direct JOIN)
progress('County-level GOP share via JOIN')
c.execute('''
    UPDATE church_scores_us
    SET political_lean = CAST(ROUND(e.rep_share) AS INTEGER),
        political_confidence = 0.7
    FROM election_results e
    WHERE church_scores_us.county_fips = e.county_fips
      AND church_scores_us.county_fips IS NOT NULL
      AND church_scores_us.county_fips != ''
''')
db.commit()
c.execute('SELECT COUNT(*) FROM church_scores_us WHERE political_lean IS NOT NULL')
print(f'done {elapsed(t0)}  |  {c.fetchone()[0]:,} with county lean')

# 2b: Denomination baseline
t0 = time.time()
progress('Denomination baselines + backfill')
c.execute('DROP TABLE IF EXISTS tmp_denom_baseline')
c.execute('''
    CREATE TEMP TABLE tmp_denom_baseline AS
    SELECT s.tradition, ROUND(AVG(e.rep_share), 1) as baseline
    FROM church_scores_us s
    INNER JOIN election_results e ON s.county_fips = e.county_fips
    WHERE s.county_fips IS NOT NULL AND s.county_fips != '' AND s.tradition IS NOT NULL
    GROUP BY s.tradition
    HAVING COUNT(*) >= 10
''')
c.execute('''
    UPDATE church_scores_us
    SET political_lean = CAST(d.baseline AS INTEGER),
        political_confidence = 0.5,
        denom_political_baseline = d.baseline
    FROM tmp_denom_baseline d
    WHERE church_scores_us.tradition = d.tradition
      AND church_scores_us.political_lean IS NULL
''')
db.commit()
c.execute('SELECT COUNT(*) FROM church_scores_us WHERE political_lean IS NOT NULL')
print(f'done {elapsed(t0)}  |  {c.fetchone()[0]:,} with lean')

# 2c: State-level fallback
t0 = time.time()
progress('State-level fallback')
c.execute('''
    UPDATE church_scores_us
    SET political_lean = CAST(ROUND(
        (SELECT AVG(e.rep_share) FROM election_results e WHERE e.state = church_scores_us.state)
    ) AS INTEGER),
    political_confidence = 0.4
    WHERE political_lean IS NULL AND state IS NOT NULL
''')
db.commit()

# 2d: Denom baseline for remaining
c.execute('''
    UPDATE church_scores_us
    SET denom_political_baseline = (
        SELECT d.baseline FROM tmp_denom_baseline d WHERE d.tradition = church_scores_us.tradition
    )
    WHERE denom_political_baseline IS NULL AND tradition IS NOT NULL
''')
db.commit()
c.execute('DROP TABLE IF EXISTS tmp_denom_baseline')

c.execute('''SELECT political_confidence, COUNT(*) 
    FROM church_scores_us WHERE political_lean IS NOT NULL GROUP BY 1 ORDER BY 1''')
for row in c.fetchall():
    print(f'    confidence={row[0]}: {row[1]:,}')
print(f'done {elapsed(t0)}')

# ── STEP 3: Financial Health ──
print('\n── STEP 3: Financial Health Scoring ──')

t0 = time.time()
progress('PPP loan data via JOIN')
c.execute('''
    UPDATE church_scores_us
    SET ppp_loan_amount = p.loan_amount,
        ppp_forgiveness_pct = CASE WHEN p.loan_amount > 0 
            THEN ROUND(COALESCE(p.forgiveness_amount, 0) / p.loan_amount * 100, 1) END,
        ppp_jobs_reported = p.jobs_reported
    FROM sba_ppp_loans p
    WHERE church_scores_us.church_id = p.church_id
''')
db.commit()
c.execute('SELECT COUNT(*) FROM church_scores_us WHERE ppp_loan_amount IS NOT NULL')
print(f'done {elapsed(t0)}  |  {c.fetchone()[0]:,} with PPP')

t0 = time.time()
progress('IRS ZIP income via JOIN')
c.execute("PRAGMA table_info(churches)")
church_cols = [r[1] for r in c.fetchall()]
zip_col = 'zip5' if 'zip5' in church_cols else ('zip' if 'zip' in church_cols else None)

if zip_col:
    c.execute('DROP TABLE IF EXISTS tmp_zip_agi')
    c.execute(f'''
        CREATE TEMP TABLE tmp_zip_agi AS
        SELECT i.zipcode, ROUND(AVG(i.agi_amount_k / NULLIF(i.return_count, 0)), 1) as avg_agi_k,
               SUM(i.return_count) as total_returns
        FROM irs_zip_data i WHERE i.return_count > 0 GROUP BY i.zipcode
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS tmp_idx_zip ON tmp_zip_agi(zipcode)')
    
    c.execute(f'''
        UPDATE church_scores_us
        SET zip_agi_avg_k = z.avg_agi_k,
            zip_charitable_pct = CASE WHEN z.avg_agi_k > 100 THEN 3.0
                                      WHEN z.avg_agi_k > 50 THEN 2.0 ELSE 1.0 END
        FROM churches ch, tmp_zip_agi z
        WHERE church_scores_us.church_id = ch.id AND ch.{zip_col} = z.zipcode
    ''')
    db.commit()
    c.execute('DROP TABLE IF EXISTS tmp_zip_agi')
    c.execute('SELECT COUNT(*) FROM church_scores_us WHERE zip_agi_avg_k IS NOT NULL')
    print(f'done {elapsed(t0)}  |  {c.fetchone()[0]:,} with ZIP data')
else:
    print(f'  No ZIP column — skipping. {elapsed(t0)}')

t0 = time.time()
progress('Computing financial_health composite')
c.execute('''
    UPDATE church_scores_us
    SET financial_health = CAST(ROUND(
        MIN(40, COALESCE(ppp_loan_amount, 0) / 25000) +
        COALESCE(ppp_forgiveness_pct, 0) * 0.2 +
        MIN(25, COALESCE(zip_agi_avg_k, 0) / 8) +
        MIN(15, COALESCE(zip_charitable_pct, 0) * 1.5)
    ) AS INTEGER)
    WHERE ppp_loan_amount IS NOT NULL OR zip_agi_avg_k IS NOT NULL
''')
db.commit()

c.execute('''SELECT COUNT(*) as total, ROUND(AVG(financial_health),1) as avg,
    COUNT(CASE WHEN financial_health>=60 THEN 1 END) as healthy,
    COUNT(CASE WHEN financial_health<20 THEN 1 END) as struggling
FROM church_scores_us WHERE financial_health IS NOT NULL''')
row = c.fetchone()
print(f'done {elapsed(t0)}')
print(f'    {row[0]:,} scored | avg={row[1]} | healthy(60+): {row[2]:,} | struggling(<20): {row[3]:,}')
print(f'    {n - row[0]:,} churches without financial data')

# ── STEP 4: Size Tier ──
print('\n── STEP 4: Size Tier ──')
t0 = time.time()
progress('Computing size tiers')
c.execute('''
    UPDATE church_scores_us
    SET size_tier = CASE
        WHEN building_sqft IS NULL THEN NULL
        WHEN building_sqft < 2000 THEN 1
        WHEN building_sqft < 5000 THEN 2
        WHEN building_sqft < 15000 THEN 3
        WHEN building_sqft < 40000 THEN 4
        ELSE 5
    END
''')
db.commit()
c.execute('SELECT size_tier, COUNT(*) FROM church_scores_us WHERE size_tier IS NOT NULL GROUP BY 1 ORDER BY 1')
tiers = {1:'Tiny',2:'Small',3:'Medium',4:'Large',5:'Mega'}
for row in c.fetchall():
    print(f'    Tier {row[0]} ({tiers[row[0]]}): {row[1]:,}')
print(f'done {elapsed(t0)}')

# ── STEP 5: Contact Completeness (JOIN) ──
print('\n── STEP 5: Contact Completeness ──')
t0 = time.time()
progress('Computing contact flags via JOIN')
c.execute('DROP TABLE IF EXISTS tmp_contacts')
c.execute('''
    CREATE TEMP TABLE tmp_contacts AS
    SELECT church_id,
           MAX(CASE WHEN contact_type='website' THEN 1 ELSE 0 END) as has_website,
           MAX(CASE WHEN contact_type='phone' THEN 1 ELSE 0 END) as has_phone,
           MAX(CASE WHEN contact_type='email' THEN 1 ELSE 0 END) as has_email
    FROM church_contact_values
    WHERE contact_type IN ('website','phone','email')
    GROUP BY church_id
''')
c.execute('CREATE INDEX IF NOT EXISTS tmp_idx_contacts ON tmp_contacts(church_id)')

c.execute('''
    UPDATE church_scores_us
    SET has_website = t.has_website, has_phone = t.has_phone, has_email = t.has_email
    FROM tmp_contacts t
    WHERE church_scores_us.church_id = t.church_id
''')
db.commit()

c.execute('''
    UPDATE church_scores_us
    SET contact_score = COALESCE(has_website,0)*40 + COALESCE(has_phone,0)*35 + COALESCE(has_email,0)*25
''')
db.commit()
c.execute('DROP TABLE IF EXISTS tmp_contacts')

c.execute('''SELECT COUNT(*) as total, ROUND(AVG(contact_score),1) as avg,
    COUNT(CASE WHEN contact_score>=75 THEN 1 END) as reachable,
    COUNT(CASE WHEN contact_score=0 THEN 1 END) as none
FROM church_scores_us''')
row = c.fetchone()
print(f'done {elapsed(t0)}')
print(f'    {row[0]:,} scored | avg={row[1]} | 75+: {row[2]:,} | none: {row[3]:,}')

# ── STEP 6: Indexes ──
print('\n── STEP 6: Indexes ──')
t0 = time.time()
for idx in ['state','tradition','political_lean','financial_health','size_tier','contact_score']:
    c.execute(f'CREATE INDEX IF NOT EXISTS idx_scores_{idx} ON church_scores_us({idx})')
db.commit()
print(f'done {elapsed(t0)}')

# ── FINAL SUMMARY ──
print()
print('=' * 70)
print('FINAL SUMMARY')
print('=' * 70)
c.execute('SELECT COUNT(*) FROM church_scores_us')
total = c.fetchone()[0]
c.execute('''SELECT 
    COUNT(CASE WHEN political_lean IS NOT NULL THEN 1 END) as political,
    COUNT(CASE WHEN financial_health IS NOT NULL THEN 1 END) as financial,
    COUNT(CASE WHEN size_tier IS NOT NULL THEN 1 END) as sized,
    COUNT(CASE WHEN contact_score IS NOT NULL THEN 1 END) as contacted,
    ROUND(AVG(political_lean),1) as avg_lean,
    ROUND(AVG(financial_health),1) as avg_finance,
    ROUND(AVG(contact_score),1) as avg_contact
FROM church_scores_us''')
row = c.fetchone()
print(f'Total US churches scored: {total:,}')
print(f'  Political lean:    {row[0]:,}  avg={row[4]} (0=Dem, 100=GOP)')
print(f'  Financial health:  {row[1]:,}  avg={row[5]}')
print(f'  Size tier:         {row[2]:,}')
print(f'  Contact score:     {row[3]:,}  avg={row[6]}')

# Top samples
print('\n── Top Influential Conservative Churches in Swing States ──')
swing = ('PA','MI','WI','GA','AZ','NV','NC')
placeholders = ','.join('?' * len(swing))
c.execute(f'''
    SELECT name, city, state, political_lean, financial_health, size_tier,
           ROUND(COALESCE(building_sqft,0),0) as sqft, contact_score
    FROM church_scores_us
    WHERE state IN ({placeholders})
      AND political_lean >= 60 AND size_tier >= 4
    ORDER BY COALESCE(building_sqft,0) DESC
    LIMIT 10
''', swing)
for row in c.fetchall():
    fin = str(row[4]) if row[4] is not None else '-'
    print(f'  {row[0][:40]:40s} {row[1]:15s} {row[2]:3s}  lean={row[3]:3.0f}  fin={fin:>3}  tier={row[5]}  {row[6]:>8,.0f}sqft  contact={row[7]}')

print(f'\nPipeline complete in {time.time()-t_total:.0f}s')
db.close()

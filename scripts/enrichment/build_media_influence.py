"""
build_media_influence.py — FCC media influence scoring for US churches.

Method:
  1. Map churches to FCC broadcast facilities (via church_fcc)
  2. Score = facility power (ERP kW) × coverage population (broadcast_coverage)
  3. Create composite media_influence score per church

Output: church_media_influence table
"""
import sqlite3, sys, os, time, math

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
from gw_db import connect as get_db

def elapsed(t0):
    return f'({time.time()-t0:.0f}s)'

print('=' * 70)
print('MEDIA INFLUENCE SCORING')
print('=' * 70)

db = get_db()
c = db.cursor()
t_total = time.time()

# ── STEP 1: Create table ──
t0 = time.time()
c.execute('DROP TABLE IF EXISTS church_media_influence')
c.execute('''
    CREATE TABLE church_media_influence (
        church_id INTEGER PRIMARY KEY,
        name TEXT, city TEXT, state TEXT,
        
        -- FCC broadcast
        fcc_facility_count INTEGER,
        fcc_total_erp_kw REAL,
        fcc_max_erp_kw REAL,
        fcc_callsigns TEXT,
        
        -- Broadcast ministries
        is_broadcast_ministry INTEGER,
        broadcast_type TEXT,
        broadcast_network TEXT,
        
        -- Coverage population
        coverage_population_est INTEGER,
        
        -- Composite scores
        media_reach_score REAL,        -- 0-100 incorporating ERP + coverage
        media_influence_tier INTEGER,  -- 1-5
        
        created_at TEXT DEFAULT (datetime('now'))
    )
''')
db.commit()
print(f'Created church_media_influence {elapsed(t0)}')

# ── STEP 2: Load US churches ──
print()
t0 = time.time()
print('Loading US churches...')
c.execute('''
    INSERT INTO church_media_influence (church_id, name, city, state)
    SELECT id, name, city, state
    FROM churches
    WHERE country = 'US' AND latitude IS NOT NULL
''')
db.commit()
c.execute('SELECT COUNT(*) FROM church_media_influence')
n = c.fetchone()[0]
print(f'  {n:,} churches {elapsed(t0)}')

# ── STEP 3: FCC facility links ──
print()
t0 = time.time()
print('Joining FCC facility links...')

# Count facilities per church
c.execute('DROP TABLE IF EXISTS tmp_fcc_agg')
c.execute('''
    CREATE TEMP TABLE tmp_fcc_agg AS
    SELECT cf.church_id,
           COUNT(DISTINCT cf.facility_id) as facility_count,
           SUM(COALESCE(bt.erp_kw, 0)) as total_erp_kw,
           MAX(COALESCE(bt.erp_kw, 0)) as max_erp_kw,
           GROUP_CONCAT(DISTINCT cf.call_sign) as callsigns
    FROM church_fcc cf
    LEFT JOIN broadcast_transmitters bt ON cf.facility_id = bt.fcc_facility_id
    GROUP BY cf.church_id
''')
c.execute('CREATE INDEX IF NOT EXISTS tmp_fcc_idx ON tmp_fcc_agg(church_id)')

c.execute('''
    UPDATE church_media_influence
    SET fcc_facility_count = f.facility_count,
        fcc_total_erp_kw = f.total_erp_kw,
        fcc_max_erp_kw = f.max_erp_kw,
        fcc_callsigns = f.callsigns
    FROM tmp_fcc_agg f
    WHERE church_media_influence.church_id = f.church_id
''')
db.commit()

c.execute('SELECT COUNT(*) FROM church_media_influence WHERE fcc_facility_count > 0')
print(f'  {c.fetchone()[0]:,} with FCC facilities {elapsed(t0)}')

# ── STEP 4: Broadcast ministry flags ──
print()
t0 = time.time()
print('Joining broadcast ministry data...')

# Church broadcast links
c.execute('DROP TABLE IF EXISTS tmp_broadcast')
c.execute('''
    CREATE TEMP TABLE tmp_broadcast AS
    SELECT cb.church_id,
           MAX(CASE WHEN cb.is_broadcast_ministry = 1 THEN 1 ELSE 0 END) as is_ministry,
           GROUP_CONCAT(DISTINCT bm.type) as types,
           GROUP_CONCAT(DISTINCT bm.network) as networks
    FROM church_broadcast cb
    LEFT JOIN broadcast_ministries bm ON cb.broadcast_ministry_id = bm.id
    GROUP BY cb.church_id
''')
c.execute('CREATE INDEX IF NOT EXISTS tmp_bcast_idx ON tmp_broadcast(church_id)')

c.execute('''
    UPDATE church_media_influence
    SET is_broadcast_ministry = b.is_ministry,
        broadcast_type = b.types,
        broadcast_network = b.networks
    FROM tmp_broadcast b
    WHERE church_media_influence.church_id = b.church_id
''')
db.commit()

c.execute('SELECT COUNT(*) FROM church_media_influence WHERE is_broadcast_ministry = 1')
print(f'  {c.fetchone()[0]:,} broadcast ministries {elapsed(t0)}')

# ── STEP 5: Coverage population estimate ──
print()
t0 = time.time()
print('Estimating coverage population...')

# Sum population in covered counties, weighted by coverage strength
c.execute('DROP TABLE IF EXISTS tmp_coverage_pop')
c.execute('''
    CREATE TEMP TABLE tmp_coverage_pop AS
    SELECT cf.church_id,
           SUM(cc.total_pop * COALESCE(bc.coverage_strength, 0.5)) as coverage_pop
    FROM church_fcc cf
    JOIN broadcast_coverage bc ON cf.facility_id = bc.broadcast_id
    JOIN county_census_us cc ON bc.fips = cc.county_fips
    GROUP BY cf.church_id
''')
c.execute('CREATE INDEX IF NOT EXISTS tmp_cov_idx ON tmp_coverage_pop(church_id)')

c.execute('''
    UPDATE church_media_influence
    SET coverage_population_est = CAST(t.coverage_pop AS INTEGER)
    FROM tmp_coverage_pop t
    WHERE church_media_influence.church_id = t.church_id
''')
db.commit()

c.execute('SELECT COUNT(*) FROM church_media_influence WHERE coverage_population_est > 0')
print(f'  {c.fetchone()[0]:,} with coverage estimates {elapsed(t0)}')

# ── STEP 6: Compute media reach score (0-100) ──
print()
t0 = time.time()
print('Computing media reach scores...')

# Formula: log-scale ERP (0-60) + coverage population (0-40)
# ERP 0=0, 100kW=60. Coverage 0=0, 10M+=40
c.execute('''
    UPDATE church_media_influence
    SET media_reach_score = CAST(ROUND(
        MIN(60, LN(COALESCE(NULLIF(fcc_total_erp_kw, 0), 0.001) + 1) * 8) +
        MIN(40, COALESCE(coverage_population_est, 0) / 250000.0)
    ) AS INTEGER),
    media_influence_tier = CASE
        WHEN fcc_facility_count IS NULL OR fcc_facility_count = 0 THEN 0
        WHEN COALESCE(fcc_total_erp_kw, 0) >= 50 OR COALESCE(coverage_population_est, 0) >= 5000000 THEN 5
        WHEN COALESCE(fcc_total_erp_kw, 0) >= 10 OR COALESCE(coverage_population_est, 0) >= 1000000 THEN 4
        WHEN COALESCE(fcc_total_erp_kw, 0) >= 1 THEN 3
        WHEN fcc_facility_count > 0 THEN 2
        ELSE 1
    END
    WHERE fcc_facility_count > 0 OR is_broadcast_ministry = 1
''')
db.commit()

# ── STEP 7: Stats ──
print()
print('=' * 70)
print('MEDIA INFLUENCE STATISTICS')
print('=' * 70)

c.execute('''SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN fcc_facility_count > 0 THEN 1 END) as with_fcc,
    COUNT(CASE WHEN is_broadcast_ministry = 1 THEN 1 END) as broadcast_ministries,
    COUNT(CASE WHEN coverage_population_est > 0 THEN 1 END) as with_coverage,
    ROUND(AVG(media_reach_score),1) as avg_score
FROM church_media_influence''')
row = c.fetchone()
print(f'Total churches: {row[0]:,}')
print(f'  With FCC facilities: {row[1]:,}')
print(f'  Broadcast ministries: {row[2]:,}')
print(f'  With coverage estimates: {row[3]:,}')
print(f'  Avg media reach score: {row[4]}')

c.execute('SELECT media_influence_tier, COUNT(*) FROM church_media_influence WHERE media_influence_tier > 0 GROUP BY 1 ORDER BY 1')
tiers = {1:'Minimal',2:'Local',3:'Regional',4:'Major Market',5:'National'}
for row in c.fetchall():
    print(f'  Tier {row[0]} ({tiers.get(row[0],"?")}): {row[1]:,}')

# Top 15 media-influential churches
print('\nTop 15 Media-Influential Churches:')
c.execute('''
    SELECT name, city, state, fcc_total_erp_kw, coverage_population_est, 
           media_reach_score, fcc_callsigns, broadcast_type
    FROM church_media_influence
    WHERE media_reach_score > 0
    ORDER BY media_reach_score DESC
    LIMIT 15
''')
for row in c.fetchall():
    erp = f'{row[3]:.0f}kW' if row[3] else '-'
    cov = f'{row[4]:,}' if row[4] else '-'
    calls = row[6][:25] if row[6] else '-'
    btype = row[7][:15] if row[7] else '-'
    print(f'  {row[0][:35]:35s} {row[1]:12s} {row[2]:3s}  ERP={erp:>8s}  cov={cov:>10s}  score={row[5]:3.0f}  [{calls}] [{btype}]')

# Cleanup
c.execute('DROP TABLE IF EXISTS tmp_fcc_agg')
c.execute('DROP TABLE IF EXISTS tmp_broadcast')
c.execute('DROP TABLE IF EXISTS tmp_coverage_pop')

c.execute('CREATE INDEX IF NOT EXISTS idx_media_reach ON church_media_influence(media_reach_score)')
c.execute('CREATE INDEX IF NOT EXISTS idx_media_tier ON church_media_influence(media_influence_tier)')
db.commit()

total_time = time.time() - t_total
print(f'\nPipeline complete in {total_time:.0f}s')
db.close()

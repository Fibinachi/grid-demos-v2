"""
build_catchment_demographics.py — Compute local-area demographics for US churches.

Method:
  Uses existing church_census_us (tract-level ACS) for radius-based catchment.
  For churches WITHOUT tract data, falls back to county-level census.

Output: church_catchment_demographics table
"""
import sqlite3, sys, os, time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
from gw_db import connect as get_db

def elapsed(t0):
    return f'({time.time()-t0:.0f}s)'

print('=' * 70)
print('CATCHMENT AREA DEMOGRAPHICS')
print('=' * 70)

db = get_db()
c = db.cursor()
t_total = time.time()

# ── STEP 1: Create table ──
t0 = time.time()
c.execute('DROP TABLE IF EXISTS church_catchment_demographics')
c.execute('''
    CREATE TABLE church_catchment_demographics (
        church_id INTEGER PRIMARY KEY,
        name TEXT, city TEXT, state TEXT,
        
        -- Tract-level ACS (from church_census_us)
        tract_total_pop INTEGER,
        tract_median_income INTEGER,
        tract_poverty_rate REAL,
        tract_white_pct REAL,
        tract_black_pct REAL,
        tract_hispanic_pct REAL,
        tract_asian_pct REAL,
        tract_bachelors_pct REAL,
        tract_median_age REAL,
        tract_unemployment_rate REAL,
        tract_median_home_value INTEGER,
        
        -- County-level fallback
        county_total_pop INTEGER,
        county_median_income INTEGER,
        county_poverty_rate REAL,
        county_white_pct REAL,
        county_black_pct REAL,
        county_hispanic_pct REAL,
        county_asian_pct REAL,
        
        -- Effective demographics (prefer tract, fall back to county)
        effective_pop INTEGER,
        effective_median_income INTEGER,
        effective_poverty_rate REAL,
        effective_white_pct REAL,
        effective_black_pct REAL,
        effective_hispanic_pct REAL,
        effective_asian_pct REAL,
        effective_density TEXT,  -- 'urban', 'suburban', 'rural'
        
        -- Data source indicator
        demographic_source TEXT,  -- 'tract' or 'county'
        
        created_at TEXT DEFAULT (datetime('now'))
    )
''')
db.commit()
print(f'Created table {elapsed(t0)}')

# ── STEP 2: Load US churches ──
t0 = time.time()
print('Loading US churches...')
c.execute('''
    INSERT INTO church_catchment_demographics (church_id, name, city, state)
    SELECT id, name, city, state
    FROM churches
    WHERE country = 'US' AND latitude IS NOT NULL
''')
db.commit()
c.execute('SELECT COUNT(*) FROM church_catchment_demographics')
n = c.fetchone()[0]
print(f'  {n:,} churches {elapsed(t0)}')

# ── STEP 3: Tract-level demographics (from church_census_us) ──
t0 = time.time()
print('Joining tract-level ACS data...')
c.execute('''
    UPDATE church_catchment_demographics
    SET tract_total_pop = cu.acs_total_pop,
        tract_median_income = cu.acs_median_income,
        tract_poverty_rate = cu.acs_poverty_rate,
        tract_white_pct = ROUND(cu.acs_white_pop * 100.0 / NULLIF(cu.acs_total_pop, 0), 1),
        tract_black_pct = ROUND(cu.acs_black_pop * 100.0 / NULLIF(cu.acs_total_pop, 0), 1),
        tract_hispanic_pct = ROUND(cu.acs_hispanic_pop * 100.0 / NULLIF(cu.acs_total_pop, 0), 1),
        tract_asian_pct = ROUND(cu.acs_asian_pop * 100.0 / NULLIF(cu.acs_total_pop, 0), 1),
        tract_median_age = cu.acs_median_age,
        tract_unemployment_rate = cu.acs_unemployment_rate,
        tract_median_home_value = cu.acs_median_home_value,
        demographic_source = 'tract'
    FROM church_census_us cu
    WHERE church_catchment_demographics.church_id = cu.church_id
''')
db.commit()
c.execute("SELECT COUNT(*) FROM church_catchment_demographics WHERE demographic_source = 'tract'")
print(f'  {c.fetchone()[0]:,} with tract-level data {elapsed(t0)}')

# ── STEP 4: County-level fallback ──
t0 = time.time()
print('Applying county-level fallback...')

# First, get county_fips for unmatched churches
c.execute('DROP TABLE IF EXISTS tmp_county_map')
c.execute('''
    CREATE TEMP TABLE tmp_county_map AS
    SELECT cdm.church_id, ch.county_fips_5
    FROM church_catchment_demographics cdm
    INNER JOIN churches ch ON cdm.church_id = ch.id
    WHERE cdm.demographic_source IS NULL
''')
c.execute('CREATE INDEX IF NOT EXISTS tmp_county_idx ON tmp_county_map(county_fips_5)')

c.execute('''
    UPDATE church_catchment_demographics
    SET county_total_pop = cc.total_pop,
        county_median_income = cc.median_hh_income,
        county_poverty_rate = cc.poverty_rate,
        county_white_pct = cc.white_pct,
        county_black_pct = cc.black_pct,
        county_hispanic_pct = cc.hispanic_pct,
        county_asian_pct = cc.asian_pct,
        demographic_source = 'county'
    FROM tmp_county_map m
    INNER JOIN county_census_us cc ON m.county_fips_5 = cc.county_fips
    WHERE church_catchment_demographics.church_id = m.church_id
      AND church_catchment_demographics.demographic_source IS NULL
''')
db.commit()
c.execute("SELECT COUNT(*) FROM church_catchment_demographics WHERE demographic_source = 'county'")
print(f'  {c.fetchone()[0]:,} with county-level fallback {elapsed(t0)}')

c.execute('DROP TABLE IF EXISTS tmp_county_map')

# ── STEP 5: Compute effective demographics ──
t0 = time.time()
print('Computing effective demographics (tract > county)...')
c.execute('''
    UPDATE church_catchment_demographics
    SET effective_pop = COALESCE(tract_total_pop, county_total_pop),
        effective_median_income = COALESCE(tract_median_income, county_median_income),
        effective_poverty_rate = COALESCE(tract_poverty_rate, county_poverty_rate),
        effective_white_pct = COALESCE(tract_white_pct, county_white_pct),
        effective_black_pct = COALESCE(tract_black_pct, county_black_pct),
        effective_hispanic_pct = COALESCE(tract_hispanic_pct, county_hispanic_pct),
        effective_asian_pct = COALESCE(tract_asian_pct, county_asian_pct)
    WHERE demographic_source IS NOT NULL
''')
db.commit()

# Compute density classification
c.execute('''
    UPDATE church_catchment_demographics
    SET effective_density = CASE
        WHEN effective_pop >= 4000 AND effective_pop IS NOT NULL THEN 'urban'
        WHEN effective_pop >= 2000 THEN 'suburban'
        ELSE 'rural'
    END
    WHERE effective_pop IS NOT NULL
''')
db.commit()

c.execute('SELECT COUNT(*) FROM church_catchment_demographics WHERE effective_pop IS NOT NULL')
print(f'  {c.fetchone()[0]:,} with effective demographics {elapsed(t0)}')

# ── STEP 6: Stats ──
print()
print('=' * 70)
print('CATCHMENT DEMOGRAPHICS SUMMARY')
print('=' * 70)

c.execute('''SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN demographic_source = 'tract' THEN 1 END) as tract_level,
    COUNT(CASE WHEN demographic_source = 'county' THEN 1 END) as county_level,
    COUNT(CASE WHEN demographic_source IS NULL THEN 1 END) as unmatched,
    ROUND(AVG(effective_pop),0) as avg_pop,
    ROUND(AVG(effective_median_income),0) as avg_income,
    ROUND(AVG(effective_poverty_rate),1) as avg_poverty
FROM church_catchment_demographics''')
row = c.fetchone()
print(f'Total churches: {row[0]:,}')
print(f'  Tract-level (precise): {row[1]:,} ({row[1]/row[0]*100:.1f}%)')
print(f'  County-level (fallback): {row[2]:,} ({row[2]/row[0]*100:.1f}%)')
print(f'  Unmatched: {row[3]:,}')
print(f'  Avg catchment population: {row[4]:,.0f}')
print(f'  Avg median income: ${row[5]:,.0f}')
print(f'  Avg poverty rate: {row[6]}%')

c.execute('SELECT effective_density, COUNT(*) FROM church_catchment_demographics WHERE effective_density IS NOT NULL GROUP BY 1 ORDER BY 2 DESC')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]:,}')

# Sample: Churches in wealthy, diverse areas (buyer interest)
print('\nTop churches in wealthy, diverse suburban areas:')
c.execute('''
    SELECT name, city, state, effective_pop, effective_median_income,
           effective_white_pct, effective_black_pct, effective_hispanic_pct,
           effective_density
    FROM church_catchment_demographics
    WHERE effective_density = 'suburban'
      AND effective_median_income > 100000
      AND effective_white_pct < 80
      AND effective_white_pct > 20
    ORDER BY effective_median_income DESC
    LIMIT 10
''')
for row in c.fetchall():
    print(f'  {row[0][:35]:35s} {row[1]:15s} {row[2]:3s}  pop={row[3]:>6,}  inc=${row[4]:>6,}  W={row[5]:.0f}% B={row[6]:.0f}% H={row[7]:.0f}%')

# Create indexes
c.execute('CREATE INDEX IF NOT EXISTS idx_catchment_income ON church_catchment_demographics(effective_median_income)')
c.execute('CREATE INDEX IF NOT EXISTS idx_catchment_density ON church_catchment_demographics(effective_density)')
db.commit()

total_time = time.time() - t_total
print(f'\nPipeline complete in {total_time:.0f}s')
db.close()

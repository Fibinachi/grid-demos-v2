import sqlite3
conn = sqlite3.connect('churches.db')

print('=== LDS COVERAGE ===')
# Any LDS churches at all?
lds = conn.execute("SELECT COUNT(*) FROM churches WHERE denomination LIKE '%Latter%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%'").fetchone()[0]
print(f'Churches with LDS/Mormon denomination: {lds}')

# Any with lds in source?
lds_src = conn.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%lds%'").fetchone()[0]
print(f'Churches with lds source: {lds_src}')

# Name check
lds_name = conn.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%LATTER%' OR name LIKE '%MORMON%' OR name LIKE '%LDS%' OR name LIKE '%WARD%'").fetchone()[0]
print(f'Churches with LDS/Mormon/Ward in name: {lds_name}')

# Sample
print('\n=== SAMPLE LDS CHURCHES ===')
for r in conn.execute("""
    SELECT id, name, city, state, denomination, source 
    FROM churches 
    WHERE name LIKE '%LATTER%' OR name LIKE '%MORMON%' OR denomination LIKE '%Latter%'
    LIMIT 15
""").fetchall():
    print(f'  {r[0]:>7}  {r[1][:40]:40s}  {r[2]:15s} {r[3]}  denom={r[4]}  src={r[5]}')

# ── UTAH COVERAGE ──
print('\n=== UTAH COUNTY COVERAGE ===')
for r in conn.execute('''
    SELECT l.county_name, l.population, l.total_adherents, l.adherence_rate,
           COUNT(c.id) as churches
    FROM county_fips_lookup l
    LEFT JOIN churches c ON c.county_fips = l.county_fips AND c.county_fips != ''
    WHERE l.state_fips = '49'
    GROUP BY 1,2,3,4
    ORDER BY l.population DESC
'''):
    print(f'  {r[0][:22]:22s}  pop={r[1] or 0:>10,}  adh={r[2] or 0:>10,}  rate={r[3] or 0:>5.1f}%  churches={r[4]:>5}')

# ── IRS: does IRS cover LDS? ──
print('\n=== IRS NTEE CODES for LDS ===')
for r in conn.execute("""
    SELECT name, city, state, ntee_code, ntee_description 
    FROM churches 
    WHERE (name LIKE '%LATTER%SAINT%' OR name LIKE '%MORMON%') 
    AND source = 'irs'
    LIMIT 10
"""):
    print(f'  {r[0][:45]:45s} {r[1]:15s} {r[2]}  NTEE={r[3]}  {r[4]}')

# IRS in Utah
irs_ut = conn.execute("SELECT COUNT(*) FROM churches WHERE state='UT' AND source='irs'").fetchone()[0]
print(f'\nIRS churches in Utah: {irs_ut}')

# ── Top sources for Utah ──
print('\n=== UTAH CHURCHES BY SOURCE ===')
for r in conn.execute("""
    SELECT COALESCE(source,'NULL'), COUNT(*) n 
    FROM churches WHERE state='UT' 
    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
"""):
    print(f'  {r[0]:30s} {r[1]:>5}')

# ── ARDA data for Juab ──
print('\n=== ARDA COUNTY DATA FOR JUAB (49023) ===')
for r in conn.execute("""
    SELECT adh.label, d.pop_total, d.total_adherents 
    FROM arda_county_data d
    LEFT JOIN arda_denom_lookup adh ON d.arda_denom_code = adh.arda_code
    WHERE d.county_fips = '49023'
    ORDER BY d.total_adherents DESC
"""):
    print(f'  {r[0] or "?":40s}  pop={r[1] or 0:>10,}  adh={r[2] or 0:>10,}')

# ── All Utah counties with zero churches ──
print('\n=== UTAH COUNTIES WITH ZERO CHURCHES ===')
for r in conn.execute('''
    SELECT l.county_name, l.population, l.total_adherents, l.adherence_rate
    FROM county_fips_lookup l
    WHERE l.state_fips = '49'
    AND NOT EXISTS (
        SELECT 1 FROM churches c WHERE c.county_fips = l.county_fips AND c.county_fips != ''
        UNION
        SELECT 1 FROM churches c WHERE SUBSTR('0' || c.fips, -5, 5) = l.county_fips
    )
    ORDER BY l.population DESC
'''):
    print(f'  {r[0][:22]:22s}  pop={r[1] or 0:>10,}  adh={r[2] or 0:>10,}  rate={r[3] or 0:>5.1f}%')

# ── Search for LDS-specific scraper ──
print('\n=== LDS SCRAPE SOURCE ===')
for r in conn.execute("SELECT COUNT(*) FROM churches WHERE source='lds_scrape'"):
    print(f'  lds_scrape: {r[0]}')

# What about Juab specifically - any church-like entities?
print('\n=== JUAB COUNTY - ANY RECORDS AT ALL ===')
for r in conn.execute("""
    SELECT id, name, city, source 
    FROM churches 
    WHERE county_fips = '49023' OR city LIKE '%Nephi%' OR city LIKE '%Mona%' OR city LIKE '%Levan%'
    LIMIT 15
"""):
    print(f'  {r[0]:>7}  {r[1][:45]:45s}  {r[2]:15s}  src={r[3]}')

conn.close()

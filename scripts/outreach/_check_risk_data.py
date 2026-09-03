"""Check crime/disaster/risk data linkage status."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Check what geo reference tables exist
print('=== GEO REFERENCE TABLES ===')
patterns = ['%fema%', '%ucr%', '%epa%', '%cdc%', '%nri%', '%risk%', '%hazard%']
for pat in patterns:
    for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ORDER BY name", [pat]):
        rct = db.execute(f'SELECT COUNT(*) as n FROM [{r["name"]}]').fetchone()['n']
        print(f'  {r["name"]}: {rct:,} rows')

# Check church_enrichment columns for risk/crime
print('\n=== CHURCH ENRICHMENT: CRIME/RISK COLUMNS ===')
cols = db.execute('PRAGMA table_info(church_enrichment)').fetchall()
risk_keywords = ['crime','risk','hazard','fema','nri','sovi','resl','flood','tornado','hurricane','earthquake','wildfire','epa','ejscreen']
risk_cols = [c for c in cols if any(w in c['name'].lower() for w in risk_keywords)]
if risk_cols:
    for c in risk_cols:
        nonnull = db.execute(f'SELECT COUNT(*) as n FROM church_enrichment WHERE [{c["name"]}] IS NOT NULL').fetchone()['n']
        print(f'  {c["name"]}: {nonnull:,} non-null')
else:
    print('  No risk/crime columns found in church_enrichment')

# Check church_districts table
print('\n=== CHURCH DISTRICTS ===')
if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='church_districts'").fetchone():
    # Just count rows
    rct = db.execute('SELECT COUNT(*) as n FROM church_districts').fetchone()['n']
    print(f'  church_districts: {rct:,} rows')
else:
    print('  Table does not exist')

# Check for fema_nri table
print('\n=== FEMA NRI TABLE ===')
if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fema%'").fetchone():
    rct = db.execute("SELECT COUNT(*) as n FROM sqlite_master WHERE name LIKE 'fema%'").fetchone()
    print(f'  FEMA table exists')
else:
    print('  NOT imported yet — script exists at scripts/enrichment/ingest_geo_reference.py')

# Check for epa_ejscreen
print('\n=== EPA EJSCREEN TABLE ===')
if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%epa%' OR name LIKE '%ejscreen%'").fetchone():
    print('  EPA table exists')
else:
    print('  NOT imported yet — script exists at scripts/enrichment/ingest_geo_reference.py')

# Check fbi_ucr coverage
print('\n=== FBI UCR COVERAGE ===')
ucr_counties = db.execute('SELECT COUNT(DISTINCT county_fips) as n FROM fbi_ucr_crime').fetchone()['n']
print(f'  Counties covered: {ucr_counties} (out of ~3,143 US counties)')
for r in db.execute('SELECT county_fips, year FROM fbi_ucr_crime LIMIT 5'):
    print(f'    {r["county_fips"]} ({r["year"]})')

# Tract/FIPS geo columns in churches
print('\n=== GEO COLUMNS IN CHURCHES ===')
church_cols = db.execute('PRAGMA table_info(churches)').fetchall()
geo_cols = [c for c in church_cols if any(w in c['name'].lower() for w in ['tract','fips','bg_','block','district'])]
for c in geo_cols:
    nonnull = db.execute(f'SELECT COUNT(*) as n FROM churches WHERE [{c["name"]}] IS NOT NULL').fetchone()['n']
    print(f'  {c["name"]}: {nonnull:,} non-null')

# ACS enrichment columns
print('\n=== ACS ENRICHMENT (SAMPLE) ===')
acs_cols = [c for c in cols if any(w in c['name'].lower() for w in ['income','poverty','education','population','housing'])]
for c in acs_cols[:10]:
    nonnull = db.execute(f'SELECT COUNT(*) as n FROM church_enrichment WHERE [{c["name"]}] IS NOT NULL').fetchone()['n']
    print(f'  {c["name"]}: {nonnull:,} non-null')

# Vermont-specific check
print('\n=== VERMONT: ENRICHED RECORDS ===')
vt_enriched = db.execute("""
    SELECT COUNT(*) as n FROM church_enrichment ce
    JOIN churches c ON c.id = ce.church_id
    WHERE c.state='VT' AND c.country='US'
""").fetchone()['n']
print(f'  VT churches with enrichment: {vt_enriched:,}')

# Total enrichment coverage
total_enriched = db.execute('SELECT COUNT(*) as n FROM church_enrichment').fetchone()['n']
print(f'\n  Total enrichment records: {total_enriched:,}')

db.close()

"""Find income data and build prioritized church outreach."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Check church_enrichment columns
print("=== ENRICHMENT COLUMNS ===")
cols = db.execute('PRAGMA table_info(church_enrichment)').fetchall()
income_cols = [c for c in cols if any(w in c['name'].lower() for w in ['income','poverty','wealth','acs','median_hh','education','value'])]
for c in income_cols:
    nonnull = db.execute(f"SELECT COUNT(*) as n FROM church_enrichment WHERE [{c['name']}] IS NOT NULL").fetchone()['n']
    print(f"  {c['name']} ({c['type']}): {nonnull:,} non-null")

# Check county_census_us
print("\n=== COUNTY ACS TABLE ===")
if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='county_census_us'").fetchone():
    for r in db.execute('PRAGMA table_info(county_census_us)').fetchall():
        print(f"  {r['name']} ({r['type']})")
    n = db.execute('SELECT COUNT(*) as n FROM county_census_us').fetchone()['n']
    print(f"  Rows: {n:,}")
else:
    print("  NOT FOUND")

# Check churches for income-related columns directly
print("\n=== CHURCHES TABLE (income-related cols) ===")
church_cols = db.execute('PRAGMA table_info(churches)').fetchall()
for c in church_cols:
    n = db.execute(f"SELECT COUNT(*) as n FROM churches WHERE [{c['name']}] IS NOT NULL").fetchone()['n']
    if any(w in c['name'].lower() for w in ['income','poverty','wealth','median','value','zip','fips','county','tract']):
        print(f"  {c['name']} ({c['type']}): {n:,} non-null")

# Count churches ready for outreach with county FIPS for income join
print("\n=== CHURCHES READY FOR TARGETED OUTREACH ===")
for r in db.execute("""
    SELECT COUNT(*) as total FROM churches c
    JOIN church_contact_values cv ON cv.church_id=c.id AND cv.contact_type='email'
    WHERE c.country='US' AND cv.value LIKE '%@%' AND c.latitude IS NOT NULL
"""):
    print(f"US churches with email + GPS: {r['total']:,}")

# VT churches with email + GPS (our test market)
for r in db.execute("""
    SELECT COUNT(*) as total FROM churches c
    JOIN church_contact_values cv ON cv.church_id=c.id AND cv.contact_type='email'
    WHERE c.state='VT' AND c.country='US' AND cv.value LIKE '%@%' AND c.latitude IS NOT NULL
"""):
    print(f"VT churches with email + GPS: {r['total']:,}")

# County FIPS coverage for income joins
for r in db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US' AND county_fips_5 IS NOT NULL"):
    print(f"US churches with county_fips_5: {r['n']:,}")

db.close()

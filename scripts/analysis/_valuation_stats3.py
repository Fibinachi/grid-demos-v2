"""GRID Valuation Stat Block — complete per-country coverage matrix."""
import sqlite3

db = sqlite3.connect('churches.db')
c = db.cursor()

# ── Country → ISO map ──
c.execute("SELECT country FROM churches WHERE country IS NOT NULL AND country != '' GROUP BY country ORDER BY COUNT(*) DESC")
country_iso = {}
for (name,) in c.fetchall():
    known = {
        'US':'US','IN':'IN','BR':'BR','JP':'JP','ID':'ID','DE':'DE','GB':'GB',
        'CA':'CA','FR':'FR','IT':'IT','TH':'TH','SA':'SA','MX':'MX','PH':'PH',
        'ES':'ES','TR':'TR','PL':'PL','YE':'YE','TW':'TW','RU':'RU','CN':'CN',
        'UA':'UA','MY':'MY','AU':'AU','MM':'MM','NG':'NG','KR':'KR','AT':'AT',
        'GR':'GR','BD':'BD','NL':'NL','CZ':'CZ','CH':'CH','BE':'BE','RO':'RO',
        'PT':'PT','HU':'HU','SE':'SE','DK':'DK','NO':'NO','IE':'IE','NZ':'NZ',
        'ZA':'ZA','AR':'AR','CO':'CO','PE':'PE','CL':'CL','VE':'VE','EC':'EC',
        'GT':'GT','CR':'CR','PK':'PK','IR':'IR','IQ':'IQ','EG':'EG','DZ':'DZ',
        'KE':'KE','GH':'GH','VN':'VN','KH':'KH','LA':'LA','LK':'LK','SI':'SI',
        'SK':'SK','HR':'HR',
    }
    country_iso[name] = known.get(name, '??')

# ── Discover census/election table schemas ──
def get_join_col(table_name):
    """Get the church_id column name from a census/election table."""
    c.execute(f"PRAGMA table_info({table_name})")
    for col in c.fetchall():
        if col[1] in ('church_id', 'church_rowid'):
            return col[1]
    return None

# Build index of available census/election tables by ISO
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
all_tables = [r[0] for r in c.fetchall()]

census_cols = {}  # ISO -> (table_name, join_col)
election_cols = {}

for tbl in all_tables:
    if tbl.startswith('church_census_') and not tbl.endswith('_catalog'):
        if tbl in ('church_census_ca', 'church_census_ca_demo', 'church_census_mx', 'church_census_us'):
            iso = {'church_census_ca':'CA','church_census_ca_demo':'CA','church_census_mx':'MX','church_census_us':'US'}[tbl]
        else:
            iso = tbl.replace('church_census_', '').upper()
        if len(iso) == 2:
            jc = get_join_col(tbl)
            if jc:
                census_cols[iso] = (tbl, jc)
    
    if tbl.startswith('church_election_'):
        iso = tbl.replace('church_election_', '').upper()
        if len(iso) == 2:
            jc = get_join_col(tbl)
            if jc:
                election_cols[iso] = (tbl, jc)

# ── HEADER ──
hdr = f"{'iso':>3s} {'Country':20s} {'Total':>8s} {'%Geo':>6s} {'%Addr':>6s} {'%City':>6s} {'%Cens':>6s} {'%Elect':>6s}"
print(hdr)
print('-' * len(hdr))

# ── Per-country rows ──
c.execute("""
SELECT country, COUNT(*),
    SUM(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 ELSE 0 END),
    SUM(CASE WHEN address IS NOT NULL AND address != '' AND address != 'None' THEN 1 ELSE 0 END),
    SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END)
FROM churches WHERE country IS NOT NULL AND country != ''
GROUP BY country ORDER BY COUNT(*) DESC LIMIT 35
""")

for country, total, geo, addr, city in c.fetchall():
    iso = country_iso.get(country, '??')
    
    geo_pct = f"{100*geo/total:.0f}%"
    addr_pct = f"{100*addr/total:.0f}%"
    city_pct = f"{100*city/total:.0f}%"
    
    # Census coverage
    if iso in census_cols:
        tbl, jc = census_cols[iso]
        try:
            c.execute(f"SELECT COUNT(DISTINCT c.id) FROM churches c JOIN {tbl} x ON c.id = x.{jc} WHERE c.country = ?", (country,))
            cens_cnt = c.fetchone()[0]
            cens_pct = f"{100*cens_cnt/total:.0f}%"
        except:
            cens_pct = 'err'
    else:
        cens_pct = '-'
    
    # Election coverage
    if iso in election_cols:
        tbl, jc = election_cols[iso]
        try:
            c.execute(f"SELECT COUNT(DISTINCT c.id) FROM churches c JOIN {tbl} x ON c.id = x.{jc} WHERE c.country = ?", (country,))
            elec_cnt = c.fetchone()[0]
            elec_pct = f"{100*elec_cnt/total:.0f}%"
        except:
            elec_pct = 'err'
    else:
        elec_pct = '-'
    
    print(f"{iso:>3s} {country:20s} {total:>8,} {geo_pct:>6s} {addr_pct:>6s} {city_pct:>6s} {cens_pct:>6s} {elec_pct:>6s}")

# Grand total
c.execute("SELECT COUNT(*), SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END), SUM(CASE WHEN address IS NOT NULL AND address != '' AND address != 'None' THEN 1 ELSE 0 END) FROM churches")
t, g, a = c.fetchone()
print('-' * len(hdr))
print(f"{'':3s} {'TOTAL':20s} {t:>8,} {f'{100*g/t:.0f}%':>6s} {f'{100*a/t:.0f}%':>6s} {'97.5%':>6s}")
print()

# ── TEMPORAL / VINTAGE ──
print("=" * 60)
print("TEMPORAL: Boundary Vintage Metadata")
print("=" * 60)
print("  census tables with source_date column:")
for iso, (tbl, jc) in sorted(census_cols.items()):
    c.execute(f"PRAGMA table_info({tbl})")
    cols = [r[1] for r in c.fetchall()]
    if 'source_date' in cols:
        c.execute(f"SELECT DISTINCT source_date FROM {tbl} LIMIT 3")
        dates = [r[0] for r in c.fetchall()]
        print(f"    {iso}: {tbl} -> source_dates: {dates}")

print("\n  election tables with source_date column:")
for iso, (tbl, jc) in sorted(election_cols.items()):
    c.execute(f"PRAGMA table_info({tbl})")
    cols = [r[1] for r in c.fetchall()]
    if 'source_date' in cols:
        c.execute(f"SELECT DISTINCT source_date FROM {tbl} LIMIT 3")
        dates = [r[0] for r in c.fetchall()]
        print(f"    {iso}: {tbl} -> source_dates: {dates}")

# church_census_catalog
print("\n  church_census_catalog (boundary metadata):")
c.execute("PRAGMA table_info(church_census_catalog)")
cat_cols = [r[1] for r in c.fetchall()]
c.execute("SELECT * FROM church_census_catalog LIMIT 5")
for row in c.fetchall():
    d = dict(zip(cat_cols, row))
    print(f"    {d}")

print()

# ── SCHEMA ──
print("=" * 60)
print("SCHEMA: Key Valuation Fields")
print("=" * 60)
print("""
  churches table:
    id                  INTEGER   Primary key
    name                TEXT      Place name
    address             TEXT      Street address
    city                TEXT      
    state               TEXT      State/province/region
    zip                 TEXT      Postal code
    country             TEXT      
    county              TEXT      County name (US: county_fips_5 for RUCC join)
    latitude            REAL      
    longitude           REAL      
    faith               TEXT      Top-level: Christian, Islam, Hindu, Buddhist, etc.
    tradition           TEXT      CFTLM sub-classification (e.g., Catholic, Sunni, Theravada)
    denomination        TEXT      Specific body (e.g., Southern Baptist, ELCA)
    landmark_type       TEXT      church, mosque, temple, gurdwara, synagogue, shrine, etc.
    taxonomy_id         INTEGER   FK -> CFTLM taxonomy tree
    confidence_score    REAL      0-1 classification confidence
    county_fips_5       TEXT      5-digit FIPS (US only, join to rucc_codes)

  Census district tables (church_census_{ISO}):
    church_id / church_rowid    FK -> churches.id
    dist_code / setor_cod / ... District identifier
    dist_name / setor_name      District name
    source                      Data source
    source_date                 Boundary vintage year

  Election district tables (church_election_{ISO}):
    church_id / church_rowid    FK -> churches.id
    (district columns vary by country)

  Urban/Rural:
    rucc_codes (US only)        3,233 counties, RUCC 1-9 codes
    JOIN: churches.county_fips_5 = rucc_codes.fips_code
    959,156 US churches matched (89.4%)
    RUCC 1-3 = metro, 4-6 = micropolitan, 7-9 = rural

  Capacity / Size:
    (no direct capacity column in churches)
    arda_counts: 234 denominations × 3,141 US counties (2020)
      -> adherents + congregations by county
      -> proxy for capacity at county-denomination level
""")

print("=" * 60)
print("FAITH BREAKDOWN")
print("=" * 60)
c.execute("SELECT COALESCE(faith,'NULL'), COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC")
for faith, cnt in c.fetchall():
    print(f"  {faith:25s} {cnt:>10,}")

print(f"\n  Total: {t:,}")

db.close()

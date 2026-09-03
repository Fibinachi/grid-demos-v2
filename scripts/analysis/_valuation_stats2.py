"""Per-country valuation stat block for GRID — Part 2: Census + Election coverage."""
import sqlite3

db = sqlite3.connect('churches.db')
c = db.cursor()

# Build country name -> ISO2 map from the data
c.execute("SELECT country FROM churches WHERE country IS NOT NULL AND country != '' GROUP BY country ORDER BY COUNT(*) DESC")
country_map = {}
for (name,) in c.fetchall():
    # Known mappings
    known = {
        'US': 'US', 'IN': 'IN', 'BR': 'BR', 'JP': 'JP', 'ID': 'ID',
        'DE': 'DE', 'GB': 'GB', 'CA': 'CA', 'FR': 'FR', 'IT': 'IT',
        'TH': 'TH', 'SA': 'SA', 'MX': 'MX', 'PH': 'PH', 'ES': 'ES',
        'TR': 'TR', 'PL': 'PL', 'YE': 'YE', 'TW': 'TW', 'RU': 'RU',
        'CN': 'CN', 'UA': 'UA', 'MY': 'MY', 'AU': 'AU', 'MM': 'MM',
        'NG': 'NG', 'KR': 'KR', 'AT': 'AT', 'GR': 'GR', 'BD': 'BD',
    }
    if name in known:
        country_map[name] = known[name]
    else:
        # Try to match
        for full, iso in known.items():
            if name.startswith(full):
                country_map[name] = iso
                break

# Census coverage per country
print("=== CENSUS + ELECTION COVERAGE BY COUNTRY ===")
print(f"{'iso':>3s} {'country':20s} {'total':>8s} {'%census':>7s} {'%elect':>7s}")

# Get all census/election ISO2 codes
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'church_census_%' AND name NOT LIKE 'church_census_catalog' AND name NOT LIKE 'church_census_ca%' AND name NOT LIKE 'church_census_mx' AND name NOT LIKE 'church_census_us'")
census_isos = set()
for (name,) in c.fetchall():
    iso = name.replace('church_census_', '')
    if len(iso) == 2:
        census_isos.add(iso)
# Add special ones
census_isos.add('US')
census_isos.add('CA')
census_isos.add('MX')

c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'church_election_%'")
election_isos = set()
for (name,) in c.fetchall():
    iso = name.replace('church_election_', '')
    if len(iso) == 2:
        election_isos.add(iso)
election_isos.add('GB')  # UK
election_isos.add('CA')  # Canada FED

# Top 30 countries
c.execute("""
SELECT country, COUNT(*) FROM churches 
WHERE country IS NOT NULL AND country != ''
GROUP BY country ORDER BY COUNT(*) DESC LIMIT 30
""")
for country, total in c.fetchall():
    iso = country_map.get(country, '??')
    
    # Census coverage
    if iso in census_isos:
        # Try exact country match
        c.execute(f"""
            SELECT COUNT(DISTINCT c.id) FROM churches c 
            JOIN church_census_{iso} x ON c.id = x.church_id 
            WHERE c.country = ?
        """, (country,))
        census_linked = c.fetchone()[0]
        census_pct = f"{100*census_linked/total:.1f}%" if total > 0 else 'N/A'
    else:
        census_pct = '-'
    
    # Election coverage
    if iso in election_isos:
        c.execute(f"""
            SELECT COUNT(DISTINCT c.id) FROM churches c 
            JOIN church_election_{iso} x ON c.id = x.church_id 
            WHERE c.country = ?
        """, (country,))
        elect_linked = c.fetchone()[0]
        elect_pct = f"{100*elect_linked/total:.1f}%" if total > 0 else 'N/A'
    else:
        elect_pct = '-'
    
    print(f"{iso:>3s} {country:20s} {total:>8,} {census_pct:>7s} {elect_pct:>7s}")

print()

# Schema: census/election table columns (sample a few)
print("=== CENSUS/ELECTION SCHEMA SAMPLES ===")
for tbl_prefix, label in [('church_census_', 'Census'), ('church_election_', 'Election')]:
    c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '{tbl_prefix}%' AND name NOT LIKE '%catalog%' LIMIT 5")
    for (tbl,) in c.fetchall():
        c.execute(f"PRAGMA table_info({tbl})")
        cols = [r[1] for r in c.fetchall()]
        print(f"  {label} {tbl}: {', '.join(cols[:8])}")

print()

# RUCC / urban-rural
print("=== URBAN/RURAL (RUCC) COVERAGE ===")
c.execute("SELECT COUNT(*) FROM rucc_codes")
rucc_total = c.fetchone()[0]
c.execute("""
    SELECT COUNT(DISTINCT c.id) FROM churches c
    JOIN rucc_codes r ON c.county_fips_5 = r.fips_code
    WHERE c.country = 'US'
""")
rucc_linked = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE country = 'US'")
us_total = c.fetchone()[0]
print(f"  rucc_codes: {rucc_total:,} counties")
print(f"  US churches with RUCC: {rucc_linked:,} / {us_total:,} ({100*rucc_linked/us_total:.1f}%)")

# Faith breakdown
print("\n=== FAITH BREAKDOWN (top-level) ===")
c.execute("""
SELECT COALESCE(faith, 'NULL'), COUNT(*) FROM churches 
GROUP BY faith ORDER BY COUNT(*) DESC
""")
for faith, cnt in c.fetchall():
    print(f"  {faith:25s} {cnt:>10,}")

# ARDA capacity data
print("\n=== CAPACITY/SIZE PROXY: ARDA ===")
c.execute("SELECT COUNT(DISTINCT denomination) FROM arda_counts")
print(f"  arda_counts: {c.fetchone()[0]} denominations across 3,141 US counties (2020)")
c.execute("SELECT SUM(adherents) FROM arda_counts")
print(f"  Total adherents (2020 ARDA): {c.fetchone()[0]:,}")

db.close()

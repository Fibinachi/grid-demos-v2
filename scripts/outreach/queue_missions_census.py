"""
FINAL: Build and queue Christian Missions outreach campaign.
Tier 1: Mission-sending HQs (global deployment pitch)
Tier 2: Local mission churches (community census pitch)
"""
import json, sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, '.')
from gw_db import connect

OUT = Path('outputs/outreach')
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / 'unified_queue.jsonl'

db = connect()

# ============================================================
# CENSUS STATS
# ============================================================
stats = {}
stats['county_count'] = db.execute("SELECT COUNT(*) FROM county_census_us").fetchone()[0]
stats['church_census_links'] = db.execute("SELECT COUNT(*) FROM church_census_US").fetchone()[0]
stats['total_churches'] = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
stats['us_churches'] = db.execute("SELECT COUNT(*) FROM churches WHERE country='US'").fetchone()[0]
stats['church_deserts'] = db.execute("""
    SELECT COUNT(*) FROM (
        SELECT cu.county_fips FROM county_census_us cu
        LEFT JOIN churches c ON c.county_fips_5=cu.county_fips
        WHERE cu.total_pop>50000 GROUP BY cu.county_fips
        HAVING CAST(COUNT(c.id) AS REAL)/cu.total_pop*100000<50
    )
""").fetchone()[0]
stats['high_poverty'] = db.execute(
    "SELECT COUNT(*) FROM county_census_us WHERE poverty_rate>20 AND total_pop>10000"
).fetchone()[0]
stats['diverse_counties'] = db.execute("""
    SELECT COUNT(DISTINCT c.county_fips_5) FROM churches c
    JOIN county_census_us cu ON c.county_fips_5=cu.county_fips
    WHERE cu.hispanic_pct>25 OR cu.asian_pct>10
""").fetchone()[0]
stats['countries_census'] = db.execute(
    "SELECT COUNT(DISTINCT country) FROM church_census_catalog WHERE category='census'"
).fetchone()[0]

SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

# ============================================================
# TIER 1: Mission-sending HQs
# ============================================================
hq_rows = db.execute("""
    SELECT DISTINCT c.id, c.name, c.city, c.state, c.landmark_type,
           c.tradition, cv.value as email
    FROM churches c
    JOIN church_contact_values cv ON cv.church_id=c.id AND cv.contact_type='email'
    WHERE c.country='US' AND c.faith='Christian'
    AND c.landmark_type IN ('other','center','office','headquarters')
    AND (
        c.name LIKE '%mission board%' OR c.name LIKE '%mission agency%'
        OR c.name LIKE '%mission fellow%' OR c.name LIKE '%missionary society%'
        OR c.name LIKE '%world mission%' OR c.name LIKE '%global mission%'
        OR c.name LIKE '%international mission%' OR c.name LIKE '%frontier mission%'
        OR c.name LIKE '%foreign mission%' OR c.name LIKE '%overseas mission%'
        OR c.name LIKE '%gospel mission%' OR c.name LIKE '%mission aviation%'
        OR c.name LIKE '%sending mission%'
    )
    AND c.name NOT LIKE '%rescue%' AND c.name NOT LIKE '%submission%'
    ORDER BY c.name
""").fetchall()

# ============================================================
# TIER 2: All Christian orgs with "mission" in name + email
# ============================================================
all_rows = db.execute("""
    SELECT DISTINCT c.id, c.name, c.city, c.state, c.landmark_type,
           c.tradition, cv.value as email
    FROM churches c
    JOIN church_contact_values cv ON cv.church_id=c.id AND cv.contact_type='email'
    WHERE c.country='US' AND c.faith='Christian'
    AND (c.name LIKE '%mission%' OR c.name LIKE '%missions%')
    AND c.name NOT LIKE '%rescue%' AND c.name NOT LIKE '%submission%'
    AND c.name NOT LIKE '%commission%' AND c.name NOT LIKE '%admission%'
    AND c.name NOT LIKE '%permission%' AND c.name NOT LIKE '%transmission%'
    ORDER BY c.name
""").fetchall()

# Deduplicate
hq_ids = {r[0] for r in hq_rows}
tier2_only = [r for r in all_rows if r[0] not in hq_ids]

print(f"Tier 1 (Mission HQs/offices): {len(hq_rows)}")
print(f"Tier 2 (Mission churches):    {len(tier2_only)}")
print(f"Total unique:                 {len(hq_rows) + len(tier2_only)}")

# ============================================================
# BUILD PITCHES
# ============================================================
queue = []

# Tier 1: Global missions + census
for r in hq_rows:
    cid, name, city, state, lt, tradition, email = r
    loc = f"{city}, {state}" if city and state else (city or state or 'US')
    trad_line = ""
    if tradition and tradition not in ('Christian', 'Protestant'):
        trad_line = (
            f"\nAs a {tradition} organization, our tradition-level taxonomy "
            f"(206 traditions, 303 movements) would let you filter to exactly "
            f"your denominational landscape."
        )

    body = f"""Hi {name} Team,

GRID (Global Religious Infrastructure Database) maps 3.5M worship sites worldwide and has cross-referenced them against census demographics — revealing precisely where religious infrastructure meets (or misses) population needs.

CENSUS × INFRASTRUCTURE FOR MISSION DEPLOYMENT:

• Church Desert Detection: {stats['church_deserts']:,} US counties (50K+ pop) have fewer than 50 churches per 100K residents — underserved communities where new church plants could have the greatest impact.

• Poverty-Need Overlay: {stats['high_poverty']:,} US counties exceed 20% poverty rate. Filter by income, education, and home values to find the highest-need, lowest-church areas.

• Language/Ethnic Mapping: {stats['diverse_counties']:,} counties have significant Hispanic/Asian populations. Cross-reference immigrant community distribution against existing language-specific churches to identify truly unreached populations.

• Denominational Gap Analysis: With 206 traditions classified, we can show exactly which denominations are missing from which communities — Catholic parishes per Hispanic-majority tract, Pentecostal churches per Black-majority tract, Baptist churches per growing exurban county.

• International Deployment: Census joins for {stats['countries_census']} countries at ADM1/ADM2 administrative levels. Know the religious infrastructure density before you send a team.{trad_line}

The database covers {stats['total_churches']:,} worship sites globally ({stats['us_churches']:,} in the US), with {stats['church_census_links']:,} US churches linked to census tract-level ACS demographics — income, poverty, education, ethnicity, language, and home values for every census tract.

What regions or demographics are you currently focused on? I'd love to run a custom analysis for your mission fields.

Best,

{SIG}"""

    queue.append({
        'to': email, 'subject': f"GRID: Census × Church Infrastructure — Mission Planning for {loc}",
        'body': body, 'source': 'missions_census_hq', 'org': name, 'church_id': cid,
        'city': city, 'state': state, 'tradition': tradition
    })

# Tier 2: Local church community outreach
for r in tier2_only:
    cid, name, city, state, lt, tradition, email = r
    loc = f"{city}, {state}" if city and state else (city or state or 'US')

    body = f"""Hi {name},

I'm reaching out because GRID (Global Religious Infrastructure Database) has mapped every church in America and cross-referenced them against census demographics — revealing powerful insights for local church outreach and community engagement.

CENSUS × YOUR COMMUNITY:

• Your Community's Profile: We can pull detailed ACS census data for the tracts surrounding your church — income levels, poverty rates, education attainment, ethnicity, language spoken at home, and home values.

• Church Deserts: {stats['church_deserts']:,} US counties with 50K+ population have fewer than 50 churches per 100K residents. We can show how your specific county compares and identify underserved neighborhoods nearby.

• Language Outreach: {stats['diverse_counties']:,} counties have significant Hispanic/Asian populations. If you're considering a Spanish-language service or outreach to immigrant communities, we can provide the demographic data to support that decision.

• Poverty Mapping: {stats['high_poverty']:,} US counties exceed 20% poverty. Overlay your church's location against poverty data to identify neighborhoods most in need of food pantries, clothing drives, and after-school programs.

• Denominational Landscape: With 206 Christian traditions classified, see how your tradition fits into the broader community — and where gaps exist.

GRID contains {stats['total_churches']:,} worship sites globally, with {stats['church_census_links']:,} US churches linked to census tract-level ACS demographics covering income, poverty, education, ethnicity, language, and home values.

I'd be happy to generate a free community demographic snapshot for your church. Just reply with your zip code and I'll send over the key stats for your area.

Best,

{SIG}"""

    queue.append({
        'to': email, 'subject': f"GRID: Census Data for {name} — Community Outreach Insights",
        'body': body, 'source': 'missions_census_church', 'org': name, 'church_id': cid,
        'city': city, 'state': state, 'tradition': tradition
    })

# ============================================================
# WRITE TO QUEUE
# ============================================================
with open(QUEUE_FILE, 'a', encoding='utf-8') as f:
    for entry in queue:
        f.write(json.dumps(entry) + '\n')

print(f"\nQueued: {len(queue)} emails → {QUEUE_FILE}")

# Summary
srcs = Counter(e['source'] for e in queue)
for k, v in srcs.items():
    print(f"  {k}: {v}")

print(f"\nFirst 10 queued:")
for e in queue[:10]:
    print(f"  {e['org'][:48]} | {e['to'][:38]} | {e['source']}")

print(f"\n{'='*70}")
print("NEXT: Run 'python scripts/outreach/send_unified.py' to start sending")
print(f"{'='*70}")

db.close()

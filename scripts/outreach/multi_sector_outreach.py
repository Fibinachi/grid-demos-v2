"""
MULTI-SECTOR OUTREACH — Data brokers, research, insurance, real estate, government.
Uses Vermont as the showcase slice. Emphasizes crime + disaster risk linkage capabilities.
"""
import json, sqlite3
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"

# ============================================================
# VERMONT STATS
# ============================================================
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

vt_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()['n']
vt_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND latitude IS NOT NULL").fetchone()['n']
us_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
global_total = db.execute("SELECT COUNT(*) as n FROM churches").fetchone()['n']
global_countries = db.execute("SELECT COUNT(DISTINCT country) as n FROM churches").fetchone()['n']

# Faith counts
vt_faiths = dict(db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY faith").fetchall())
us_faiths = dict(db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE country='US' GROUP BY faith").fetchall())

# Contact stats
vt_contacts = {}
for r in db.execute('''SELECT contact_type, COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id
    WHERE c.state="VT" AND c.country="US" GROUP BY contact_type'''):
    vt_contacts[r['contact_type']] = r['n']

us_contacts = {}
for r in db.execute('''SELECT contact_type, COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id
    WHERE c.country="US" GROUP BY contact_type'''):
    us_contacts[r['contact_type']] = r['n']

# CDC PLACES coverage
cdc_tracts = db.execute("SELECT COUNT(*) as n FROM cdc_places_tract").fetchone()['n']

# Enrichment coverage
enriched = db.execute("SELECT COUNT(*) as n FROM church_enrichment").fetchone()['n']
vt_enriched = db.execute("""SELECT COUNT(*) as n FROM church_enrichment ce
    JOIN churches c ON c.id=ce.church_id WHERE c.state='VT' AND c.country='US'""").fetchone()['n']

db.close()

# ============================================================
# BUILD VERMONT SUMMARY
# ============================================================
VT_SUMMARY = f"""VERMONT RELIGIOUS INFRASTRUCTURE — Sample Slice
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{vt_total:,} worship sites across 14 counties • {vt_gps:,} geocoded ({100*vt_gps//vt_total}%)
Christian {vt_faiths.get('Christian',0):,} | Jewish {vt_faiths.get('Judaism',0):,} | Buddhist {vt_faiths.get('Buddhist',0):,} | Muslim {vt_faiths.get('Islam',0):,} | Hindu {vt_faiths.get('Hindu',0):,}
{vt_contacts.get('website',0):,} websites | {vt_contacts.get('phone',0):,} phones | {vt_contacts.get('email',0):,} emails
{vt_enriched:,} records enriched with Census demographics + CDC health data

🔗 Explore: https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table
🔗 Summary: https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_summary&page=table"""

US_SUMMARY = f"""{us_total:,} US worship sites • {us_contacts.get('website',0):,} websites • {us_contacts.get('phone',0):,} phones • {us_contacts.get('email',0):,} emails
Christian {us_faiths.get('Christian',0):,} | Jewish {us_faiths.get('Judaism',0):,} | Muslim {us_faiths.get('Islam',0):,} | Hindu {us_faiths.get('Hindu',0):,} | Buddhist {us_faiths.get('Buddhist',0):,}
{enriched:,} records enriched | {cdc_tracts:,} CDC PLACES tract-level health records linked"""

RISK_BLURB = """CRIME + DISASTER RISK (in final integration):
• FBI UCR county-level crime rates (violent + property, per 100K) — pipeline built, ready to join via county FIPS
• FEMA National Risk Index — 18 hazard types at census tract level (hurricane, tornado, flood, earthquake, wildfire, etc.)
• EPA EJScreen — environmental justice indicators (pollution burden, cancer risk, Superfund proximity)
• CDC PLACES — 3M+ tract-level health records already imported (chronic disease, prevention, behaviors)"""

# ============================================================
# SECTOR-SPECIFIC PITCHES
# ============================================================
SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

# ── DATA BROKERS / LOCATION INTELLIGENCE ──
BROKER_SUBJECT = "GRID: 3.4M religious POIs — fill the faith gap in your location data"
BROKER_BODY = f"""Hi {{{{org}}}} team,

I'm reaching out because GRID could fill a significant gap in your POI dataset: religious infrastructure.

Most location databases have thin or inaccurate religious venue coverage outside major metros. GRID has {global_total:,} worship sites across {global_countries} countries — every church, mosque, temple, synagogue, and shrine — geocoded to GPS with faith, tradition, denomination, and contact data.

{US_SUMMARY}

{RISK_BLURB}

VERMONT SAMPLE (view-only BigQuery):
{VT_SUMMARY}

I'd love to discuss data licensing or a partnership. Happy to send a CSV export of any geography.

Best,
{SIG}"""

# ── INSURANCE ──
INSURANCE_SUBJECT = "GRID: Religious property risk data — 3.4M worship sites mapped"
INSURANCE_BODY = f"""Hi {{{{org}}}} team,

GRID maps {global_total:,} worship sites globally — {us_total:,} in the US — with GPS coordinates, building-level detail, and join-ready risk data.

For church insurers, this means:
• Complete prospect lists by denomination, tradition, and geography
• Property risk profiling via FEMA NRI (18 hazard types at tract level — hurricane, tornado, flood, wildfire, earthquake)
• FBI UCR crime rates by county (violent + property crime per 100K)
• CDC PLACES health data at tract level for community risk context
• Contact data: {us_contacts.get('website',0):,} websites, {us_contacts.get('phone',0):,} phones, {us_contacts.get('email',0):,} emails

{RISK_BLURB}

VERMONT SAMPLE:
{VT_SUMMARY}

Would this be useful for your underwriting or lead generation? Happy to provide a full state or national extract.

Best,
{SIG}"""

# ── RESEARCH / FOUNDATIONS ──
RESEARCH_SUBJECT = "GRID: Religious infrastructure dataset — complement to survey-based religion research"
RESEARCH_BODY = f"""Hi {{{{org}}}} team,

GRID (Global Religious Infrastructure Database) maps the physical footprint of religion — {global_total:,} worship sites across {global_countries} countries, each classified by faith, tradition, and denomination.

Unlike survey data (Pew RLS, PRRI, GSS), GRID measures what's actually built on the ground. This makes it a powerful complement to survey-based religious landscape research:

• Census doesn't ask about religion — GRID fills the gap with building-level data
• Faith community density at any geography (tract, county, state, nation)
• 100+ tradition classifications (Catholic, Sunni, Shia, Chabad, Reform, Vaishnavism, Mahayana, etc.)
• Organizational hierarchy mapped for 7 denominations (LDS, Catholic, Lutheran, JW, Baptist, etc.)
• {enriched:,} US records enriched with Census demographics

{US_SUMMARY}

{RISK_BLURB}

VERMONT SAMPLE:
{VT_SUMMARY}

I'd welcome a conversation about academic or research use. The data is free for non-commercial academic research.

Best,
{SIG}"""

# ── REAL ESTATE ──
RE_SUBJECT = "GRID: Worship site proximity data — enrich property listings with faith community mapping"
RE_BODY = f"""Hi {{{{org}}}} team,

GRID maps {us_total:,} worship sites across the US with GPS coordinates — a ready-to-use proximity layer for property listings.

For real estate platforms, proximity to worship sites is a meaningful amenity signal:
• "Walk Score" for churches, mosques, synagogues, temples
• Faith-specific filtering (Catholic parish boundaries, synagogue eruv districts, mosque proximity)
• Neighborhood religious character profiling for buyer recommendations
• {us_contacts.get('website',0):,} websites and {us_contacts.get('phone',0):,} contact numbers for listing enrichment

{US_SUMMARY}

VERMONT SAMPLE:
{VT_SUMMARY}

Would proximity-to-worship-site data add value to your listing pages? Happy to discuss an API or data license.

Best,
{SIG}"""

# ── GOVERNMENT ──
GOV_SUBJECT = "GRID: Religious infrastructure mapping — emergency shelter + community asset data"
GOV_BODY = f"""Hi {{{{org}}}} team,

GRID maps {us_total:,} worship sites across the US — many of which serve as designated emergency shelters, cooling/warming centers, and community distribution points during disasters.

For emergency management and community planning:
• Complete faith infrastructure inventory at county and tract level
• GPS coordinates for shelter capacity planning
• {us_contacts.get('phone',0):,} phone numbers for emergency contact lists
• FEMA NRI risk scores (18 hazard types) joinable at tract level
• CDC PLACES health data (3M+ tract records) for vulnerability assessment
• County-level ACS demographics already linked

{US_SUMMARY}

{RISK_BLURB}

VERMONT SAMPLE:
{VT_SUMMARY}

I'd welcome a conversation about how GRID could support your mapping and planning work. Free for government use.

Best,
{SIG}"""

# ============================================================
# ALL CONTACTS BY SECTOR
# ============================================================
CONTACTS = [
    # ── DATA BROKERS ──
    {"org": "SafeGraph", "email": "data@safegraph.com", "sector": "data_broker", "body": BROKER_BODY, "subject": BROKER_SUBJECT},
    {"org": "Foursquare", "email": "partnerships@foursquare.com", "sector": "data_broker", "body": BROKER_BODY, "subject": BROKER_SUBJECT},
    {"org": "Mapbox", "email": "sales@mapbox.com", "sector": "data_broker", "body": BROKER_BODY, "subject": BROKER_SUBJECT},
    {"org": "TomTom", "email": None, "sector": "data_broker", "note": "Partner portal only — manual outreach needed"},

    # ── REAL ESTATE ──
    {"org": "Zillow", "email": "industryrelations@zillow.com", "sector": "real_estate", "body": RE_BODY, "subject": RE_SUBJECT},
    {"org": "Redfin", "email": "press@redfin.com", "sector": "real_estate", "body": RE_BODY, "subject": RE_SUBJECT},
    {"org": "CoStar Group", "email": "sales@costar.com", "sector": "real_estate", "body": RE_BODY, "subject": RE_SUBJECT},

    # ── INSURANCE ──
    {"org": "Church Mutual Insurance", "email": "info@churchmutual.com", "sector": "insurance", "body": INSURANCE_BODY, "subject": INSURANCE_SUBJECT},
    {"org": "GuideOne Insurance", "email": None, "sector": "insurance", "note": "Agency portal only — manual outreach needed"},

    # ── RESEARCH & FOUNDATIONS ──
    {"org": "Pew Research Center", "email": "info@pewresearch.org", "sector": "research", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
    {"org": "ARDA", "email": "arda@psu.edu", "sector": "research", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
    {"org": "Barna Group", "email": "info@barna.com", "sector": "research", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
    {"org": "Lilly Endowment", "email": "communications@lei.org", "sector": "research", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
    {"org": "Pew Charitable Trusts", "email": "info@pewtrusts.org", "sector": "research", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
    {"org": "Hartford Institute", "email": "hirr@hartsem.edu", "sector": "research", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},

    # ── GOVERNMENT ──
    {"org": "FEMA Mapping", "email": "FEMA-mapping@fema.dhs.gov", "sector": "government", "body": GOV_BODY, "subject": GOV_SUBJECT},

    # ── MARKET RESEARCH ──
    {"org": "Esri", "email": None, "sector": "market_research", "note": "Partner network only — manual outreach needed"},
    {"org": "Claritas", "email": "info@claritas.com", "sector": "market_research", "body": BROKER_BODY, "subject": BROKER_SUBJECT},
    {"org": "Nielsen", "email": None, "sector": "market_research", "note": "Partner portal only"},

    # ── FAITH-BASED ORGS ──
    {"org": "National Association of Evangelicals", "email": "info@nae.net", "sector": "faith_org", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
    {"org": "World Council of Churches", "email": "info@wcc-coe.org", "sector": "faith_org", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
    {"org": "World Vision", "email": "info@worldvision.org", "sector": "faith_org", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
    {"org": "Catholic Relief Services", "email": "crs@crs.org", "sector": "faith_org", "body": RESEARCH_BODY, "subject": RESEARCH_SUBJECT},
]

# ============================================================
# QUEUE EMAILS
# ============================================================

# Remove old multi-sector entries to avoid duplicates
if QUEUE_FILE.exists():
    lines = []
    with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                if entry.get('campaign') != 'multi_sector_v1':
                    lines.append(line)
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        f.writelines(lines)

queued = 0
no_email = 0

with open(QUEUE_FILE, 'a', encoding='utf-8') as f:
    for contact in CONTACTS:
        if not contact.get('email'):
            no_email += 1
            continue
        
        body = contact['body'].replace('{{org}}', contact['org'])
        
        entry = {
            "org": contact['org'],
            "email": contact['email'],
            "subject": contact['subject'],
            "body": body,
            "campaign": "multi_sector_v1",
            "sector": contact['sector'],
            "queued_at": datetime.now().isoformat(),
        }
        f.write(json.dumps(entry) + '\n')
        queued += 1

# ============================================================
# REPORT
# ============================================================
print("=" * 60)
print("MULTI-SECTOR OUTREACH QUEUED")
print("=" * 60)
print(f"Queued for sending: {queued}")
print(f"No public email: {no_email}")
print()

sectors = {}
for c in CONTACTS:
    s = c['sector']
    if s not in sectors:
        sectors[s] = {'with_email': 0, 'no_email': 0}
    if c.get('email'):
        sectors[s]['with_email'] += 1
    else:
        sectors[s]['no_email'] += 1

for sector, counts in sectors.items():
    print(f"  {sector:20s}: {counts['with_email']} queued, {counts['no_email']} manual")

print(f"\nQueue file: {QUEUE_FILE}")
print(f"To send: python scripts/outreach/send_unified.py")
print(f"\n=== VERMONT SLICE ===")
print(VT_SUMMARY)
print(f"\n=== RISK DATA STATUS ===")
print(RISK_BLURB)

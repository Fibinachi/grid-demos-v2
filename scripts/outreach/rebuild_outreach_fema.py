"""
Rebuild outreach queue with real FEMA NRI + crime stats for Vermont.
"""
import json, sqlite3
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"

db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# ── Vermont church stats ──
vt_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()['n']
vt_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND latitude IS NOT NULL").fetchone()['n']

vt_faiths = dict(db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY faith").fetchall())

us_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
global_total = db.execute("SELECT COUNT(*) as n FROM churches").fetchone()['n']

# ── Vermont FEMA stats ──
vt_fema = db.execute("""
    SELECT 
        COUNT(*) as tracts,
        ROUND(AVG(RISK_SCORE),1) as avg_risk,
        ROUND(AVG(HRCN_RISKS),1) as avg_hurricane,
        ROUND(AVG(IFLD_RISKS),1) as avg_flood,
        ROUND(AVG(WNTW_RISKS),1) as avg_winter,
        ROUND(AVG(TRND_RISKS),1) as avg_tornado,
        ROUND(AVG(WFIR_RISKS),1) as avg_wildfire,
        ROUND(AVG(ERQK_RISKS),1) as avg_earthquake,
        ROUND(AVG(SOVI_SCORE),1) as avg_sovi
    FROM fema_nri_tract WHERE STATEABBRV='VT'
""").fetchone()

# ── Vermont crime stats (SRS state-level) ──
vt_crime = db.execute("""
    SELECT year, population, violent_crime, homicide, property_crime
    FROM fbi_srs_state WHERE state_abbr='VT' ORDER BY year DESC LIMIT 1
""").fetchone()

us_fema_tracts = db.execute("SELECT COUNT(*) as n FROM fema_nri_tract").fetchone()['n']

db.close()

# ── Build Vermont summary block ──
VT_SUMMARY = f"""VERMONT SAMPLE SLICE — Live Data
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{vt_total:,} worship sites • {vt_gps:,} geocoded ({100*vt_gps//vt_total}%)
Christian {vt_faiths.get('Christian',0):,} | Jewish {vt_faiths.get('Judaism',0):,} | Buddhist {vt_faiths.get('Buddhist',0):,} | Muslim {vt_faiths.get('Islam',0):,}

FEMA National Risk Index (tract-level):
• {vt_fema['tracts']} tracts scored — avg RISK_SCORE: {vt_fema['avg_risk']} (Relatively Low)
• Top hazards: Winter Weather {vt_fema['avg_winter']}, Inland Flood {vt_fema['avg_flood']}, Hurricane {vt_fema['avg_hurricane']}
• Social Vulnerability (SoVI): {vt_fema['avg_sovi']} | Tornado: {vt_fema['avg_tornado']} | Wildfire: {vt_fema['avg_wildfire']}

Crime ({vt_crime['year']} FBI UCR):
• Population: {vt_crime['population']:,} | Violent: {vt_crime['violent_crime']:,} | Homicide: {vt_crime['homicide']} | Property: {vt_crime['property_crime']:,}

🔗 Vermont sample (BigQuery): https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table
🔗 Buy on AWS Data Exchange: https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084"""

US_STATS = f"""{us_total:,} US worship sites • 91% GPS • 89% county FIPS • {us_fema_tracts:,} FEMA risk-scored tracts"""
ADX_LINK = "https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084"

ENRICH_BLURB = """WHAT'S IN THE DATASET:
• FTLM Taxonomy: 5-level classification (Civilization > Faith > Legacy > Tradition > Movement) — 12 faiths, 1,066 traditions, 300+ movements
• FEMA National Risk Index: 18 hazard scores joined to 980K US churches at tract level
• FBI Crime Data: State-level violent/property crime 1979-2024 + agency-level NIBRS 2024
• 10 Census geographic layers: Tract, Block Group, ZIP, Congressional District, State House/Senate, Urban/Rural
• 9 denomination hierarchies: Lutheran (57K), Catholic (33K), Baptist (36K), LDS (19K), JW (11K), and more
• Contacts: 337K websites, 46K phones, 16K emails
• 1.8M enrichment changes with full provenance tracking"""

SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

# ── Email templates ──

POLITICAL_BODY = f"""Hi {{{{org}}}} team,

GRID maps {global_total:,} worship sites globally — {us_total:,} in the US — with GPS coordinates, FTLM taxonomy (Civilization > Faith > Legacy > Tradition > Movement), and FEMA National Risk Index scores at the census tract level.

For political targeting, this means you can layer religious community density AND natural hazard risk onto voter files. Every worship site is classified across 5 taxonomic levels — slice by civilization, faith, legacy, tradition, or movement.

{US_STATS}

=== VERMONT EXAMPLE ===
{VT_SUMMARY}

{ENRICH_BLURB}

Buy on AWS Data Exchange — Vermont sample included free:
{ADX_LINK}

I'd love to send you a CSV export of any geography or set up a call.

Best,
{SIG}"""

# ── CHURCH OUTREACH PITCH (fear-based disaster angle) ──
CHURCH_SUBJECT = "Is your church in a high-risk disaster zone? Here's what FEMA says about your area"
CHURCH_BODY = f"""Pastor,

I run GRID — the Global Religious Infrastructure Database. We map every church, mosque, and temple in America, and we just integrated FEMA's National Risk Index data.

I looked up the risk profile for churches in your state, and here's what FEMA says:

VERMONT CHURCHES FACE:
• Winter Weather risk score: {vt_fema['avg_winter']}/100
• Inland Flood risk score: {vt_fema['avg_flood']}/100
• Hurricane risk score: {vt_fema['avg_hurricane']}/100

These are REAL numbers from FEMA's v1.20 National Risk Index — the same data insurance companies use to price your policy.

I can tell you exactly where YOUR church falls on all 18 hazard types (tornado, wildfire, earthquake, flood, hurricane, winter storm...), plus what FEMA says about your community's ability to recover (Resilience score) and how vulnerable your neighbors are (Social Vulnerability Index).

This isn't theoretical. Churches are the #1 emergency shelter in most communities. If your building isn't prepared for the hazards FEMA flagged, your congregation is at risk.

Want to see your church's risk profile? Reply and I'll send it — takes 30 seconds.

You can also see the full dataset on AWS Data Exchange:
{ADX_LINK}

Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
charlesaprescottjr@gmail.com | 843-504-4542"""

# ── CHURCH TEASER (for outreach queue) ──
CHURCH_TEASER_BODY = f"""Pastor {{{{name}}}},

I run a research project mapping every house of worship in America — {us_total:,} churches, mosques, temples, and synagogues. We just integrated FEMA's National Risk Index data (v1.20, Dec 2025).

Here's the thing most pastors don't realize: FEMA scores every census tract in America for 18 natural hazards. Your church sits in one of those tracts.

For churches in your area, the top risks are:
• Winter Weather
• Inland Flooding
• Hurricane

I can pull your specific risk profile — all 18 hazards, your Resilience score, and Social Vulnerability Index — in about 30 seconds. No cost, no catch. Just reply and ask.

Why does this matter? Churches are the default emergency shelter in most communities. If yours is in a high-risk zone, your congregation needs to know.

Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
charlesaprescottjr@gmail.com | 843-504-4542

P.S. — You can explore the Vermont sample data here (read-only):
https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table"""

INSURANCE_BODY = f"""Hi {{{{org}}}} team,

GRID maps {global_total:,} worship sites globally with FEMA risk scores at the census tract level — a complete prospect list with built-in risk profiling.

{ENRICH_BLURB}

=== VERMONT ===
{VT_SUMMARY}

Buy on AWS Data Exchange:
{ADX_LINK}

Best,
{SIG}"""

RESEARCH_BODY = f"""Hi {{{{org}}}} team,

GRID maps the physical footprint of religion — {global_total:,} worship sites across 291 countries, each classified by the 5-level FTLM taxonomy. Unlike survey data, GRID measures what's actually built.

{ENRICH_BLURB}

=== VERMONT ===
{VT_SUMMARY}

Buy on AWS Data Exchange:
{ADX_LINK}

Best,
{SIG}"""

GENERIC_BODY = f"""Hi {{{{org}}}} team,

GRID maps {global_total:,} worship sites globally — {us_total:,} in the US — with GPS, FTLM taxonomy, contacts, FEMA risk scores, and 10 geographic layers.

{US_STATS}

{ENRICH_BLURB}

=== VERMONT ===
{VT_SUMMARY}

Buy on AWS Data Exchange:
{ADX_LINK}

Best,
{SIG}"""

# ── All contacts ──
CONTACTS = [
    # Political
    {"org": "TargetSmart", "email": "sales@targetsmart.com", "sector": "political", "body": POLITICAL_BODY, "subject": "GRID: Religious infrastructure + FEMA risk data for voter targeting"},
    {"org": "Catalist", "email": "press@catalist.us", "sector": "political", "body": POLITICAL_BODY, "subject": "GRID: Religious infrastructure + FEMA risk data for voter targeting"},
    {"org": "Grassroots Analytics", "email": "sales@grassrootsanalytics.com", "sector": "political", "body": POLITICAL_BODY, "subject": "GRID: Religious infrastructure + FEMA risk data for voter targeting"},
    {"org": "i360", "email": "support@i-360.com", "sector": "political", "body": POLITICAL_BODY, "subject": "GRID: Religious infrastructure + FEMA risk data for voter targeting"},
    {"org": "L2 Data", "email": "info@L2-data.com", "sector": "political", "body": POLITICAL_BODY, "subject": "GRID: Religious infrastructure + FEMA risk data for voter targeting"},
    {"org": "Aristotle", "email": "info@aristotle.com", "sector": "political", "body": POLITICAL_BODY, "subject": "GRID: Religious infrastructure + FEMA risk data for voter targeting"},
    # Insurance
    {"org": "Church Mutual Insurance", "email": "info@churchmutual.com", "sector": "insurance", "body": INSURANCE_BODY, "subject": "GRID: Church property risk data — FEMA NRI + 3.4M worship sites"},
    # Research
    {"org": "Pew Research Center", "email": "info@pewresearch.org", "sector": "research", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
    {"org": "ARDA", "email": "arda@psu.edu", "sector": "research", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
    {"org": "Barna Group", "email": "info@barna.com", "sector": "research", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
    {"org": "Lilly Endowment", "email": "communications@lei.org", "sector": "research", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
    {"org": "Pew Charitable Trusts", "email": "info@pewtrusts.org", "sector": "research", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
    # Data brokers
    {"org": "SafeGraph", "email": "data@safegraph.com", "sector": "data_broker", "body": GENERIC_BODY, "subject": "GRID: 3.4M religious POIs with FEMA risk scores"},
    {"org": "Foursquare", "email": "partnerships@foursquare.com", "sector": "data_broker", "body": GENERIC_BODY, "subject": "GRID: 3.4M religious POIs with FEMA risk scores"},
    {"org": "Mapbox", "email": "sales@mapbox.com", "sector": "data_broker", "body": GENERIC_BODY, "subject": "GRID: 3.4M religious POIs with FEMA risk scores"},
    # Real estate
    {"org": "Zillow", "email": "industryrelations@zillow.com", "sector": "real_estate", "body": GENERIC_BODY, "subject": "GRID: Worship site proximity + FEMA risk for property listings"},
    {"org": "CoStar Group", "email": "sales@costar.com", "sector": "real_estate", "body": GENERIC_BODY, "subject": "GRID: Religious CRE data — worship sites with FEMA risk scores"},
    # Government
    {"org": "FEMA Mapping", "email": "FEMA-mapping@fema.dhs.gov", "sector": "government", "body": GENERIC_BODY, "subject": "GRID: Religious infrastructure + FEMA NRI — emergency shelter mapping"},
    # Faith orgs
    {"org": "National Association of Evangelicals", "email": "info@nae.net", "sector": "faith_org", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
    {"org": "World Council of Churches", "email": "info@wcc-coe.org", "sector": "faith_org", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
    {"org": "World Vision", "email": "info@worldvision.org", "sector": "faith_org", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
    {"org": "Catholic Relief Services", "email": "crs@crs.org", "sector": "faith_org", "body": RESEARCH_BODY, "subject": "GRID: Religious infrastructure data with FEMA risk scores"},
]

# ── Church outreach: only churches we can generate a risk report for ──
# Requirements: email + GPS + county_fips_5 + not Catholic/Anglican/Orthodox
db2 = sqlite3.connect('churches.db')
db2.row_factory = sqlite3.Row

church_contacts = []
for r in db2.execute("""
    SELECT c.id, c.name, c.city, c.tradition, cv.value as email,
           c.latitude, c.longitude, c.county_fips_5
    FROM churches c
    JOIN church_contact_values cv ON cv.church_id = c.id
    WHERE c.state='VT' AND c.country='US' AND cv.contact_type='email'
    AND cv.value LIKE '%@%'
    AND c.latitude IS NOT NULL
    AND c.county_fips_5 IS NOT NULL
    AND (c.tradition IS NULL OR (
        c.tradition NOT LIKE '%Catholic%'
        AND c.tradition NOT LIKE '%Anglican%'
        AND c.tradition NOT LIKE '%Episcopal%'
        AND c.tradition NOT LIKE '%Orthodox%'
    ))
    LIMIT 10
"""):
    church_contacts.append({
        "org": f"{r['name']} ({r['city']}, VT)",
        "email": r['email'],
        "sector": "church_outreach",
        "body": CHURCH_BODY,
        "subject": CHURCH_SUBJECT,
    })

db2.close()
print(f"  Church contacts found: {len(church_contacts)} (report-ready: email + GPS + FIPS, non-Catholic/Anglican/Orthodox)")

# ── Queue 'em ──
# Remove old v2/v1 multi-sector entries
if QUEUE_FILE.exists():
    lines = []
    with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                camp = entry.get('campaign', '')
                if camp not in ('political_data_firms', 'political_data_firms_v2', 'multi_sector_v1'):
                    lines.append(line)
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        f.writelines(lines)

queued = 0
with open(QUEUE_FILE, 'a', encoding='utf-8') as f:
    for c in CONTACTS + church_contacts:
        body = c['body'].replace('{{org}}', c['org'])
        if '{{name}}' in body and c.get('sector') == 'church_outreach':
            body = body.replace('{{name}}', c['org'].split('(')[0].strip().replace('SAINT ', 'St. ').title())
        entry = {
            "org": c['org'], "email": c['email'],
            "subject": c['subject'], "body": body,
            "campaign": "outreach_v3_fema", "sector": c['sector'],
            "queued_at": datetime.now().isoformat(),
        }
        f.write(json.dumps(entry) + '\n')
        queued += 1

print(f"Queued {queued} emails:")
print(f"  Political: 6 | Research: 5 | Data brokers: 3 | Insurance: 1 | Real Estate: 2 | Gov: 1 | Faith orgs: 4 | Church outreach: {len(church_contacts)}")
print(f"\nVermont: {vt_total:,} churches, FEMA avg risk {vt_fema['avg_risk']}")
print(f"To send: python scripts/outreach/send_unified.py")

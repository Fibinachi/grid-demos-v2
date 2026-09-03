"""
POLITICAL DATA FIRM OUTREACH — Build contact list + queue emails.
Pitches GRID (Global Religious Infrastructure Database) to political data firms
using Vermont as the showcase example slice.
"""
import json, sqlite3
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"

# ============================================================
# POLITICAL DATA FIRM CONTACTS
# ============================================================
POLITICAL_CONTACTS = [
    # === DEMOCRATIC/PROGRESSIVE ===
    {
        "org": "TargetSmart",
        "email": "sales@targetsmart.com",
        "note": "Leading Dem data/analytics firm. Also try press@targetsmart.com",
        "priority": 1,
        "tier": "Tier 1 — Core Political Data Ecosystem",
    },
    {
        "org": "Catalist",
        "email": "press@catalist.us",
        "note": "Progressive data hub. Contact form at catalist.us/contact-us. Phone: (202) 962-7200",
        "priority": 1,
        "tier": "Tier 1 — Core Political Data Ecosystem",
    },
    {
        "org": "Grassroots Analytics",
        "email": "sales@grassrootsanalytics.com",
        "note": "Progressive fundraising + data. DC-based. CEO: Meghan McAnespie. ~68 employees",
        "priority": 1,
        "tier": "Tier 4 — Niche Fundraising/Tech",
    },
    # === REPUBLICAN/CONSERVATIVE ===
    {
        "org": "i360",
        "email": "support@i-360.com",
        "note": "Koch Industries subsidiary. GOP data powerhouse. Contact form at i-360.com/get-started. 10K+ orgs use it.",
        "priority": 1,
        "tier": "Tier 1 — Core Political Data Ecosystem",
    },
    {
        "org": "Data Trust",
        "email": None,  # No public email — use contact form
        "note": "THE GOP voter file provider. Served 5,000+ campaigns in 2024. thedatatrust.com. 11-50 employees.",
        "priority": 1,
        "tier": "Tier 1 — Core Political Data Ecosystem",
    },
    # === NON-PARTISAN ===
    {
        "org": "L2 Data",
        "email": "info@L2-data.com",
        "note": "Non-partisan voter file. 50+ years. 250M+ records. Also: matt.curley@l2-data.com (West coast sales)",
        "priority": 1,
        "tier": "Tier 1 — Non-Partisan Voter Data",
    },
    {
        "org": "Aristotle",
        "email": "info@aristotle.com",
        "note": "Non-partisan data/analytics. DC HQ. Also: sales@aristotle.com, 800-296-2747. International office in Toronto.",
        "priority": 1,
        "tier": "Tier 1 — Non-Partisan",
    },
    # === CALIFORNIA ===
    {
        "org": "PDI (Political Data Inc.)",
        "email": None,  # Contact form at politicaldata.com
        "note": "CA-focused voter data. pdione.net. Phone: (562) 406-2360. CA early ballot returns leader.",
        "priority": 2,
        "tier": "Tier 4 — California Specialist",
    },
    # === PARTY COMMITTEES ===
    {
        "org": "DNC Tech/Data Team",
        "email": None,
        "note": "democrats.org/tech — Apply via their data infrastructure program. No direct sales email public.",
        "priority": 2,
        "tier": "Party Committee",
    },
    {
        "org": "RNC Data Team",
        "email": None,
        "note": "gop.com — No direct data team email public. Contact via main RNC channels.",
        "priority": 2,
        "tier": "Party Committee",
    },
    # === DEEP ROOT (Trump 2016 data firm) ===
    {
        "org": "Deep Root Analytics",
        "email": None,
        "note": "GOP data firm (Trump 2016 campaign data team). Famous for 198M voter data exposure. Contact via website.",
        "priority": 2,
        "tier": "Tier 3 — GOP Analytics",
    },
]

# ============================================================
# VERMONT STATS (from cleaned data)
# ============================================================
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

vt_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()['n']
vt_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND latitude IS NOT NULL").fetchone()['n']

# Faith breakdown
vt_faiths = {}
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY faith ORDER BY n DESC"):
    vt_faiths[r['faith']] = r['n']

# Tradition breakdown (top 10)
vt_trads = []
for r in db.execute("""
    SELECT tradition, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND tradition IS NOT NULL 
    GROUP BY tradition ORDER BY n DESC LIMIT 10
"""):
    vt_trads.append((r['tradition'], r['n']))

# Contact coverage
vt_contacts = {}
for r in db.execute('''
    SELECT contact_type, COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.state='VT' AND c.country='US'
    GROUP BY contact_type
'''):
    vt_contacts[r['contact_type']] = r['n']

# US totals for context
us_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
us_faiths = {}
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE country='US' GROUP BY faith ORDER BY n DESC"):
    us_faiths[r['faith']] = r['n']

db.close()

# ============================================================
# BUILD EMAIL PITCH
# ============================================================
SUBJECT = "GRID: 3.4M worship sites with contact data — religious micro-targeting for campaigns"

BODY = f"""Hi {{{{org}}}} team,

I'm reaching out because GRID (Global Religious Infrastructure Database) could be a powerful new data layer for your voter targeting and micro-targeting products.

WHAT GRID IS:
The world's largest database of religious infrastructure — 3.4 million churches, mosques, temples, synagogues, and other worship sites across 200+ countries. 1.07M in the US alone.

Every record includes:
• GPS coordinates (91% US coverage)
• Faith + tradition classification (100+ traditions, from Catholic parishes to Chabad houses to Sunni mosques)
• Denomination, landmark type, address
• Contact data: 337K US websites, 46K phones, 16K emails
• County-level geography (FIPS codes)

WHY IT MATTERS FOR POLITICAL DATA:
Religious affiliation is one of the strongest predictors of voting behavior. GRID lets you:
• Map faith community density at the precinct, county, or district level
• Target GOTV by specific denominations (e.g., all Evangelical churches in swing districts)
• Enrich voter files with proximity-to-worship-site metrics
• Identify faith-based community anchors for organizing

VERMONT EXAMPLE (a state with only ~2,300 worship sites):
Our Vermont slice has 2,284 churches across 14 counties — 2,046 with GPS coordinates. 
Faith breakdown: Christian 2,183 (Protestant 1,351, Catholic 180, Baptist 196, Pentecostal 75), 
Jewish 41 (including 12 Chabad), Buddhist 23, Muslim 9, Hindu 2.
907 have websites, 74 have phone numbers, 37 have email addresses.
Every record is geocoded, classified by tradition, and enrichment-tracked.

US TOTALS:
{us_total:,} worship sites: Christian {us_faiths.get('Christian',0):,}, Jewish {us_faiths.get('Judaism',0):,}, 
Muslim {us_faiths.get('Islam',0):,}, Hindu {us_faiths.get('Hindu',0):,}, Buddhist {us_faiths.get('Buddhist',0):,}.

NEXT STEP:
I'd love to send you a Vermont sample CSV so you can see the data quality firsthand, 
or set up a quick call to discuss how GRID could integrate with your existing data products.

Happy to provide a sample slice of any state, county, or district.

Best,
Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542
BigQuery: american-rel-infra.American_Religious_Infrastructure"""

# ============================================================
# QUEUE EMAILS (only those with email addresses)
# ============================================================
queued = 0
no_email = 0

with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
    existing = {json.loads(line).get('org', '') for line in f if line.strip()}

with open(QUEUE_FILE, 'a', encoding='utf-8') as f:
    for contact in POLITICAL_CONTACTS:
        if not contact['email']:
            no_email += 1
            continue
        if contact['org'] in existing:
            continue
        
        body = BODY.replace('{{org}}', contact['org'])
        
        entry = {
            "org": contact['org'],
            "email": contact['email'],
            "subject": SUBJECT,
            "body": body,
            "campaign": "political_data_firms",
            "tier": contact['tier'],
            "priority": contact['priority'],
            "note": contact['note'],
            "queued_at": datetime.now().isoformat(),
        }
        f.write(json.dumps(entry) + '\n')
        queued += 1

# ============================================================
# SUMMARY
# ============================================================
print(f"=== POLITICAL DATA FIRM OUTREACH QUEUED ===")
print(f"Queued for sending: {queued}")
print(f"No public email (contact form needed): {no_email}")
print(f"Queue file: {QUEUE_FILE}")
print()
print("=== CONTACTS WITHOUT EMAIL (need manual outreach) ===")
for c in POLITICAL_CONTACTS:
    if not c['email']:
        print(f"  {c['org']} — {c['note'][:80]}")
print()
print("=== VERMONT SLICE STATS ===")
print(f"Total: {vt_total:,} | GPS: {vt_gps:,} ({100*vt_gps//vt_total}%)")
print(f"Faith: {vt_faiths}")
print(f"Contacts: {vt_contacts}")
print(f"Top traditions: {vt_trads[:5]}")
print()
print("To send: python scripts/outreach/send_unified.py")
print("(Runs 1 email per 3 minutes via Gmail SMTP)")

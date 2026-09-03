"""
Create BigQuery Vermont demo view + regenerate political outreach with BQ link.
"""
import json, sqlite3
from pathlib import Path
from datetime import datetime
from google.cloud import bigquery

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"

PROJECT = "american-rel-infra"
DATASET = "American_Religious_Infrastructure"

# ============================================================
# 1. CREATE BIGQUERY VERMONT VIEW
# ============================================================
print("=== CREATING VERMONT BIGQUERY VIEW ===")
client = bigquery.Client(project=PROJECT)

# Create a demo view with Vermont churches (limited sample for exploration)
view_id = f"{PROJECT}.{DATASET}.demo_vt_churches"

# LIMIT 500 so they can explore but not download the full dataset
# Only use columns that exist in the BQ churches table
view_sql = f"""
SELECT 
    id,
    name,
    faith,
    tradition,
    landmark_type,
    city,
    state,
    county,
    country,
    latitude,
    longitude,
    address,
    source
FROM `{PROJECT}.{DATASET}.churches`
WHERE state = 'VT' AND country = 'US'
ORDER BY name
LIMIT 500
"""

# Also create a Vermont summary/aggregation view (safe to share fully)
agg_view_id = f"{PROJECT}.{DATASET}.demo_vt_summary"
agg_sql = f"""
SELECT 
    faith,
    tradition,
    county,
    COUNT(*) as site_count,
    COUNTIF(latitude IS NOT NULL) as with_gps,
    ROUND(COUNTIF(latitude IS NOT NULL) * 100.0 / COUNT(*), 1) as pct_gps
FROM `{PROJECT}.{DATASET}.churches`
WHERE state = 'VT' AND country = 'US'
GROUP BY faith, tradition, county
ORDER BY site_count DESC
"""

try:
    # Drop existing views if any
    client.delete_table(view_id, not_found_ok=True)
    client.delete_table(agg_view_id, not_found_ok=True)
    
    # Create views
    view = bigquery.Table(view_id)
    view.view_query = view_sql
    client.create_table(view)
    print(f"  ✅ Created: {view_id}")
    
    agg_view = bigquery.Table(agg_view_id)
    agg_view.view_query = agg_sql
    client.create_table(agg_view)
    print(f"  ✅ Created: {agg_view_id}")
    
except Exception as e:
    print(f"  ⚠ BQ error: {e}")
    print("  Continuing without BQ views — update manually.")

BQ_VT_LINK = f"https://console.cloud.google.com/bigquery?project={PROJECT}&p={PROJECT}&d={DATASET}&t=demo_vt_churches&page=table"
BQ_VT_AGG_LINK = f"https://console.cloud.google.com/bigquery?project={PROJECT}&p={PROJECT}&d={DATASET}&t=demo_vt_summary&page=table"

# ============================================================
# 2. GET VERMONT STATS
# ============================================================
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

vt_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()['n']
vt_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND latitude IS NOT NULL").fetchone()['n']

vt_faiths = []
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY faith ORDER BY n DESC"):
    vt_faiths.append((r['faith'], r['n']))

vt_trads = []
for r in db.execute("""
    SELECT tradition, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND tradition IS NOT NULL 
    GROUP BY tradition ORDER BY n DESC LIMIT 12
"""):
    vt_trads.append((r['tradition'], r['n']))

vt_contacts = {}
for r in db.execute('''
    SELECT contact_type, COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.state='VT' AND c.country='US'
    GROUP BY contact_type
'''):
    vt_contacts[r['contact_type']] = r['n']

# County counts
vt_counties = []
for r in db.execute("""
    SELECT county, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND county IS NOT NULL AND county != ''
    GROUP BY county ORDER BY n DESC
"""):
    vt_counties.append((r['county'], r['n']))

# Top cities
vt_cities = []
for r in db.execute("""
    SELECT city, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND city IS NOT NULL AND city != ''
    GROUP BY city ORDER BY n DESC LIMIT 10
"""):
    vt_cities.append((r['city'], r['n']))

# US totals
us_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
us_faiths = {}
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE country='US' GROUP BY faith ORDER BY n DESC"):
    us_faiths[r['faith']] = r['n']

# Global totals
global_total = db.execute("SELECT COUNT(*) as n FROM churches").fetchone()['n']
global_countries = db.execute("SELECT COUNT(DISTINCT country) as n FROM churches").fetchone()['n']

db.close()

# ============================================================
# 3. BUILD VERMONT SUMMARY TEXT
# ============================================================
vt_summary = f"""VERMONT RELIGIOUS INFRASTRUCTURE — GRID Sample Slice

Total worship sites: {vt_total:,}  •  GPS coverage: {vt_gps:,} ({100*vt_gps//vt_total}%)

FAITH BREAKDOWN:
""" + "\n".join(f"  {faith}: {n:,}" for faith, n in vt_faiths) + f"""

TOP TRADITIONS:
""" + "\n".join(f"  {trad}: {n:,}" for trad, n in vt_trads[:8]) + f"""

CONTACT COVERAGE:
  Websites: {vt_contacts.get('website',0):,}
  Phones: {vt_contacts.get('phone',0):,}
  Emails: {vt_contacts.get('email',0):,}

TOP CITIES:
""" + "\n".join(f"  {city}: {n:,}" for city, n in vt_cities) + f"""

COUNTIES (all 14):
""" + "\n".join(f"  {cty}: {n:,}" for cty, n in vt_counties)

# ============================================================
# 4. BUILD UPDATED EMAIL
# ============================================================
SUBJECT = "GRID: Religious infrastructure data for voter micro-targeting (Vermont sample inside)"

BODY_TEMPLATE = f"""Hi {{{{org}}}} team,

I'm reaching out because GRID (Global Religious Infrastructure Database) could add a powerful new dimension to your voter targeting products — religious community mapping at the precinct level.

WHAT GRID IS:
{global_total:,} worship sites across {global_countries} countries. {us_total:,} in the US alone, each classified by faith, tradition, denomination, and contact availability.

Every record: GPS coordinates • faith + tradition • address • website/phone/email where available.

WHY THIS MATTERS FOR POLITICAL DATA:
Religious affiliation is one of the strongest predictors of voting behavior. GRID maps the physical infrastructure — letting you:
• Layer faith community density onto voter files at any geography
• Target GOTV by denomination (all 196 Baptist churches vs. 75 Pentecostal in VT, for example)
• Identify community anchors for organizing and canvassing
• Model religious composition where Census doesn't capture it

=== VERMONT SAMPLE SLICE ===
{vt_summary}

EXPLORE THE DATA YOURSELF:
🔗 Vermont churches sample (500 records, read-only): {BQ_VT_LINK}
🔗 Vermont aggregated summary (full, no download limit): {BQ_VT_AGG_LINK}

These BigQuery views let you run SQL queries against the Vermont data directly — filter by county, tradition, GPS proximity, etc. The sample view is capped at 500 rows so you can explore without downloading our full dataset.

NEXT STEP:
Happy to provide a CSV export of any state, district, or county. Or set up a 15-minute call to show you how GRID maps onto your existing data products.

Best,
Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

# ============================================================
# 5. QUEUE EMAILS
# ============================================================
POLITICAL_CONTACTS = [
    {"org": "TargetSmart", "email": "sales@targetsmart.com", "tier": "Democratic data leader"},
    {"org": "Catalist", "email": "press@catalist.us", "tier": "Progressive data hub"},
    {"org": "Grassroots Analytics", "email": "sales@grassrootsanalytics.com", "tier": "Progressive fundraising+data"},
    {"org": "i360", "email": "support@i-360.com", "tier": "Koch/GOP data powerhouse"},
    {"org": "L2 Data", "email": "info@L2-data.com", "tier": "Non-partisan voter file (50yr)"},
    {"org": "Aristotle", "email": "info@aristotle.com", "tier": "Non-partisan data/analytics"},
]

# Clear old political entries to avoid duplicates
if QUEUE_FILE.exists():
    lines = []
    with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                if entry.get('campaign') != 'political_data_firms_v2':
                    lines.append(line)
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        f.writelines(lines)

queued = 0
with open(QUEUE_FILE, 'a', encoding='utf-8') as f:
    for contact in POLITICAL_CONTACTS:
        body = BODY_TEMPLATE.replace('{{org}}', contact['org'])
        entry = {
            "org": contact['org'],
            "email": contact['email'],
            "subject": SUBJECT,
            "body": body,
            "campaign": "political_data_firms_v2",
            "tier": contact['tier'],
            "queued_at": datetime.now().isoformat(),
        }
        f.write(json.dumps(entry) + '\n')
        queued += 1

# ============================================================
# 6. SAVE VERMONT SUMMARY TO FILE
# ============================================================
summary_path = OUT / "vt_summary_for_outreach.txt"
summary_path.write_text(vt_summary, encoding='utf-8')

print(f"=== DONE ===")
print(f"Queued: {queued} emails")
print(f"Vermont summary saved: {summary_path}")
print(f"BQ sample view: {BQ_VT_LINK}")
print(f"BQ aggregate view: {BQ_VT_AGG_LINK}")
print(f"\nTo send: python scripts/outreach/send_unified.py")

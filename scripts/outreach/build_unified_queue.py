"""
BUILD: Whale email pitches + BQ views + unified continuous sender.
Maximizes the 1-email-per-3-minutes Gmail slot.
"""
import sqlite3, smtplib, time, os, sys, csv, json
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.cloud import bigquery
from datetime import datetime

PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    print("Set GMAIL_APP_PASSWORD"); sys.exit(1)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
REPLY_TO = "charlesaprescott@outlook.com"
SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

BQ_BASE = "https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure"

client = bigquery.Client(project="american-rel-infra")
DATASET = "American_Religious_Infrastructure"
PROJECT = "american-rel-infra"

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"

# ============================================================
# 1. CREATE BQ DEMO VIEWS FOR WHALES
# ============================================================
print("=== CREATING BQ DEMO VIEWS ===\n")

demo_views = {
    "demo_global_top10": {
        "desc": "Top 10 countries by worship site count — shows global scale",
        "sql": f"SELECT country, faith, COUNT(*) as sites FROM `{PROJECT}.{DATASET}.churches` WHERE latitude IS NOT NULL GROUP BY country, faith ORDER BY COUNT(*) DESC"
    },
    "demo_us_catholic": {
        "desc": "US Catholic parishes with enrichment — what a diocese gets",
        "sql": f"SELECT c.* FROM `{PROJECT}.{DATASET}.churches` c JOIN `{PROJECT}.{DATASET}.church_enrichment` ce ON ce.church_id=c.id WHERE c.country='US' AND c.tradition LIKE '%Catholic%' LIMIT 1000"
    },
    "demo_muslim_world": {
        "desc": "Global Muslim worship sites — 361K mosques",
        "sql": f"SELECT * FROM `{PROJECT}.{DATASET}.churches` WHERE faith='Islam' AND latitude IS NOT NULL LIMIT 1000"
    },
    "demo_contact_enriched": {
        "desc": "Churches with email+phone+website — the commercial slice",
        "sql": f"SELECT c.id, c.name, c.faith, c.tradition, c.city, c.state, c.country, c.latitude, c.longitude FROM `{PROJECT}.{DATASET}.churches` c WHERE c.id IN (SELECT DISTINCT church_id FROM `{PROJECT}.{DATASET}.church_contact_values` WHERE contact_type IN ('email','phone','website')) LIMIT 1000"
    }
}

for vid, info in demo_views.items():
    view_id = f"{PROJECT}.{DATASET}.{vid}"
    try:
        client.query(f"CREATE OR REPLACE VIEW `{view_id}` AS {info['sql']}").result()
        print(f"  ✅ {vid} — {info['desc']}")
    except Exception as e:
        print(f"  ❌ {vid}: {e}")

# ============================================================
# 2. BUILD WHALE EMAIL QUEUE
# ============================================================
print("\n=== BUILDING WHALE EMAILS ===\n")

whales = [
    {
        "to": "contactems@experian.com",
        "name": "Experian Marketing Services",
        "subject": "GRID: 3.4M Religious POI Dataset — Enrich Experian's Location Intelligence",
        "body": f"""Hi Experian Marketing Team,

I'd like to discuss how GRID (Global Religious Infrastructure Database) could enrich Experian's location intelligence and consumer data products.

GRID contains 3.4M worship sites across 291 countries — every church, mosque, temple, synagogue, and shrine — each geocoded to GPS coordinates and classified across 12 faiths, 206 traditions, and 303 movements.

What makes this valuable for Experian:

• 3.36M geocoded POIs — unmatched religious infrastructure coverage globally
• 1.02M US churches with Census tract demographics (income, poverty, education, home values)
• 399K websites, 48K phone numbers, 16K emails — verified contact data
• 100% faith-classified: Sunni vs Shia vs Ibadi; Catholic vs Baptist vs Pentecostal; Orthodox vs Reform vs Chabad
• Organizational hierarchy: 300K+ parent-child relationships across 7 denominations
• Multi-source verified provenance on every record

I've set up live BigQuery demo views so you can explore the data directly:

→ Global overview: {BQ_BASE}&t=demo_global_top10&page=table
→ US Catholic sample: {BQ_BASE}&t=demo_us_catholic&page=table
→ Global Muslim sites: {BQ_BASE}&t=demo_muslim_world&page=table
→ Contact-enriched slice: {BQ_BASE}&t=demo_contact_enriched&page=table

Could GRID complement Experian's existing location data? I'd welcome a conversation about data licensing — I'm at 843-504-4542.

Best,

{SIG}"""
    },
    {
        "to": None,  # D&B uses web form — skip for now
        "name": "Dun & Bradstreet",
        "subject": "SKIP — web form only",
        "body": "SKIP"
    },
    {
        "to": None,  # HERE uses partner form
        "name": "HERE Technologies",
        "subject": "SKIP — partner form only",
        "body": "SKIP"
    },
    {
        "to": None,  # Foursquare uses contact form
        "name": "Foursquare",
        "subject": "SKIP — contact form only",
        "body": "SKIP"
    },
]

# ============================================================
# 3. BUILD UNIFIED QUEUE FROM ALL SOURCES
# ============================================================
print("=== BUILDING UNIFIED QUEUE ===\n")

queue = []

# Source A: Whale emails with direct addresses
for w in whales:
    if w["to"] and "@" in w["to"] and "SKIP" not in w["subject"]:
        queue.append({
            "to": w["to"],
            "subject": w["subject"],
            "body": w["body"],
            "source": "whales",
            "org": w["name"]
        })
        print(f"  + WHALE: {w['name']} -> {w['to']}")

# Source B: Remaining enterprise CSV leads (not yet sent, not bounced)
sent_log = OUT / "gmail_sent.txt"
bounce_log = OUT / "gmail_bounced.txt"

already_sent = set()
if sent_log.exists():
    already_sent = set(sent_log.read_text().strip().split("\n"))

bounced_emails = set()
if bounce_log.exists():
    bounced_emails = set(bounce_log.read_text().strip().split("\n"))
print(f"  Bounced addresses: {len(bounced_emails)}")

with open(OUT / "outreach_emails.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["contact_type"] == "Email" and r["org"] not in already_sent:
            queue.append({
                "to": r["contact_value"],
                "subject": r["subject"],
                "body": r["body"],
                "source": "enterprise_csv",
                "org": r["org"]
            })

print(f"  + ENTERPRISE CSV: {sum(1 for q in queue if q['source']=='enterprise_csv')} remaining")

# Source C: Church teaser campaign (generate on-the-fly)
TEASER_COUNT = 500  # first batch
db = sqlite3.connect("E:/grid/churches.db")

teaser_sent = set()
teaser_log = OUT / "church_campaign_sent.txt"
if teaser_log.exists():
    teaser_sent = set(int(x) for x in teaser_log.read_text().strip().split("\n") if x.strip())

teaser_churches = db.execute(f"""
    SELECT c.id, c.name, c.city, c.state, c.tradition,
           (SELECT value FROM church_contact_values WHERE church_id=c.id AND contact_type='email' LIMIT 1) as email,
           ca.acs_median_income, ca.acs_total_pop, ca.acs_poverty_rate
    FROM churches c
    LEFT JOIN church_census_us ca ON ca.church_id = c.id
    WHERE c.country = 'US'
      AND c.id IN (SELECT church_id FROM church_contact_values WHERE contact_type='email')
      AND c.id NOT IN ({','.join(str(x) for x in teaser_sent) if teaser_sent else '0'})
    ORDER BY c.state, c.city
    LIMIT {TEASER_COUNT}
""").fetchall()

for c in teaser_churches:
    name = c[1] or "Church Leader"
    city = c[2] or "your community"
    state = c[3] or ""
    location = f"{city}, {state}" if state else city
    income_str = f"${c[6]:,.0f}" if c[6] else "varies"
    pop_str = f"{c[7]:,.0f}" if c[7] else "your area"
    poverty_str = f"{c[8]:.1f}%" if c[8] else "varies"
    
    subject = f"Community Snapshot for {name} — {location}"
    body = f"""Hi {name},

I put together a quick community snapshot for your church in {location}:

📊 Neighborhood median income: {income_str}
👥 Area population: {pop_str}
🏠 Poverty rate: {poverty_str}

This is a preview from the GRID Community Intelligence Report — built from Census ACS data, FCC broadband maps, and religious infrastructure mapping.

The full $250 report includes complete demographics, a religious landscape map of every worship site near you, outreach opportunity analysis, voting patterns, and peer comparison data.

👉 Get the full report: https://buymeacoffee.com/CharlesPrescott

After purchase, I'll email your complete report within 24 hours.

Blessings,

{SIG}

P.S. Reply with any specific data question about {city} — happy to share a custom preview."""

    queue.append({
        "to": c[5],
        "subject": subject,
        "body": body,
        "source": "church_teaser",
        "org": name,
        "church_id": c[0]
    })

print(f"  + CHURCH TEASERS: {len(teaser_churches)} generated")

db.close()

# Source D: Faith media leads (studios, streaming, TV, publishing, curriculum)
print("  + FAITH MEDIA: loading...")
if (OUT / "faith_media_leads.json").exists():
    media = json.load(open(OUT / "faith_media_leads.json"))
    for m in media:
        key = m['org'].lower()
        if key not in already_sent and m['email'] not in already_sent:
            queue.append({
                "to": m['email'],
                "subject": f"GRID: church partnership data for {m['org'][:40]}",
                "body": f"Dear {m['org']},\n\nGRID maps 1M+ US churches for partnership targeting — contact charlesaprescottjr@gmail.com for a custom extract of your service area.",
                "source": "faith_media",
                "org": m['org']
            })
    print(f"  + FAITH MEDIA: {sum(1 for q in queue if q['source']=='faith_media')}")

# Source E: Faith hunger leads (food banks, hunger orgs, church partnership networks)
print("  + FAITH HUNGER: loading...")
if (OUT / "faith_hunger_leads.json").exists():
    hunger = json.load(open(OUT / "faith_hunger_leads.json"))
    for h in hunger:
        key = h['org'].lower()
        if key not in already_sent and h['email'] not in already_sent:
            queue.append({
                "to": h['email'],
                "subject": f"GRID: Every church in your service area for food program partnerships",
                "body": f"Dear {h['org']},\n\nGRID maps 1M+ US churches by denomination, contact info, and FEMA risk data — perfect for food pantry partner targeting. Contact charlesaprescottjr@gmail.com for a free service area extract.",
                "source": "faith_hunger",
                "org": h['org']
            })
    print(f"  + FAITH HUNGER: {sum(1 for q in queue if q['source']=='faith_hunger')}")

# Source F: Muslim organization leads (relief, advocacy, finance, travel, halal)
print("  + MUSLIM ORGS: loading...")
if (OUT / "muslim_org_leads.json").exists():
    muslim = json.load(open(OUT / "muslim_org_leads.json"))
    for m in muslim:
        key = m['org'].lower()
        if key not in already_sent and m['email'] not in already_sent:
            queue.append({
                "to": m['email'],
                "subject": f"GRID: 361K mosques mapped — data for {m['org'][:40]}",
                "body": f"Dear {m['org']},\n\nGRID maps 361K mosques globally (35 traditions, 100% classified) — contact charlesaprescottjr@gmail.com for a free extract of your target region.",
                "source": "muslim_org",
                "org": m['org']
            })
    print(f"  + MUSLIM ORGS: {sum(1 for q in queue if q['source']=='muslim_org')}")

# Source G: MENA embassy leads (government mosque registry requests)
print("  + MENA EMBASSIES: loading...")
if (OUT / "mena_embassy_leads.json").exists():
    mena = json.load(open(OUT / "mena_embassy_leads.json"))
    for m in mena:
        key = m['org'].lower()
        if key not in already_sent and m['email'] not in already_sent:
            queue.append({
                "to": m['email'],
                "subject": m['subject'],
                "body": m['body'],
                "source": "mena_embassy",
                "org": m['org']
            })
    print(f"  + MENA EMBASSIES: {sum(1 for q in queue if q['source']=='mena_embassy')}")

# Source H: Insurance data departments — run build_insurance_pipeline.py separately
# (36 contacts across P&C, reinsurance, InsurTech, data vendors, specialty, consulting)
# Adds directly to unified_queue.jsonl when run without --preview
print(f"  ℹ INSURANCE: run build_insurance_pipeline.py separately (36 leads)")

# Filter out bounced addresses before writing
if bounced_emails:
    before = len(queue)
    queue = [item for item in queue
             if (item.get("to") or item.get("email") or "").strip().lower() not in bounced_emails]
    removed = before - len(queue)
    if removed:
        print(f"\n  🚫 Removed {removed} bounced entries from queue")

# Write queue
with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    for item in queue:
        f.write(json.dumps(item) + "\n")

print(f"\n=== TOTAL QUEUE: {len(queue)} emails ===")
if bounced_emails:
    print(f"  ({len(bounced_emails)} bounced addresses excluded)")
print(f"  Whales:       {sum(1 for q in queue if q['source']=='whales')}")
print(f"  Enterprise:   {sum(1 for q in queue if q['source']=='enterprise_csv')}")
print(f"  Church:       {sum(1 for q in queue if q['source']=='church_teaser')}")
print(f"  Faith Media:  {sum(1 for q in queue if q['source']=='faith_media')}")
print(f"  Faith Hunger: {sum(1 for q in queue if q['source']=='faith_hunger')}")
print(f"  Muslim Orgs:  {sum(1 for q in queue if q['source']=='muslim_org')}")
print(f"  MENA Embassy:  {sum(1 for q in queue if q['source']=='mena_embassy')}")
print(f"\n  At 1/3min = {len(queue)*3/60:.1f} hours to complete")
print(f"  Queue file: {QUEUE_FILE}")

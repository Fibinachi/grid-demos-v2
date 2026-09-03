"""
WEEKEND BLAST — Chains all faith-specific outreach lists.
Whales → Jewish → Muslim/Hindu → Buddhist/Sikh/Bahai → Churches
Sends at 1 per 3 min (~480/day). No gap between lists.
"""
import json, smtplib, time, os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
PWD = os.environ.get("GMAIL_APP_PASSWORD")
INTERVAL = 180
OUT = Path("outputs/outreach")
SENT_LOG = OUT / "gmail_sent.txt"
FAIL_LOG = OUT / "gmail_failed.txt"
ADX = "https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084"
BQ = "https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table"
SIG = "Charles Prescott\nCreator, GRID\ncharlesaprescottjr@gmail.com | 843-504-4542"

if not PWD: print("Set GMAIL_APP_PASSWORD"); exit(1)

# ── Load all lead lists ──
def load_json(path):
    if path.exists():
        return json.load(open(path))
    return []

leads = []

# Faith-specific leads with custom subjects/bodies
faith_lists = [
    # (file, faith_name, subject_template, body_template)
]

# Simple approach: load all lead files, build body per faith
for file, faith_label_hint in [
    (OUT/"jewish_sent.txt", None),  # skip - sent log, not lead file
]:
    pass

# Load actual lead files
for file, fname in [
    ("buddhist_sikh_bahai_leads.json", "buddhist_sikh_bahai_leads.json"),
    ("hindu_muslim_leads.json", "hindu_muslim_leads.json"),
]:
    p = OUT / fname
    if p.exists():
        leads.extend(load_json(p))

# Also load Jewish leads (built separately)
# We'll add them inline


# Load already sent
already = set()
for log_file in [SENT_LOG, OUT/"church_campaign_sent.txt", OUT/"jewish_sent.txt", OUT/"whale_sent.txt"]:
    if log_file.exists():
        for line in log_file.read_text().strip().split('\n'):
            if line.strip():
                already.add(line.strip().lower())

# Filter
pending = [l for l in leads if l.get('email','').lower() not in already and l.get('org','').lower() not in already]
print(f"Total pending: {len(pending)} from {len(leads)} loaded")

from collections import Counter
for s, n in Counter(l.get('faith','?') for l in pending).most_common():
    print(f"  {s}: {n}")

# ── Build body per faith ──
def make_body(lead):
    faith = lead.get('faith', 'Other')
    org = lead['org']
    
    if faith == 'Judaism':
        stats = "26,632 Jewish entries | 98% GPS | 54 countries | 12 traditions | Chabad hierarchy: 3,012"
    elif faith == 'Islam':
        stats = "361,077 global mosques | 227 countries | 35 traditions | 99.8% GPS"
    elif faith == 'Hindu':
        stats = "201,988 temples | 162 countries | 73 traditions | 99% GPS | Vaishnavism, Shaivism, Swaminarayan, ISKCON"
    elif faith == 'Buddhist':
        stats = "199,010 temples/monasteries | 119 countries | 70 traditions | 100% GPS | Japan 71K, Thailand 54K, Myanmar 21K"
    elif faith == 'Sikh':
        stats = "6,706 gurdwaras | 60 countries | 25 traditions | 100% DeepSeek-classified"
    elif faith == 'Bahai':
        stats = "1,192 hierarchy records | World Centre > NSA > LSA > center | 4-tier structure"
    else:
        stats = "3,481,509 global worship sites | 291 countries | FTLM taxonomy"
    
    if lead.get('sector') == 'Government' and faith == 'Islam':
        # Middle East governments already have their own national mosque lists
        # Pitch them on global diaspora data they can't get elsewhere
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) maps the global Muslim ummah — 361,077 mosques across 227 countries, each classified by tradition (Sunni, Shia, Ibadi, Sufi, Ahmadiyya) and geocoded.

While you have your own national mosque registry, GRID provides what no single government can: a complete picture of the global diaspora — every mosque in every country, from the US (6,707) to Indonesia (101K) to Germany to Brazil.

This matters for:
• Mapping the ummah globally — know where every mosque is, not just in your borders
• Diaspora outreach — identify communities your programs currently miss
• Hajj infrastructure — every mosque that organizes pilgrimages
• Tradition distribution — Sunni vs Shia vs Ibadi mapping worldwide
• Aid coordination — mosques as disaster relief nodes in 227 countries

FEMA risk scores are also joined at the census tract level for all US and European mosques (18 hazard types).

Buy on AWS Data Exchange (Vermont sample free):
{ADX}

Happy to discuss a custom extract for the entire Muslim world.

{SIG}"""
    else:
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) contains the most comprehensive dataset on {faith.lower()} religious infrastructure ever assembled.

{faith_label} DATA:
• {stats}
• FEMA National Risk Index scores joined at census tract level (18 hazard types)
• FBI crime data: state-level 1979-2024 + agency-level 2024
• 10 Census geographic layers per site (tract, block group, ZIP, congressional district, etc.)
• 1.8M enrichment changes with full provenance tracking

Buy the full dataset on AWS Data Exchange (Vermont sample included free):
{ADX}

Explore Vermont sample (read-only BigQuery):
{BQ}

Happy to discuss custom extracts for {org}.

{SIG}"""

# ── Send loop ──
def send(to, subj, body):
    msg = MIMEMultipart()
    msg["From"] = FROM; msg["To"] = to
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Disposition-Notification-To"] = FROM
    msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls(); s.login("charlesaprescottjr@gmail.com", PWD); s.send_message(msg)

ok = fail = 0
for i, lead in enumerate(pending):
    faith_label = lead.get('faith', 'Other')
    body = make_body(lead)
    subject = f"GRID: {faith_label} religious infrastructure data — {lead['org'][:40]}"
    
    print(f"[{i+1}/{len(pending)}] {lead['org'][:40]:40s} | {faith_label:12s} -> {lead['email']:30s}", end="", flush=True)
    try:
        send(lead['email'], subject, body); ok += 1
        to_log = f"{lead.get('org','')}|{lead.get('email','')}"
        with open(OUT/"gmail_sent.txt", "a") as f: f.write(f"{to_log}\n")
        print(f" OK")
    except Exception as e:
        fail += 1; print(f" FAIL: {str(e)[:60]}")
        with open(FAIL_LOG, "a") as f: f.write(f"{datetime.now().isoformat()},{lead.get('email','')},{e}\n")
    
    if i < len(pending) - 1:
        time.sleep(INTERVAL)

print(f"\n\nDone: {ok} sent, {fail} failed in {datetime.now().strftime('%H:%M')}")

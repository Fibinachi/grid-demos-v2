"""
WEEKEND BLAST MASTER — Chains ALL lead files sequentially.
Diaspora gov + Embassies + Jewish + Buddhist/Sikh/Bahai + Hindu/Muslim
Sends 1 per 3 min on the same Gmail session. Run after whale_sender.py finishes.
"""
import json, smtplib, time, os, sqlite3
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from collections import Counter

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
PWD = os.environ.get("GMAIL_APP_PASSWORD")
INTERVAL = 180
OUT = Path("outputs/outreach")

if not PWD: print("Set GMAIL_APP_PASSWORD"); exit(1)

# Load ALL lead files
all_leads = []

# 1. Diaspora governments (from diaspora_outreach.py list — inline)
from outreach.diaspora_outreach import DIASPORA
# Can't import inline, so load from the file
# Actually, let's just hardcode the combined list here
# Or better: load from the JSON lead files we already built

for fname in ["embassy_leads.json", "buddhist_sikh_bahai_leads.json", "hindu_muslim_leads.json"]:
    p = OUT / fname
    if p.exists():
        leads = json.load(open(p))
        all_leads.extend(leads)
        print(f"{fname}: {len(leads)} leads")

# Also add diaspora gov leads inline (not yet saved as JSON)
diaspora_gov = [
    {"org":"China State Council - Overseas Chinese Affairs","email":"qwhq@gqb.gov.cn","faith":"Chinese Folk"},
    {"org":"Indian Ministry of External Affairs - Diaspora","email":"diaspora@mea.gov.in","faith":"Hindu"},
    {"org":"Indian Council for Cultural Relations","email":"info@iccr.gov.in","faith":"Hindu"},
    {"org":"Turkish YTB (Diaspora)","email":"info@ytb.gov.tr","faith":"Islam"},
    {"org":"German BAMF Integration Research","email":"forschung@bamf.bund.de","faith":"Islam"},
    {"org":"UK Ministry of Housing - Integration","email":"integration@communities.gov.uk","faith":"Islam"},
    {"org":"French Interministerial Delegation Integration","email":"integration@interieur.gouv.fr","faith":"Islam"},
    {"org":"Netherlands Ministry Social Affairs - Integration","email":"integratie@minszw.nl","faith":"Islam"},
    {"org":"Swedish MUCF","email":"info@mucf.se","faith":"Islam"},
    {"org":"Danish Ministry Immigration & Integration","email":"integration@uim.dk","faith":"Islam"},
    {"org":"Belgian Myria","email":"info@myria.be","faith":"Islam"},
    {"org":"Austrian Integration Fund (OIF)","email":"info@integrationsfonds.at","faith":"Islam"},
    {"org":"Thai Office of National Buddhism","email":"info@onab.go.th","faith":"Buddhist"},
    {"org":"Vietnam State Committee for Overseas Vietnamese","email":"info@ucng.gov.vn","faith":"Buddhist"},
    {"org":"Pakistan Ministry of Religious Affairs","email":"info@mora.gov.pk","faith":"Islam"},
    {"org":"Indonesia Ministry of Religious Affairs","email":"info@kemenag.go.id","faith":"Islam"},
    {"org":"Bangladesh Ministry Religious Affairs","email":"info@mora.gov.bd","faith":"Islam"},
    {"org":"Sri Lanka Ministry of Buddhasasana","email":"info@buddhasasana.gov.lk","faith":"Buddhist"},
    {"org":"Mexico Institute of Mexicans Abroad","email":"ime@ime.gob.mx","faith":"Christian"},
    {"org":"Philippines Commission on Filipinos Overseas","email":"info@cfo.gov.ph","faith":"Christian"},
    {"org":"Nepal Ministry of Culture","email":"info@tourism.gov.np","faith":"Hindu"},
    {"org":"Myanmar Ministry of Religious Affairs","email":"info@mora.gov.mm","faith":"Buddhist"},
    {"org":"Korean MOFA - Overseas Koreans","email":"overseas@mofa.go.kr","faith":"Christian"},
    {"org":"EU Fundamental Rights Agency","email":"info@fra.europa.eu","faith":"Islam"},
    {"org":"EU Radicalisation Awareness Network","email":"ran@ec.europa.eu","faith":"Islam"},
]
all_leads.extend(diaspora_gov)

# Load already sent from ALL logs
already = set()
for log_file in [OUT/"gmail_sent.txt", OUT/"church_campaign_sent.txt", OUT/"whale_sent.txt", OUT/"jewish_sent.txt"]:
    if log_file.exists():
        for line in log_file.read_text().strip().split('\n'):
            if line.strip():
                already.add(line.strip().lower().split('|')[0].strip())

# Dedup by email
seen = set()
pending = []
for l in all_leads:
    e = l.get('email','').lower()
    o = l.get('org','').lower()
    if e and e not in seen and o not in already and e not in already:
        seen.add(e)
        pending.append(l)

print(f"\nTotal pending: {len(pending)}")
for f, n in Counter(l.get('faith','?') for l in pending).most_common():
    print(f"  {f}: {n}")

# DB for church outreach
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row
church_rows = list(db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.county, cv.value as email,
           c.latitude, c.longitude, c.county_fips_5,
           a.median_hh_income
    FROM churches c
    JOIN church_contact_values cv ON cv.church_id=c.id AND cv.contact_type='email'
    LEFT JOIN county_census_us a ON a.county_fips=c.county_fips_5
    WHERE c.country='US' AND cv.value LIKE '%@%' AND c.latitude IS NOT NULL
      AND c.county_fips_5 IS NOT NULL
      AND (c.tradition IS NULL OR (
          c.tradition NOT LIKE '%Catholic%' AND c.tradition NOT LIKE '%Anglican%'
          AND c.tradition NOT LIKE '%Episcopal%' AND c.tradition NOT LIKE '%Orthodox%'))
    ORDER BY a.median_hh_income DESC NULLS LAST
"""))
db.close()

church_pending = [r for r in church_rows if str(r['id']) not in already]
print(f"Churches (income-prioritized): {len(church_pending):,}")

ADX = "https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084"
BQ = "https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table"
SIG = "Charles Prescott\nCreator, GRID\ncharlesaprescottjr@gmail.com | 843-504-4542"

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

# Phase 1: Diaspora + Faith org leads
print(f"\n=== PHASE 1: Faith orgs & embassies ({len(pending)}) ===")
for i, lead in enumerate(pending):
    faith = lead.get('faith','Other')
    org = lead['org']
    
    body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) maps the global religious landscape like no other dataset — 3.48M worship sites across 291 countries, each geocoded and classified by tradition.

GRID includes:
• 361,077 mosques globally — Sunni/Shia/Ibadi/Sufi, 227 countries
• 201,988 Hindu temples — Vaishnavism/Shaivism/Swaminarayan, 162 countries
• 199,010 Buddhist temples — Mahayana/Theravada/Vajrayana, 119 countries
• 26,632 Jewish sites — Rabbinic/Chabad/Reform/Orthodox, 54 countries
• 6,706 Sikh gurdwaras — fully DeepSeek-classified
• 1,072 Bahai centers — full hierarchy from World Centre to local

All enriched with FEMA risk scores, FBI crime data, and 10 Census geography layers.

Buy on AWS Data Exchange:
{ADX}

Explore Vermont sample (read-only BigQuery):
{BQ}

{SIG}"""
    
    subject = f"GRID: {faith} religious infrastructure data — 3.48M sites globally"
    print(f"[{i+1}/{len(pending)}] {org[:40]:40s} | {faith:12s} -> {lead['email']:30s}", end="", flush=True)
    try:
        send(lead['email'], subject, body); ok += 1
        with open(OUT/"gmail_sent.txt","a") as f: f.write(f"{org}|{lead['email']}\n")
        print(f" OK")
    except Exception as e:
        fail += 1; print(f" FAIL: {str(e)[:60]}")
    if i < len(pending)-1: time.sleep(INTERVAL)

# Phase 2: Income-targeted churches
print(f"\n=== PHASE 2: Income-targeted churches ({len(church_pending):,}) ===")
for i, church in enumerate(church_pending[:100]):  # Top 100 by income
    income = church['median_hh_income']
    tier = "Premium" if income and income > 75000 else "Standard"
    subject = f"FEMA risk report for {church['name'][:30]} ({tier})"
    
    income_line = ""
    if income:
        t = "Very High" if income > 100000 else "High" if income > 75000 else "Upper-Middle" if income > 55000 else "Middle"
        income_line = f"\nYour area's median household income: ${income:,.0f} ({t})"
    
    body = f"""Pastor,

I run GRID — the Global Religious Infrastructure Database. We map every church in America and just integrated FEMA's National Risk Index (v1.20, Dec 2025).

Your church: {church['name']}
Location: {church['city']}, {church['state']}{income_line}

Here's the thing most pastors don't realize: FEMA scores every census tract in America for 18 natural hazards. Your church sits in one of those tracts.

I can pull your church's COMPLETE FEMA risk profile for $250 — covering all 18 hazard types, your Expected Annual Loss, Social Vulnerability Index, and Community Resilience score. This is the same data insurance companies use.

Reply "REPORT" and I'll send your custom report link. $250, one-time, no subscription.

{SIG}"""
    
    print(f"[{i+1}/{100}] {church['name'][:35]:35s} -> {church['email']:30s} ${income or 0:>8,.0f}", end="", flush=True)
    try:
        send(church['email'], subject, body); ok += 1
        with open(OUT/"church_campaign_sent.txt","a") as f: f.write(f"{church['id']}\n")
        print(f" OK")
    except Exception as e:
        fail += 1; print(f" FAIL: {str(e)[:60]}")
    time.sleep(INTERVAL)

print(f"\n\nWeekend blast complete: {ok} sent, {fail} failed")

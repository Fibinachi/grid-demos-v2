"""
ACADEMIC SENDER — University libraries, seminaries, religion departments.
July is when academic library budgets open. Institutional site license pricing.
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

ACADEMIC = json.load(open(OUT / "academic_leads.json"))
SEMINARIES = json.load(open(OUT / "seminaries_leads.json"))

# Combine — seminaries first (highest conversion probability), then general academic
all_leads = SEMINARIES + ACADEMIC

# Load already sent
already = set()
for f in [SENT_LOG, OUT/"whale_sent.txt", OUT/"church_campaign_sent.txt", OUT/"jewish_sent.txt"]:
    if f.exists():
        for line in f.read_text().strip().split('\n'):
            if line.strip():
                already.add(line.strip().lower().split('|')[0].strip())

pending = [l for l in all_leads if l['email'].lower() not in already and l['org'].lower() not in already]
print(f"Academic targets: {len(pending)} new (of {len(all_leads)} total)")
from collections import Counter
for t, n in Counter(l.get('type','Seminary') for l in pending).most_common():
    print(f"  {t}: {n}")

def send(to, subj, body):
    msg = MIMEMultipart()
    msg["From"] = FROM; msg["To"] = to
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls(); s.login("charlesaprescottjr@gmail.com", PWD); s.send_message(msg)

ok = fail = 0
for i, lead in enumerate(pending):
    org_type = lead['type']
    org = lead['org']
    
    # Customize pitch by type
    if org_type in ("Data Archive", "Publisher"):
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) is the world's most comprehensive religious infrastructure dataset — 3.48M worship sites across 291 countries, each classified by the FTLM taxonomy (Civilization > Faith > Legacy > Tradition > Movement).

We're looking for distribution partners to offer GRID through your existing academic institutional licensing channels. This would complement your current religion/theology database offerings.

What GRID offers your subscribers:
• 3.48M sites — every church, mosque, temple, synagogue, gurdwara, shrine
• FTLM taxonomy: 12 faiths, 1,066 traditions, 300+ movements — fully classified, 0% unclassified
• FEMA risk scores joined at census tract for all US sites (18 hazard types)
• FBI crime data (1979-2024) — enrichment layer for spatial research
• Weekly updates — continuously ingested from 20+ denominational sources
• Used in sociology, political science, geography, public health, and religious studies

Institutional pricing for your network (reseller discount available):
• Single institution: $997/yr
• Consortium (5+): $2,997/yr
• Seminary discount (under 1K FTE): $497/yr
• Global access: $4,997/yr

Buy on AWS Data Exchange (Vermont sample free):
{ADX}

Explore Vermont sample:
{BQ}

Interested in a reseller or distribution partnership for the fall semester cycle?

{SIG}"""
    elif org_type in ("Seminary Library", "Seminary"):
        body = f"""Dear {org},

July is the start of academic purchasing cycles, and I wanted to introduce GRID (Global Religious Infrastructure Database) as a new research resource for your seminary.

GRID maps 3.48M worship sites globally with the FTLM taxonomy — every church, mosque, temple, and synagogue classified by faith, tradition, and movement. It's the first complete dataset on the physical footprint of religion.

For theological education, GRID supports:
• Congregational studies — understand your denomination's landscape
• Sociology of religion — spatial analysis of religious communities  
• Missiology — map global church distribution
• Practical theology — church planting, urban ministry
• FEMA risk data joined to every US church (18 hazard types)

**Institutional site license for seminaries: $497/yr** (under 1K FTE)

This is a dataset subscription — not a one-time book purchase. It updates quarterly or more often as new sources are ingested.

Buy on AWS Data Exchange (Vermont sample free):
{ADX}

Explore Vermont sample:
{BQ}

Would your library be interested in a trial for fall semester?

{SIG}"""
    else:  # Departments, Associations, Research
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) is now available for academic institutional licensing — the world's most comprehensive religious infrastructure dataset, designed as a research complement to Pew, PRRI, and ARDA survey data.

Unlike survey data (which measures what people believe), GRID measures what's actually built — 3.48M worship sites across 291 countries.

For researchers in sociology, political science, geography, and religious studies:
• Religion demography at every geography (tract, county, state, national)
• 1,066 traditions fully classified across 12 faiths
• FEMA risk + FBI crime enrichment layers
• 10 Census geography layers per US site
• Complete provenance tracking — every record source-documented

Explore Vermont sample (free, read-only BigQuery):
{BQ}

Institutional pricing from $497/yr (seminary) to $997/yr (university).

{SIG}"""
    
    subject = f"GRID: Institutional site license for {org[:35]} — new for fall semester"
    print(f"[{i+1}/{len(pending)}] {org[:40]:40s} | {org_type:15s} -> {lead['email']:30s}", end="", flush=True)
    try:
        send(lead['email'], subject, body); ok += 1
        with open(SENT_LOG, "a") as f: f.write(f"{org}|{lead['email']}\n")
        print(f" OK")
    except Exception as e:
        fail += 1; print(f" FAIL: {str(e)[:60]}")
    if i < len(pending)-1: time.sleep(INTERVAL)

print(f"\nDone: {ok} sent, {fail} failed")

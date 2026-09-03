"""
PRIORITIZED SENDER — Fires all outreach campaigns in order of purchase likelihood.
Seminaries first (buying now, $497/yr), then media/hunger/muslim, then the rest.

Run once and let it go. At 1 per 3 min, total queue = ~18 hours.
"""
import json, smtplib, time, os, sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from collections import defaultdict

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

if not PWD:
    PWD = os.popen("powershell -c \"[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','Machine')\"").read().strip()
if not PWD: print("Set GMAIL_APP_PASSWORD"); exit(1)

def send(to, subj, body):
    msg = MIMEMultipart()
    msg["From"] = FROM; msg["To"] = to
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls(); s.login("charlesaprescottjr@gmail.com", PWD); s.send_message(msg)

def load_sent():
    sent = set()
    for f in [SENT_LOG, OUT/"whale_sent.txt", OUT/"church_campaign_sent.txt"]:
        if f.exists():
            for line in f.read_text().strip().split('\n'):
                if line.strip():
                    sent.add(line.strip().lower().split('|')[0].strip())
    return sent

def mark_sent(org): SENT_LOG.write_text(SENT_LOG.read_text() + f"{org}\n") if SENT_LOG.exists() else SENT_LOG.write_text(f"{org}\n")

# ============================================================
# TIER 1: SEMINARIES ($497/yr) — BUYING NOW, JULY BUDGET CYCLE
# ============================================================
SEMINARIES = json.load(open(OUT / "seminaries_leads.json"))
ACADEMIC = json.load(open(OUT / "academic_leads.json"))

TIER1 = [{"org": s["org"], "email": s["email"], "tier": 1, "type": "Seminary", "pitch": "seminary"} for s in SEMINARIES]

# ============================================================
# TIER 2: FAITH MEDIA ($997/yr) — HAVE BUDGET, CLEAR ROI
# ============================================================
MEDIA = json.load(open(OUT / "faith_media_leads.json"))
HUNGER = json.load(open(OUT / "faith_hunger_leads.json"))
MUSLIM = json.load(open(OUT / "muslim_org_leads.json"))

TIER2 = []
for m in MEDIA: TIER2.append({"org": m["org"], "email": m["email"], "tier": 2, "type": m["sector"], "pitch": "media"})
for h in HUNGER: TIER2.append({"org": h["org"], "email": h["email"], "tier": 2, "type": h["sector"], "pitch": "hunger"})
for m in MUSLIM: TIER2.append({"org": m["org"], "email": m["email"], "tier": 2, "type": m["sector"], "pitch": "muslim"})

# ============================================================
# TIER 0: SCHOLARS (free access) — BUILT DATASETS BY HAND
# ============================================================
SCHOLARS = json.load(open(OUT / "scholar_leads.json"))
TIER0 = [{"org": s["name"], "email": s["email"], "tier": 0, "type": "Scholar", "pitch": "scholar", "field": s.get("field","")} for s in SCHOLARS]

# ============================================================
# TIER 3: ACADEMIC NON-SEMINARY ($997/yr) — SLOWER DECISIONS
# ============================================================
SEMINARY_ORGS = {s["org"].lower() for s in SEMINARIES}
TIER3 = [{"org": a["org"], "email": a["email"], "tier": 3, "type": a["type"], "pitch": "academic"} for a in ACADEMIC if a["org"].lower() not in SEMINARY_ORGS]

# ============================================================
# TIER 4: EVERYTHING ELSE
# ============================================================
# Jewish orgs, diaspora, embassies, etc. could be added here
# For now, tier 4 is empty — these need separate senders
TIER4 = []

# ============================================================
# BUILD PRIORITY QUEUE
# ============================================================
all_leads = TIER0 + TIER1 + TIER2 + TIER3 + TIER4
already = load_sent()

pending = []
for l in all_leads:
    org_key = l['org'].lower()
    email_key = l['email'].lower()
    if org_key not in already and email_key not in already:
        pending.append(l)

# Dedup by org
seen_orgs = set()
deduped = []
for l in pending:
    if l['org'].lower() not in seen_orgs:
        seen_orgs.add(l['org'].lower())
        deduped.append(l)
pending = deduped

# Count by tier and type
tier_counts = defaultdict(lambda: defaultdict(int))
for l in pending:
    tier_counts[l['tier']][l.get('type', 'unknown')] += 1

print(f"{'='*60}")
print(f"PRIORITIZED OUTREACH — {len(pending)} targets")
print(f"{'='*60}")
total_time = len(pending) * INTERVAL / 3600
print(f"  Estimated time: {total_time:.1f} hours at {INTERVAL}s interval\n")

for tier in sorted(tier_counts.keys()):
    print(f"\n  TIER {tier}: {sum(tier_counts[tier].values())} targets")
    for type_name, count in sorted(tier_counts[tier].items(), key=lambda x: -x[1]):
        print(f"    {type_name:25s} {count}")

print(f"\n{'='*60}")
print(f"Press Ctrl+C to stop. Starting in 5 seconds...")
print(f"{'='*60}")
time.sleep(5)

# ============================================================
# SEND LOOP — by priority order
# ============================================================
ok = fail = 0
for i, lead in enumerate(pending):
    org = lead['org']
    to_addr = lead['email']
    tier = lead['tier']
    lead_type = lead.get('type', '')
    pitch = lead.get('pitch', 'generic')

    # Pick the right pitch template
    if pitch == "seminary":
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

This is a dataset subscription — not a one-time book purchase. It updates quarterly.

Buy on AWS Data Exchange (Vermont sample free):
{ADX}

Explore Vermont sample:
{BQ}

Would your library be interested in a trial for fall semester?

{SIG}"""
        subject = f"GRID: Institutional site license for {org[:35]} — new for fall semester"

    elif pitch == "media":
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) is the world's most comprehensive map of religious infrastructure — 3.48M worship sites globally, 1M+ in the US.

For media organizations targeting faith audiences through church partnerships, GRID provides what no other dataset can:
• 1M+ US churches — every congregation, not just survey samples
• Phone, email, website for 345K+ — direct contact for promotion
• FEMA risk scores — plan screenings in communities with need
• Location by census tract, county, DMA, congressional district

Use cases for faith media:
  → Route church screening materials by denomination
  → Target communities by theology (non-denom, evangelical, Catholic)
  → Plan releases by church density per DMA
  → Find mega-churches for curriculum partnerships

Vermont sample (free, read-only BigQuery):
{BQ}

Pricing from $997/yr. Want a free dataset sample covering your target counties?

{SIG}"""
        subject = f"GRID dataset for {org[:35]} — church partnerships"

    elif pitch == "hunger":
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) maps every faith community in America — 1M+ churches, mosques, temples, and synagogues — each classified by denomination, with contact info and census demographics.

For hunger organizations, this means:
• Find every potential church pantry partner in your service area
• Target churches in high food-insecurity census tracts (FEMA risk data)
• Contact denominational networks with one query
• Deploy disaster food response — know every church in a disaster county
• 345K+ phones and emails — start calling tomorrow

Vermont sample (free, read-only BigQuery):
{BQ}

Pricing from $497/yr (nonprofit). Need a customized extract of churches in your service area?
        subject = f"GRID: Every church in your service area for food program partnerships"

    elif pitch == "scholar":
        field = lead.get('field', '')
        if 'Jain' in field:
            body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) has 979 Jain temples in a single SQL query. Built in 30 minutes.

I don't know how long it took you to build your dataset, but I know the pain — constructing, cleaning, geocoding sacred sites by hand is what every scholar in this space has been doing. I've done it too.

GRID currently contains:
• 3.48M worship sites globally — every category
• 979 Jain sites: temples, shrines, community centers
• 203K Buddhist temples, 202K Hindu sites, 361K mosques
• 65K Shinto shrines, 23K synagogues, 6K Sikh gurdwaras
• 1,728 Bahai centers, 1,702 ancient/Pleiades sites
• Each classified by tradition — fully, down to the sub-tradition
• All geocoded, most with census data, FEMA risk, contact info
• Accessible by SQL — one query, no scraping

Individual scholar site license: $497/yr (institutional PO or card). Want a SQLite copy of the Jain subset, or the full database? Reply and I'll set up access.

Vermont sample (free, read-only BigQuery):
{BQ}

Charles Prescott
charlesaprescottjr@gmail.com"""
            subject = f"GRID: 979 Jain temples in one query — $497/yr scholar license"
        elif 'Zoroastrian' in field:
            body = f"""Dear {org},

GRID has the sacred topography of pre-Islamic Iran mapped — Zoroastrian sites, fire temples, tower of silence locations, all geocoded alongside 1,702 ancient sites from Pleiades. Individual scholar license: $497/yr.
Vermont sample (free, read-only BigQuery):
{BQ}
Charles Prescott
charlesaprescottjr@gmail.com"""
            subject = f"GRID: ancient & Zoroastrian sacred site data — $497/yr"
        elif 'Buddhist' in field or 'Buddhism' in field:
            body = f"""Dear {org},

GRID has 203K Buddhist sites — Theravada, Mahayana, Vajrayana, Zen, Pure Land — all geocoded and classified. Also 65K Shinto shrines, 5,619 Sikh gurdwaras, 1,702 ancient sites. Scholar license: $497/yr.

Vermont sample (free, read-only BigQuery):
{BQ}

Charles Prescott
charlesaprescottjr@gmail.com"""
            subject = f"GRID: 203K Buddhist sites — $497/yr scholar license"
        elif 'Sikh' in field:
            body = f"""Dear {org},

GRID: 5,619 Sikh sites, 5,353 gurdwaras, fully DeepSeek-classified by tradition (Khalsa, Singh Sabha, Nanaksar, Ravidassia, etc.). Scholar license: $497/yr.

Vermont sample (free, read-only BigQuery):
{BQ}

Charles Prescott
charlesaprescottjr@gmail.com"""
            subject = f"GRID: 5,619 Sikh gurdwaras — $497/yr scholar license"
        elif 'Shinto' in field:
            body = f"""Dear {org},

GRID has 65K Shinto shrines — all Shrine Shinto, fully geocoded across Japan. Scholar license: $497/yr.

Vermont sample (free, read-only BigQuery):
{BQ}

Charles Prescott
charlesaprescottjr@gmail.com"""
            subject = f"GRID: 65K Shinto shrines — $497/yr scholar license"
        elif 'Ancient' in field or 'Roman' in field or 'Pagan' in field:
            body = f"""Dear {org},

GRID integrates 1,702 ancient sites via Pleiades: Roman Religion (720), Hellenistic (154), Mesopotamian (97), Egyptian (72), Parthian (11), Celtiberian (2). 24-faith taxonomy under Pagan. Scholar license: $497/yr.

Vermont sample (free, read-only BigQuery):
{BQ}

Charles Prescott
charlesaprescottjr@gmail.com"""
            subject = f"GRID: 1,702 ancient sites + 24-faith taxonomy — $497/yr"
        elif 'ARDA' in field or 'Congregation' in field:
            body = f"""Dear {org},

GRID is the dataset ARDA needs — 3.48M sites, 1,066 traditions, site-level not aggregate, updated continuously. Unlike the US Religion Census (every 10 years, county aggregates), this is live. Scholar license: $497/yr.

Vermont sample (free, read-only BigQuery):
{BQ}

Charles Prescott
charlesaprescottjr@gmail.com"""
            subject = f"GRID: 3.48M sites, 1,066 traditions — $497/yr scholar license"
        else:
            body = f"""Dear {org},

I saw your work and wanted to introduce GRID — 3.48M worship sites, every faith, every country, all geocoded. Individual scholar license: $497/yr. Want a copy for your research?

Vermont sample (free, read-only BigQuery):
{BQ}

Charles Prescott
charlesaprescottjr@gmail.com"""
            subject = f"GRID: 3.48M worship sites — $497/yr scholar license"

    elif pitch == "muslim":
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) is the world's most comprehensive map of Muslim worship sites — **361,077 mosques, prayer rooms, and Islamic centers across 291 countries**, each classified by tradition.

• 35 traditions: Sunni (296K), Shia (54K), Ibadi (2.8K), Sufi orders, Ahmadiyya, and more
• 6,707 mosques in the US — mapped with contact info, census demographics
• 3,178 with phone/email/website — direct outreach channel
• FEMA risk data joined to every US mosque

Use cases for Muslim organizations:
  → Relief: find every mosque in a disaster zone for food distribution
  → Finance: target high-density Muslim areas for Islamic banking
  → Halal: locate every mosque for certification outreach
  → Travel: target US mosques for Hajj/Umrah marketing
  → Advocacy: know exactly where the Muslim community lives

Vermont sample (free, read-only BigQuery):
{BQ}

Pricing from $497/yr (nonprofit). Want a free extract of mosques in your service area?

{SIG}"""
        subject = f"GRID: 361K mosques mapped globally — data for {org[:35]}"

    else:  # generic academic
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) is now available for academic licensing — 3.48M worship sites across 291 countries, fully classified by faith, tradition, and movement.

For researchers: FEMA risk enrichment, FBI crime data, Census demographics, and complete provenance tracking on every record.

Institutional pricing from $497/yr (seminary) to $997/yr (university).

Explore Vermont sample:
{BQ}

{SIG}"""
        subject = f"GRID: Institutional site license for {org[:35]}"

    print(f"[{i+1}/{len(pending)}] [Tier {tier}] {org[:40]:40s} -> {to_addr[:35]:35s}", end="", flush=True)
    try:
        send(to_addr, subject, body)
        ok += 1
        mark_sent(org)
        print(f" ✅")
    except Exception as e:
        fail += 1
        print(f" ❌ {str(e)[:60]}")

    if i < len(pending) - 1:
        time.sleep(INTERVAL)

print(f"\n{'='*60}")
print(f"DONE: {ok} sent, {fail} failed in {total_time:.1f} hours")
print(f"{'='*60}")

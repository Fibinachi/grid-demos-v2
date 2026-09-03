"""
FAITH PARTNER SENDER — Faith media (studios, streaming, broadcast, publishing)
+ Faith hunger (food banks, hunger orgs, church partnership networks)
+ Muslim organizations (relief, advocacy, finance, pilgrimage, halal).

These orgs need one thing: worship sites to partner with. GRID gives them the complete map.
"""
import json, smtplib, time, os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

MEDIA = json.load(open(OUT / "faith_media_leads.json"))
HUNGER = json.load(open(OUT / "faith_hunger_leads.json"))
MUSLIM = json.load(open(OUT / "muslim_org_leads.json"))

# Combine — all faith-based partnership sectors
all_leads = MEDIA + HUNGER + MUSLIM

# Load already sent
already = set()
for f in [SENT_LOG, OUT/"whale_sent.txt", OUT/"church_campaign_sent.txt", OUT/"jewish_sent.txt"]:
    if f.exists():
        for line in f.read_text().strip().split('\n'):
            if line.strip():
                already.add(line.strip().lower().split('|')[0].strip())

pending = [l for l in all_leads if l['email'].lower() not in already and l['org'].lower() not in already]
print(f"Faith partner targets: {len(pending)} new (of {len(all_leads)} total)")
from collections import Counter
for sector, count in Counter(l['sector'] for l in pending).most_common():
    print(f"  {sector}: {count}")

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
    org = lead['org']
    sector = lead['sector']
    sub = lead.get('sub', '')

    # Sector-specific pitch templates
    if sector in ("Relief", "Advocacy", "Finance", "Travel", "Halal", "Funeral", "Directory", "Umbrella"):
        # MUSLIM ORGS: mosque partnership / community targeting pitch
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) is the world's most comprehensive map of Muslim worship sites — **361,077 mosques, prayer rooms, and Islamic centers across 291 countries**, each classified by tradition (Sunni, Shia, Ibadi, Sufi) and fully geocoded.

For Muslim organizations, this is a map of the global Ummah that didn't exist before:

• 361K mosques worldwide — every known site, not just survey samples
• 35 traditions classified — Sunni (296K), Shia (54K), Ibadi (2.8K), Sufi orders, Ahmadiyya, Mahdavia, CRCJ, Quranist, Mahamid, Yarsan, Alevi, etc.
• 6,707 mosques in the US — mapped by city, county, tract, with contact info
• 3,178 with phone/email/website — direct outreach channel
• FEMA risk data joined to every US mosque — disaster response planning
• Census demographics for every US mosque — income, population, poverty

Use cases for Muslim organizations:
  → Relief: find every mosque in a disaster zone for food/water distribution
  → Finance: target high-density Muslim areas for Islamic banking branches
  → Halal: locate every mosque for certification outreach & restaurant placement
  → Travel: target US mosques for Hajj/Umrah marketing by city
  → Advocacy: know exactly where the Muslim community lives for voter outreach
  → Funeral: contact every mosque about burial services in each state
  → Education: find mosque spaces for weekend school programs

Pricing from $497/yr (nonprofit) to $997/yr (organization). Vermont sample free:

{ADX}

Want a free extract of mosques in your service area? I'll build it in 5 minutes.

{SIG}"""
    elif sector in ("Film Studio", "TV Network", "Streaming", "Radio"):
        # MEDIA: church partnership / screening / promotion pitch
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) is the world's most comprehensive map of religious infrastructure — 3.48M worship sites globally, 1M+ in the US. Every record classified by faith, tradition, denomination, and movement.

For media organizations targeting faith audiences through church partnerships, GRID provides what no other dataset can:

• 1M+ US churches — every congregation, not just survey samples
• Phone, email, website for 600K+ — direct contact for promotion
• FEMA risk scores — know which communities face disasters (plan your "Jesus Revolution" screenings in counties with need)
• Location by census tract, county, DMA, congressional district
• Church building proxy data — prioritize larger facilities for screenings

Use cases for faith media:
  → Route church screening DVDs only to Baptist churches in the South
  → Target "The Chosen"-compatible communities by theology (non-denom, evangelical)
  → Plan theatrical releases by church density per DMA
  → Find mega-churches for curriculum partnerships
  → Map where your audience already is — then reach them

We need distribution partners to make GRID available to faith media organizations. Pricing starts at $997/yr (single organization) or $1,997/yr for unlimited organizational use.

Buy on AWS Data Exchange (Vermont sample free):
{ADX}

{Vermont on BigQuery:}
{BQ}

Want a free dataset sample covering your target counties?

{SIG}"""
    elif sector in ("Publishing", "Curriculum"):
        # PUBLISHING: church curriculum / book distribution pitch
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) can help you target church partners for curriculum and book distribution more effectively than any church directory available.

What GRID offers your publishing team:
• 1M+ US churches with denomination classification — know exactly which churches use your curriculum line
• Phone/email/website for 600K+ — direct marketing channel
• FEMA risk enrichment — know which communities are rebuilding (new curriculum buyers)
• SBC, Lutheran, Methodist, Presbyterian, Catholic — all classified by body/synod/diocese
• Census tract demographics — income, education, population density

Your authors' next book tour could target churches in the top 50 highest-income counties with Lutheran churches — GRID makes that query in 3 seconds.

Pricing from $997/yr (publisher) to $1,997/yr (unlimited). Explore Vermont sample free:

{ADX}

{SIG}"""
    else:
        # HUNGER / FOOD BANK: church partnership pitch
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) maps every faith community in America — 1M+ churches, mosques, temples, and synagogues — each classified by denomination, with contact info and census demographics.

For hunger organizations, this means:

• **Find every potential church pantry partner in your service area** — filtered by denomination, city, county
• **Target churches in high food-insecurity census tracts** — GRID has FEMA risk data at the tract level
• **Contact denominational networks** — reach all Methodist churches in a region with one query
• **Deploy disaster food response** — know every church in a federally-declared disaster county, pre-filtered by denomination
• **600K+ phones and emails** — your field team can start calling tomorrow

Practical example: Feeding America's Chicago food bank serves 700+ church pantries. With GRID, they could find every church in Cook County without a pantry partner — and target them by denomination and size.

We're looking for distribution partners in the anti-hunger space. Pricing from $497/yr (nonprofit) to $997/yr (organization). Vermont sample free on AWS Data Exchange:

{ADX}

Need a customized extract of churches in your service area? I'll build it for free.

{SIG}"""

    subject = f"GRID dataset for {org[:40].strip()} — church partnerships"
    print(f"[{i+1}/{len(pending)}] {org[:40]:40s} | {sector:20s} -> {lead['email']:30s}", end="", flush=True)
    try:
        send(lead['email'], subject, body); ok += 1
        with open(SENT_LOG, "a") as f: f.write(f"{org}|{lead['email']}\n")
        print(f" OK")
    except Exception as e:
        fail += 1; print(f" FAIL: {str(e)[:60]}")

    if i < len(pending)-1: time.sleep(INTERVAL)

print(f"\nDone: {ok} sent, {fail} failed")

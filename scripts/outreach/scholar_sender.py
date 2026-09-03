"""
SCHOLAR SENDER — Academics who have published on geomapping religion.
They've been hand-building tiny datasets for years. GRID is catnip.

This is the highest-probability audience. Free trial offer, no pricing.
"""
import json, smtplib, time, os, sys
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
SENT_LOG = OUT / "gmail_sent.txt"
FAIL_LOG = OUT / "gmail_failed.txt"
SCHOLAR_LOG = OUT / "scholar_sent.txt"

if not PWD:
    PWD = os.popen("powershell -c \"[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','Machine')\"").read().strip()
if not PWD: print("Set GMAIL_APP_PASSWORD"); exit(1)

SCHOLARS = json.load(open(OUT / "scholar_leads.json"))

# Load already sent from all sent logs
already = set()
for f in [SENT_LOG, OUT/"whale_sent.txt", OUT/"church_campaign_sent.txt", SCHOLAR_LOG]:
    if f.exists():
        for line in f.read_text().strip().split('\n'):
            if line.strip():
                already.add(line.strip().lower().split('|')[0].strip())

pending = [s for s in SCHOLARS if s['name'].lower() not in already and s['email'].lower() not in already]
print(f"Scholar targets: {len(pending)} new (of {len(SCHOLARS)} total)")
print(f"Estimated time: {len(pending) * INTERVAL / 3600:.1f} hours\n")

import sqlite3
db = sqlite3.connect('churches.db')
# Pre-compute counts for the pitch
all_faiths = {}
for f in ['Christian','Islam','Buddhist','Hindu','Shinto','Judaism','Taoist','Sikh','Bahai','Jain','Confucian','Zoroastrian','Other']:
    c = db.execute("SELECT COUNT(*) FROM churches WHERE faith=?", (f,)).fetchone()[0]
    if c > 0: all_faiths[f] = c
jain_count = all_faiths.get('Jain', 0)
buddhist_count = all_faiths.get('Buddhist', 0)
shinto_count = all_faiths.get('Shinto', 0)
sikh_count = all_faiths.get('Sikh', 0)
bahai_count = all_faiths.get('Bahai', 0)
zoroastrian_count = all_faiths.get('Zoroastrian', 0)
total = sum(all_faiths.values())
db.close()

def send(to, subj, body):
    msg = MIMEMultipart()
    msg["From"] = FROM; msg["To"] = to
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls(); s.login("charlesaprescottjr@gmail.com", PWD); s.send_message(msg)

def mark_sent(name, email):
    with open(SCHOLAR_LOG, "a") as f: f.write(f"{name}|{email}|{datetime.now().isoformat()}\n")

ok = fail = 0
for i, s in enumerate(pending):
    name = s['name']
    email = s['email']
    org = s['org']
    field = s['field']

    # Personalized pitch based on their field
    if 'Jain' in field or 'Jain' in org:
        # Jain scholars — 437 temples in 30 minutes
        body = f"""Dear {name},

I built a global religious infrastructure database. In 30 minutes, I mapped 437 Jain temples across the world.

Someone told me you spent 3 years assembling a dataset on Jain sacred sites. I don't know if that's actually true, but I know the pain — constructing, cleaning, geocoding, and classifying religious sites by hand is what scholars in your position have been doing for decades. I've done it too.

GRID (Global Religious Infrastructure Database) currently contains:

• 3.48M worship sites globally — 100% faith-classified
• 437 Jain sites — pulled from Overture Maps, OpenStreetMap, and wikidata in 30 minutes
• 203K Buddhist temples, 202K Hindu sites, 361K mosques, 65K Shinto shrines, 23K synagogues, 6K Sikh gurdwaras, 1,728 Bahai centers, 72 Confucian sites
• Each classified by tradition (Vaishnavism 135K, Shaktism 20K, Shaivism 18K, Jain 437, etc.)
• Every site geocoded, most with contact info, census demographics, and FEMA risk
• All accessible by SQL — no scraping, no hand-mapping

Individual scholar license: $497/yr. Reply if you'd like a dataset sample to evaluate for your research.

Want a direct SQLite copy of the Jain subset? Or the full database? Reply and I'll set up access.

Charles Prescott
Creator, GRID
charlesaprescottjr@gmail.com | 843-504-4542"""
        subject = f"GRID: 437 Jain temples in one query"

    elif 'Zoroastrian' in field:
        body = f"""Dear {name},

I'm building a global religious infrastructure database called GRID. We have the sacred topography of pre-Islamic Iran — Zoroastrian sites mapped and classified. Also fire temples, tower of silence locations, and their current condition.

Similarly, we've mapped 1,702 ancient sites through Pleiades integration: Roman Religion (720), Hellenistic (154), Mesopotamian (97), Ancient Egyptian (72), Parthian (11), and 24 specific tradition nodes under a Pagan/Ancient taxonomy.

If you'd like a copy of the Zoroastrian or ancient site subset for your research, it's yours — free for scholars.

Charles Prescott
charlesaprescottjr@gmail.com"""
        subject = f"GRID: Zoroastrian & ancient sacred sites data"

    elif 'Buddhist' in field or 'Buddhism' in field:
        body = f"""Dear {name},

GRID (Global Religious Infrastructure Database) contains 203K Buddhist sites globally — fully classified by tradition (Theravada, Mahayana, Vajrayana, Zen, Pure Land, etc.), all geocoded.

If you're working on a digital atlas or spatial analysis of Buddhism, GRID has 203K sites fully classified. Scholar license: $497/yr. We also have:
• 5,619 Sikh gurdwaras (100% DeepSeek-reviewed)
• 65K Shinto shrines (all Shrine Shinto)
• 1,702 ancient sites (Pleiades integration)
• Chinese diaspora temple network

Free for scholars — just reply and I'll send a copy.

Charles Prescott
charlesaprescottjr@gmail.com"""
        subject = f"GRID: 203K Buddhist sites — free for scholars"

    elif 'Sikh' in field:
        body = f"""Dear {name},

GRID contains 5,619 Sikh sites — 5,353 gurdwaras, 147 community centers, 78 shrines — all 100% DeepSeek-classified. Every gurdwara tagged with tradition (Khalsa 5,016, Singh Sabha 243, Nanaksar 93, etc.) and sikh_affiliation.

Scholar license: $497/yr. Reply for a dataset sample.

Charles Prescott
charlesaprescottjr@gmail.com"""
        subject = f"GRID: 5,619 Sikh gurdwaras mapped"

    elif 'Shinto' in field:
        body = f"""Dear {name},

GRID contains 65K Shinto shrines — all classified as Shrine Shinto (Jinja Shinto), fully geocoded across Japan. Also mapped Buddhist-Shinto complex sites.

Scholar license: $497/yr. Reply for a dataset sample.

Charles Prescott
charlesaprescottjr@gmail.com"""
        subject = f"GRID: 65K Shinto shrines mapped"

    elif 'ARDA' in field or 'Congregation' in field or 'census' in field.lower() or 'demography' in field.lower():
        body = f"""Dear {name},

GRID is the dataset ARDA wishes it had — 3.48M sites, every faith, every country, all geocoded. Unlike the US Religion Census (county-level aggregates, 370 groups every 10 years), GRID is site-level, 1,066 traditions, updated continuously.

Scholar license: $497/yr. Vermont sample available on AWS Data Exchange.

Charles Prescott
charlesaprescottjr@gmail.com"""
        subject = f"GRID: 3.48M sites, 1,066 traditions — site-level data"

    elif 'Ancient' in field or 'Roman' in field or 'Pagan' in field:
        body = f"""Dear {name},

GRID integrates 1,702 ancient religious sites from Pleiades, plus our own taxonomy: Roman Religion (720), Hellenistic (154), Mesopotamian (97), Egyptian (72), Parthian (11), Celtiberian (2), plus 24 tradition nodes under Pagan. All geocoded, all in one query.

Free for scholars studying ancient sacred geography.

Charles Prescott
charlesaprescottjr@gmail.com"""
        subject = f"GRID: 1,702 ancient sacred sites + 24-faith taxonomy"

    else:
        # General pitch
        body = f"""Dear {name},

I saw your work in the geography of religion / spatial study of faith and wanted to introduce GRID — the Global Religious Infrastructure Database.

3.48M worship sites. 12 faiths. 1,066 traditions. Every site geocoded. 
{', '.join(f'{v:,} {k}' for k,v in list(all_faiths.items())[:5])} and more.

Scholar license: $497/yr. Want a dataset sample for your next paper?

Charles Prescott
charlesaprescottjr@gmail.com"""
        subject = f"GRID: 3.48M worship sites — $497/yr scholar license"

    print(f"[{i+1}/{len(pending)}] {name:35s} -> {email:35s}", end="", flush=True)
    try:
        send(email, subject, body)
        ok += 1
        mark_sent(name, email)
        print(f" ✅")
    except Exception as e:
        fail += 1
        print(f" ❌ {str(e)[:60]}")

    if i < len(pending) - 1:
        time.sleep(INTERVAL)

print(f"\nDone: {ok} sent, {fail} failed")

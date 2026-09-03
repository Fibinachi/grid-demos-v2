"""Diaspora government outreach — every country cares where its people worship abroad."""
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
SIG = "Charles Prescott\nCreator, GRID\ncharlesaprescottjr@gmail.com | 843-504-4542"

if not PWD: print("Set GMAIL_APP_PASSWORD"); exit(1)

DIASPORA = [
    # ═══ CHINA — Chinese shrines abroad ═══
    {"org": "China State Council - Overseas Chinese Affairs", "email": "qwhq@gqb.gov.cn", "faith": "Chinese Folk", "country": "China"},
    {"org": "Chinese Ministry of Culture & Tourism", "email": "info@mct.gov.cn", "faith": "Chinese Folk", "country": "China"},
    {"org": "Chinese Embassy - Cultural Affairs (Bangkok)", "email": "chinaembassy_th@mfa.gov.cn", "faith": "Chinese Folk", "country": "China"},

    # ═══ INDIA — diaspora department ═══
    {"org": "Ministry of External Affairs (India) - Diaspora", "email": "diaspora@mea.gov.in", "faith": "Hindu", "country": "India"},
    {"org": "Indian Council for Cultural Relations (ICCR)", "email": "info@iccr.gov.in", "faith": "Hindu", "country": "India"},
    {"org": "Indian Embassy Washington DC - Community Affairs", "email": "community@indianembassy.org", "faith": "Hindu", "country": "India"},
    {"org": "Overseas Indian Facilitation Centre", "email": "info@oifc.in", "faith": "Hindu", "country": "India"},

    # ═══ TURKIYE — Diyanet already listed, but diaspora-specific ═══
    {"org": "Ministry of Foreign Affairs (Turkiye) - Diaspora", "email": "diaspora@mfa.gov.tr", "faith": "Islam", "country": "Turkiye"},
    {"org": "YTB (Yurtdisi Turkler ve Akraba Topluluklar)", "email": "info@ytb.gov.tr", "faith": "Islam", "country": "Turkiye"},
    {"org": "Turkish Embassy Berlin - Religious Affairs", "email": "berlin@mfa.gov.tr", "faith": "Islam", "country": "Turkiye"},

    # ═══ THAILAND ═══
    {"org": "Thailand Ministry of Foreign Affairs - Diaspora", "email": "diaspora@mfa.go.th", "faith": "Buddhist", "country": "Thailand"},
    {"org": "Thailand Office of National Buddhism", "email": "info@onab.go.th", "faith": "Buddhist", "country": "Thailand"},
    {"org": "Royal Thai Embassy Washington DC", "email": "info@thaiembdc.org", "faith": "Buddhist", "country": "Thailand"},

    # ═══ VIETNAM ═══
    {"org": "Vietnam State Committee for Overseas Vietnamese", "email": "info@ucng.gov.vn", "faith": "Buddhist", "country": "Vietnam"},
    {"org": "Vietnam Ministry of Home Affairs - Religion", "email": "info@btgt.gov.vn", "faith": "Buddhist", "country": "Vietnam"},

    # ═══ PAKISTAN ═══
    {"org": "Pakistan Ministry of Religious Affairs", "email": "info@mora.gov.pk", "faith": "Islam", "country": "Pakistan"},
    {"org": "Pakistan Embassy - Community Welfare", "email": "community@pakistanembassy.org", "faith": "Islam", "country": "Pakistan"},

    # ═══ INDONESIA ═══
    {"org": "Indonesia Ministry of Religious Affairs", "email": "info@kemenag.go.id", "faith": "Islam", "country": "Indonesia"},
    {"org": "Indonesian Embassy - Community", "email": "info@kemlu.go.id", "faith": "Islam", "country": "Indonesia"},

    # ═══ BANGLADESH ═══
    {"org": "Bangladesh Ministry of Religious Affairs", "email": "info@mora.gov.bd", "faith": "Islam", "country": "Bangladesh"},

    # ═══ SRI LANKA ═══
    {"org": "Sri Lanka Ministry of Buddhasasana", "email": "info@buddhasasana.gov.lk", "faith": "Buddhist", "country": "Sri Lanka"},

    # ═══ MEXICO / LATAM (churches abroad) ═══
    {"org": "Mexico Institute of Mexicans Abroad", "email": "ime@ime.gob.mx", "faith": "Christian", "country": "Mexico"},
    {"org": "Philippines Commission on Filipinos Overseas", "email": "info@cfo.gov.ph", "faith": "Christian", "country": "Philippines"},
    {"org": "Philippines Embassy - Religious Affairs", "email": "religion@philippineembassy.org", "faith": "Christian", "country": "Philippines"},

    # ═══ NEPAL ═══
    {"org": "Nepal Ministry of Culture, Tourism & Civil Aviation", "email": "info@tourism.gov.np", "faith": "Hindu", "country": "Nepal"},
    {"org": "Nepali Embassy - Community", "email": "consular@nepalembassy.org", "faith": "Hindu", "country": "Nepal"},

    # ═══ MYANMAR ═══
    {"org": "Myanmar Ministry of Religious Affairs & Culture", "email": "info@mora.gov.mm", "faith": "Buddhist", "country": "Myanmar"},

    # ═══ SOUTH KOREA ═══
    {"org": "Korean Ministry of Foreign Affairs - Overseas Koreans", "email": "overseas@mofa.go.kr", "faith": "Christian", "country": "Korea"},

    # ═══ EUROPEAN IMMIGRATION / INTEGRATION ═══
    {"org": "Germany BAMF (Integration Research)", "email": "forschung@bamf.bund.de", "faith": "Islam", "country": "Germany"},
    {"org": "German Conference on Islam (DIK)", "email": "info@dik.bund.de", "faith": "Islam", "country": "Germany"},
    {"org": "UK Ministry of Housing, Communities & Local Gov", "email": "integration@communities.gov.uk", "faith": "Islam", "country": "UK"},
    {"org": "UK Commission on Race & Ethnic Disparities", "email": "info@racecommission.gov.uk", "faith": "Islam", "country": "UK"},
    {"org": "French Interministerial Delegation for Integration", "email": "integration@interieur.gouv.fr", "faith": "Islam", "country": "France"},
    {"org": "Netherlands Ministry of Social Affairs - Integration", "email": "integratie@minszw.nl", "faith": "Islam", "country": "Netherlands"},
    {"org": "Swedish Agency for Youth & Civil Society (MUCF)", "email": "info@mucf.se", "faith": "Islam", "country": "Sweden"},
    {"org": "Danish Ministry of Immigration & Integration", "email": "integration@uim.dk", "faith": "Islam", "country": "Denmark"},
    {"org": "Belgian Federal Migration Centre (Myria)", "email": "info@myria.be", "faith": "Islam", "country": "Belgium"},
    {"org": "Austrian Integration Fund (OIF)", "email": "info@integrationsfonds.at", "faith": "Islam", "country": "Austria"},
    {"org": "Swiss Federal Migration Commission", "email": "info@ekm.admin.ch", "faith": "Islam", "country": "Switzerland"},
    {"org": "EU Fundamental Rights Agency (FRA)", "email": "info@fra.europa.eu", "faith": "Islam", "country": "EU"},
    {"org": "EU Radicalisation Awareness Network (RAN)", "email": "ran@ec.europa.eu", "faith": "Islam", "country": "EU"},
]

# Load already sent
already = set()
for f in [SENT_LOG, OUT/"whale_sent.txt"]:
    if f.exists():
        for line in f.read_text().strip().split('\n'):
            if line.strip(): already.add(line.strip().lower())

pending = [d for d in DIASPORA if d['email'].lower() not in already]
print(f"Diaspora targets: {len(pending)} new (of {len(DIASPORA)} total)")

from collections import Counter
for c, n in Counter(d['country'] for d in pending).most_common():
    print(f"  {c}: {n}")

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
for i, d in enumerate(pending):
    # Build country-specific diaspora stats
    country = d['country']
    if country in ('Germany','UK','France','Netherlands','Sweden','Denmark','Belgium','Austria','Switzerland'):
        # European integration agencies — map immigrant religious communities
        body = f"""Dear {d['org']},

GRID maps every mosque, temple, and church maintained by immigrant communities across Europe — the most complete dataset on religious infrastructure in the European diaspora.

For example:
• 2,869 mosques in Germany serving Turkish, Arab, and Balkan communities
• 2,788 mosques in the UK serving South Asian and Arab communities  
• 1,491 mosques in France serving North African communities
• 783 mosques in the Netherlands serving Turkish and Moroccan communities
• 5,242 Hindu temples in the US (and thousands more across Europe)

GRID covers all these communities globally — each site classified by tradition, geocoded to GPS, and enriched with FEMA risk scores. This is the data you need for religious integration research, community mapping, and counter-extremism programs.

Buy the full dataset on AWS Data Exchange:
{ADX}

Happy to provide a Europe-specific extract for your integration work.

{SIG}"""
    else:
        body = f"""Dear {d['org']},

GRID maps every worship site of {country}'s diaspora worldwide — temples, mosques, churches, and shrines maintained by {country}'s expatriate communities, each geocoded and classified by tradition.

For example:
• 796 Chinese folk shrines in Thailand alone
• 5,242 Hindu temples in the United States
• 2,869 Turkish mosques in Germany
• 906 Thai Buddhist temples in the US

GRID covers all these communities globally — no other dataset maps diaspora religious infrastructure at this scale. Every site has GPS coordinates, tradition classification, and FEMA risk scores.

Buy the full dataset on AWS Data Exchange:
{ADX}

Happy to provide a custom extract for {country}'s global diaspora specifically.

{SIG}"""

    subject = f"GRID: {d['country']}'s religious diaspora — mapped globally"
    
    print(f"[{i+1}/{len(pending)}] {d['org'][:45]:45s} -> {d['email']:30s}", end="", flush=True)
    try:
        send(d['email'], subject, body); ok += 1
        with open(SENT_LOG, "a") as f: f.write(f"{d['org']}|{d['email']}\n")
        print(f" OK")
    except Exception as e:
        fail += 1; print(f" FAIL: {str(e)[:60]}")
    if i < len(pending)-1: time.sleep(INTERVAL)

print(f"\nDone: {ok} sent, {fail} failed")

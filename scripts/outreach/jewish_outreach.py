"""
JEWISH ORG OUTREACH — GRID has the most complete dataset on Jewish life in the modern world.
26,632 entries, 98% GPS, 12 canonical traditions, 3,012 Chabad centers, 54 countries.
Pitches: data licensing, community planning, genealogy, security, research.
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
JEWISH_SENT = OUT / "jewish_sent.txt"
FAIL_LOG = OUT / "gmail_failed.txt"
ADX = "https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084"
SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
charlesaprescottjr@gmail.com | 843-504-4542"""

if not PWD: print("Set GMAIL_APP_PASSWORD"); exit(1)

JEWISH_ORGS = [
    # ═══ FOUNDATIONS (billions in assets) ═══
    {"org": "The David Berg Foundation", "email": "info@bergfoundation.org", "sector": "Foundation"},
    {"org": "The Harry and Jeanette Weinberg Foundation", "email": "info@hjweinberg.org", "sector": "Foundation"},
    {"org": "The Samuel Bronfman Foundation", "email": "info@bronfmanfoundation.org", "sector": "Foundation"},
    {"org": "The Mandel Foundation", "email": "info@mandelfoundation.org", "sector": "Foundation"},
    {"org": "The Jim Joseph Foundation", "email": "info@jimjosephfoundation.org", "sector": "Foundation"},
    {"org": "The AVI CHAI Foundation", "email": "info@avichai.org", "sector": "Foundation"},
    {"org": "The Wexner Foundation", "email": "info@wexnerfoundation.org", "sector": "Foundation"},
    {"org": "The Charles and Lynn Schusterman Foundation", "email": "info@schusterman.org", "sector": "Foundation"},
    {"org": "The Rose and Hal Israel Foundation", "email": "info@israelfoundation.org", "sector": "Foundation"},
    {"org": "Ronald S. Lauder Foundation", "email": "info@lauderfoundation.com", "sector": "Foundation"},
    {"org": "Maimonides Fund", "email": "info@maimonidesfund.org", "sector": "Foundation"},
    {"org": "The Gottesman Fund", "email": "info@gottesmanfund.org", "sector": "Foundation"},
    {"org": "The Tikvah Fund", "email": "info@tikvahfund.org", "sector": "Foundation"},

    # ═══ UMBRELLA / COMMUNITY ORGS ═══
    {"org": "Jewish Federations of North America", "email": "info@jewishfederations.org", "sector": "Umbrella"},
    {"org": "URJ (Union for Reform Judaism)", "email": "info@urj.org", "sector": "Umbrella"},
    {"org": "USCJ (United Synagogue of Conservative Judaism)", "email": "info@uscj.org", "sector": "Umbrella"},
    {"org": "OU (Orthodox Union)", "email": "info@ou.org", "sector": "Umbrella"},
    {"org": "Chabad Lubavitch World HQ", "email": "info@chabad.org", "sector": "Umbrella"},
    {"org": "Rabbinical Council of America", "email": "info@rabbis.org", "sector": "Umbrella"},
    {"org": "Central Conference of American Rabbis", "email": "info@ccarnet.org", "sector": "Umbrella"},
    {"org": "Rabbinical Assembly", "email": "info@rabbinicalassembly.org", "sector": "Umbrella"},
    {"org": "World Jewish Congress", "email": "info@worldjewishcongress.org", "sector": "Umbrella"},
    {"org": "Jewish Agency for Israel", "email": "info@jewishagency.org", "sector": "Umbrella"},
    {"org": "American Jewish Joint Distribution Committee", "email": "info@jdc.org", "sector": "Umbrella"},
    {"org": "Jewish Federations - Data", "email": "data@jewishfederations.org", "sector": "Umbrella"},
    {"org": "BJC (Board of Jewish Communities)", "email": "info@thebjc.org", "sector": "Umbrella"},

    # ═══ RESEARCH / THINK TANKS ═══
    {"org": "Cohen Center for Modern Jewish Studies (Brandeis)", "email": "cmjs@brandeis.edu", "sector": "Research"},
    {"org": "Jewish People Policy Institute", "email": "info@jppi.org.il", "sector": "Research"},
    {"org": "Berman Jewish DataBank", "email": "info@jewishdatabank.org", "sector": "Research"},
    {"org": "Pew Research - Religion", "email": "info@pewresearch.org", "sector": "Research"},
    {"org": "Pew-Templeton Global Religious Futures", "email": "info@globalreligiousfutures.org", "sector": "Research"},
    {"org": "Sulam Center for Jewish Studies", "email": "info@sulamcenter.org", "sector": "Research"},
    {"org": "Herbert D. Katz Center for Advanced Judaic Studies", "email": "katzcenter@upenn.edu", "sector": "Academic"},
    {"org": "Yad Vashem - Research", "email": "research@yadvashem.org.il", "sector": "Research"},

    # ═══ GENEALOGY / HERITAGE ═══
    {"org": "JewishGen", "email": "info@jewishgen.org", "sector": "Genealogy"},
    {"org": "Ancestry - Jewish Records", "email": "jewishrecords@ancestry.com", "sector": "Genealogy"},
    {"org": "MyHeritage - Jewish", "email": "jewish@myheritage.com", "sector": "Genealogy"},
    {"org": "Museum of Jewish Heritage NYC", "email": "info@mjhnyc.org", "sector": "Museum"},
    {"org": "US Holocaust Memorial Museum", "email": "research@ushmm.org", "sector": "Museum"},
    {"org": "The Jewish Museum (Berlin)", "email": "info@jmberlin.de", "sector": "Museum"},
    {"org": "Polin Museum (Warsaw)", "email": "info@polin.pl", "sector": "Museum"},
    {"org": "ANU - Museum of the Jewish People (Tel Aviv)", "email": "info@anumuseum.org.il", "sector": "Museum"},
    {"org": "Beit Hatfutsot", "email": "info@bh.org.il", "sector": "Museum"},

    # ═══ MEDIA ═══
    {"org": "The Forward", "email": "newsdesk@forward.com", "sector": "Media"},
    {"org": "Tablet Magazine", "email": "info@tabletmag.com", "sector": "Media"},
    {"org": "The Times of Israel", "email": "news@timesofisrael.com", "sector": "Media"},
    {"org": "Haaretz English", "email": "english@haaretz.co.il", "sector": "Media"},
    {"org": "The Jerusalem Post", "email": "news@jpost.com", "sector": "Media"},
    {"org": "Mosaic Magazine", "email": "info@mosaicmagazine.com", "sector": "Media"},
    {"org": "Algemeiner", "email": "news@algemeiner.com", "sector": "Media"},

    # ═══ SECURITY / COMMUNITY ═══
    {"org": "Secure Community Network (SCN)", "email": "info@securecommunitynetwork.org", "sector": "Security"},
    {"org": "Community Security Trust (UK)", "email": "info@cst.org.uk", "sector": "Security"},
    {"org": "ADL - Data", "email": "data@adl.org", "sector": "Security"},
    {"org": "Jewish Community Watch", "email": "info@jewishcommunitywatch.org", "sector": "Security"},
    {"org": "Sefaria - Data", "email": "data@sefaria.org", "sector": "Tech/Jewish"},
    {"org": "Hillel International", "email": "info@hillel.org", "sector": "Education"},
    {"org": "Birthright Israel", "email": "info@birthrightisrael.com", "sector": "Education"},

    # ═══ JEWISH GENEALOGY / CEMETERY ═══
    {"org": "Jewish Cemetery Association", "email": "info@jewishcemetery.org", "sector": "Cemetery"},
    {"org": "European Jewish Cemeteries Initiative", "email": "info@esjf-cemetery.org", "sector": "Cemetery"},
    {"org": "JewishGen - KehilaLinks", "email": "kehilalinks@jewishgen.org", "sector": "Genealogy"},
]

# Deduplicate
seen = set()
unique = []
for o in JEWISH_ORGS:
    if o['email'] not in seen:
        seen.add(o['email'])
        unique.append(o)
print(f"Jewish orgs: {len(unique)} unique")

# Load already sent
already = set()
for log in [OUT/"gmail_sent.txt", OUT/"jewish_sent.txt"]:
    if log.exists():
        for line in log.read_text().strip().split('\n'):
            if line.strip():
                already.add(line.strip().lower())

emails = [o for o in unique if o['email'].lower() not in already]
print(f"Not yet sent: {len(emails)}")
from collections import Counter
for s, n in Counter(o['sector'] for o in emails).most_common():
    print(f"  {s}: {n}")

# ── Pitch ──
BODY = f"""Hi {{{{org}}}} team,

GRID (Global Religious Infrastructure Database) contains the most complete dataset on Jewish religious infrastructure in the modern world — 26,632 synagogues, Chabad houses, yeshivas, cemeteries, and community centers across 54 countries, each classified by tradition and geocoded.

**Why this is unique:**
- **26,632 Jewish entries** worldwide — fully cleaned, 0 problematic records
- **98% GPS coverage** — every synagogue, Chabad, yeshiva mapped
- **3,012 Chabad centers** with full hierarchy (HQ > regional > local)
- **12 canonical traditions**: Rabbinic, Orthodox, Chabad, Reform, Conservative, Sephardic, Hasidic, Yeshiva, Reconstructionist, Humanistic, Karaite, Mizrahi
- **AI-verified classification** — every entry tradition-classified with provenance
- **54 countries** — comprehensive coverage from the US (16,630) to Poland (787) to Ukraine (390) to Morocco (125)
- **Hierarchy data**: 2,885 Chabad relationships, synagogue-to-movement links

**Top US states**: NY (6,346), NJ (1,748), CA (1,474), FL (901), MA (470), PA (442), IL (427), MD (337), OH (296), CT (233)

**Contacts**: 3,345 phone numbers, 4,029 websites, 279 emails

**Buy on AWS Data Exchange (Vermont sample free):**
{ADX}

**Explore Vermont sample (read-only):**
https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table

Happy to discuss custom extracts, research licenses, or enterprise access.

{SIG}"""

SUBJECT = "GRID: The most complete Jewish infrastructure dataset — 26,632 entries, 54 countries"

def send_email(to, subj, body):
    msg = MIMEMultipart()
    msg["From"] = FROM; msg["To"] = to
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls(); s.login("charlesaprescottjr@gmail.com", PWD); s.send_message(msg)

ok = fail = 0
for i, o in enumerate(emails):
    body = BODY.replace('{{org}}', o['org'])
    print(f"[{i+1}/{len(emails)}] {o['org']:45s} -> {o['email']:35s}", end="", flush=True)
    try:
        send_email(o['email'], SUBJECT, body); ok += 1
        with open(OUT/"jewish_sent.txt", "a") as f: f.write(f"{o['org']}|{o['email']}\n")
        print(f" OK ({ok}/{fail})")
    except Exception as e:
        fail += 1; print(f" FAIL: {str(e)[:60]}")
    if i < len(emails)-1:
        print(f" {INTERVAL//60}m...", end="", flush=True); time.sleep(INTERVAL)

print(f"\n\nDone: {ok} sent, {fail} failed")

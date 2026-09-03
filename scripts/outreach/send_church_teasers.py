"""
GRID Church-Direct Campaign — Teaser Email Sender
Sends personalized teaser emails to US churches with known email addresses.
Includes 3-4 personalized community stats + CTA to buy full $250 report.

Rate: 1 per 12 seconds = 300/hr = safe under Gmail's 500/hr limit
"""
import sqlite3, smtplib, time, os, sys, random
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
REPLY_TO = "charlesaprescott@outlook.com"
BUY_LINK = "https://buymeacoffee.com/CharlesPrescott"
FULL_REPORT_PRICE = "$250"

PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    print("ERROR: Set GMAIL_APP_PASSWORD")
    sys.exit(1)

SENT_LOG = Path("outputs/outreach/church_campaign_sent.txt")
FAIL_LOG = Path("outputs/outreach/church_campaign_failed.txt")
SENT_LOG.parent.mkdir(parents=True, exist_ok=True)

# Load already-sent church IDs
already_sent = set()
if SENT_LOG.exists():
    already_sent = set(int(x) for x in SENT_LOG.read_text().strip().split("\n") if x.strip())

# ============================================================
# LOAD CHURCHES TO SEND
# ============================================================
DB = sqlite3.connect("E:/grid/churches.db")
DB.row_factory = sqlite3.Row

# US churches with email, not yet sent, with enrichment data
churches = DB.execute("""
    SELECT c.id, c.name, c.city, c.state, c.tradition,
           (SELECT value FROM church_contact_values WHERE church_id=c.id AND contact_type='email' LIMIT 1) as email,
           ce.county_name, ce.county_total_pop, ce.county_median_hh_income,
           ce.county_poverty_rate, ce.county_bachelors_25_64,
           ce.county_median_age, ce.rucc_description,
           cb.broadband_pct,
           ca.acs_median_home_value
    FROM churches c
    LEFT JOIN church_enrichment ce ON ce.church_id = c.id
    LEFT JOIN church_broadband cb ON cb.church_id = c.id
    LEFT JOIN church_census_us ca ON ca.church_id = c.id
    WHERE c.country = 'US'
      AND c.id IN (SELECT church_id FROM church_contact_values WHERE contact_type='email')
      AND c.id NOT IN ({})
    ORDER BY c.state, c.city
    LIMIT 500
""".format(",".join(str(x) for x in already_sent) if already_sent else "0"))

church_list = list(churches)
print(f"Loaded {len(church_list)} churches to send")
print(f"Already sent: {len(already_sent)}")

if not church_list:
    print("All churches have been sent! Generate more leads or reset sent log.")
    DB.close()
    sys.exit(0)

# ============================================================
# TEASER EMAIL TEMPLATE
# ============================================================
def build_teaser(c):
    """Build personalized teaser email for a church."""
    name = c["name"].title() if c["name"] else "Church Leader"
    city = c["city"] or "your community"
    state = c["state"] or ""
    tradition = c["tradition"] or "Christian"
    county = c["county_name"] or "your county"
    
    # Build 3 compelling stats
    stats = []
    if c["county_total_pop"]:
        pop_str = f"{c['county_total_pop']:,.0f}" if c["county_total_pop"] >= 1000 else str(int(c["county_total_pop"]))
        stats.append(f"📊 **Population**: {pop_str} people live in {county}")
    if c["county_median_hh_income"]:
        stats.append(f"💰 **Median household income**: ${c['county_median_hh_income']:,.0f}")
    if c["county_poverty_rate"] is not None:
        stats.append(f"🏠 **Poverty rate**: {c['county_poverty_rate']:.1f}%")
    if c["county_bachelors_25_64"] is not None:
        stats.append(f"🎓 **College graduates**: {c['county_bachelors_25_64']:.1f}%")
    if c["broadband_pct"] is not None:
        stats.append(f"🌐 **Broadband access**: {c['broadband_pct']:.1f}% of households")
    if c["county_median_age"] is not None:
        stats.append(f"👥 **Median age**: {c['county_median_age']:.0f} years")
    if c["rucc_description"]:
        stats.append(f"🏙️ **Community type**: {c['rucc_description']}")
    
    # Pick 3-4 most interesting stats
    selected = stats[:4]
    stats_html = "\n".join(selected)
    
    # City-specific intro
    location_line = f"{city}, {state}" if state else city
    
    subject = f"📊 Community Snapshot for {name} — {location_line}"

    body = f"""Hi {name},

I put together a quick community snapshot for your church in {location_line}. As someone serving {tradition} congregations, I thought you'd find this useful for outreach planning:

{stats_html}

This is a preview from the **GRID Community Intelligence Report** — a data-rich analysis built from Census ACS data, FCC broadband maps, voting records, and religious infrastructure mapping.

The full {FULL_REPORT_PRICE} report includes:

• **Complete demographic profile** of your surrounding community
• **Religious landscape map** — every church, mosque, temple, and synagogue near you
• **Outreach opportunity heatmap** — where are the underserved populations?
• **Political & cultural landscape** — voting patterns 2016-2024
• **Broadband & technology access** — how reachable is your community online?
• **Peer comparison** — how does your area compare to similar churches in your denomination?

👉 **Get the full report here**: {BUY_LINK}

After purchase, I'll email you the complete report within 24 hours.

This is data that grant writers, outreach pastors, and church planters use to make smarter decisions about where and how to serve.

Blessings,

Charles Prescott
Creator, GRID Community Intelligence
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com

P.S. If you'd like to see a specific data point about {city} before purchasing, just reply and ask — I'm happy to share a custom preview."""
    
    return subject, body


# ============================================================
# SEND LOOP
# ============================================================
INTERVAL = 12  # seconds between sends (300/hr, safe under 500/hr Gmail limit)
ok = fail = 0

for i, c in enumerate(church_list):
    to_addr = c["email"]
    if not to_addr or "@" not in to_addr:
        continue
    
    subject, body = build_teaser(c)
    
    print(f"[{i+1}/{len(church_list)}] {c['name'][:45]} -> {to_addr[:45]}")
    
    msg = MIMEMultipart()
    msg["From"] = FROM
    msg["To"] = to_addr
    msg["Reply-To"] = REPLY_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login("charlesaprescottjr@gmail.com", PWD)
            s.send_message(msg)
        ok += 1
        with open(SENT_LOG, "a") as sf:
            sf.write(f"{c['id']}\n")
        print(f"  SENT ({ok} ok, {fail} fail)")
    except Exception as e:
        fail += 1
        with open(FAIL_LOG, "a") as ff:
            ff.write(f"{c['id']},{c['email']},{str(e)[:100]}\n")
        print(f"  FAIL: {e}")
    
    if i < len(church_list) - 1:
        time.sleep(INTERVAL)

print(f"\n=== DONE ===")
print(f"Sent: {ok} | Failed: {fail}")
print(f"Total sent to date: {len(already_sent) + ok}")
print(f"To send more, run again — it will pick up where it left off.")

DB.close()

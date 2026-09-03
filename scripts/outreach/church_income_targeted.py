"""
TARGETED CHURCH OUTREACH — $250 disaster risk reports.
Prioritizes churches in high-income counties using ACS income data.
Runs at 1 per 14 min (~100/day) in gaps between whale emails.
"""
import json, smtplib, sqlite3, time, os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
PWD = os.environ.get("GMAIL_APP_PASSWORD")
INTERVAL = 840  # 14 min = ~100/day
OUT = Path("outputs/outreach")
CHURCH_SENT = OUT / "church_campaign_sent.txt"
FAIL_LOG = OUT / "gmail_failed.txt"
ADX = "https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084"

SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
charlesaprescottjr@gmail.com | 843-504-4542"""

if not PWD:
    print("Set GMAIL_APP_PASSWORD"); exit(1)

# ── Load priority churches from DB ──
print("Loading prioritized churches...")
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Churches with email + GPS + county_fips, joined to ACS income data
# Exclude Catholic/Anglican/Orthodox (they buy at diocese level)
# Prioritize by median_hh_income DESC
rows = list(db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.county, cv.value as email,
           c.latitude, c.longitude, c.county_fips_5,
           a.median_hh_income, a.poverty_rate, a.median_home_value
    FROM churches c
    JOIN church_contact_values cv ON cv.church_id = c.id AND cv.contact_type = 'email'
    LEFT JOIN county_census_us a ON a.county_fips = c.county_fips_5
    WHERE c.country = 'US'
      AND cv.value LIKE '%@%'
      AND c.latitude IS NOT NULL
      AND c.county_fips_5 IS NOT NULL
      AND (c.tradition IS NULL OR (
          c.tradition NOT LIKE '%Catholic%'
          AND c.tradition NOT LIKE '%Anglican%'
          AND c.tradition NOT LIKE '%Episcopal%'
          AND c.tradition NOT LIKE '%Orthodox%'
      ))
    ORDER BY a.median_hh_income DESC NULLS LAST
"""))
db.close()
print(f"  {len(rows):,} prioritized churches (highest income first)")

# Load already sent
already = set()
if CHURCH_SENT.exists():
    for line in CHURCH_SENT.read_text().strip().split('\n'):
        if line.strip():
            already.add(line.strip())

emails = [r for r in rows if str(r['id']) not in already]
print(f"  Not yet sent: {len(emails):,}")

if not emails:
    print("All done!"); exit(0)

# Income stats for top tier
top10 = emails[:10]
incomes = [r['median_hh_income'] for r in top10 if r['median_hh_income']]
print(f"  Top 10 income range: ${min(incomes):,.0f} - ${max(incomes):,.0f}" if incomes else "  No income data")

# ── Email body ──
def make_body(church):
    income = church['median_hh_income']
    income_line = ""
    if income:
        tier = "Very High" if income > 100000 else "High" if income > 75000 else "Upper-Middle" if income > 55000 else "Middle" if income > 40000 else "Lower-Middle"
        income_line = f"\nYour area's median household income: ${income:,.0f} ({tier})"

    return f"""Pastor,

I run GRID — the Global Religious Infrastructure Database. We map every church in America and just integrated FEMA's National Risk Index (v1.20, Dec 2025).

Your church: {church['name']}
Location: {church['city']}, {church['state']}{income_line}

Here's the thing most pastors don't realize: FEMA scores every census tract in America for 18 natural hazards. Your church sits in one of those tracts, and FEMA has already calculated your risk for hurricane, tornado, flood, wildfire, earthquake, winter storm, and more.

I can pull your church's COMPLETE FEMA risk profile for $250 — a one-time Community Intelligence Report covering:
• All 18 hazard risk scores (with national percentiles)
• Your Expected Annual Loss (EAL) in dollars
• Your Social Vulnerability Index (how at-risk your congregation is)
• Your Community Resilience score (how well your area bounces back)
• Comparable churches in your county

This is the same data insurance companies use to price your policy. Churches are the #1 emergency shelter in most communities — you need to know what FEMA says about your building.

Reply "REPORT" and I'll send you the custom report link. $250, one-time, no subscription.

You can also explore the full Vermont sample dataset (free, read-only):
{BQ if 'BQ' in dir() else 'https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table'}

Or buy the full dataset on AWS:
{ADX}

{SIG}

P.S. — Churches in high-risk zones pay more for insurance. Knowing your FEMA score helps you negotiate."""

BQ_LINK = "https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table"

SUBJECT_TEMPLATE = "Your church's FEMA disaster risk profile — $250 report"

# ── Send loop ──
def send_email(to_addr, subject, body):
    msg = MIMEMultipart()
    msg["From"] = FROM
    msg["To"] = to_addr
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls()
        s.login("charlesaprescottjr@gmail.com", PWD)
        s.send_message(msg)

ok = fail = 0
for i, church in enumerate(emails):
    # Update subject with church name and income tier
    tier = "Premium" if church['median_hh_income'] and church['median_hh_income'] > 75000 else "Standard"
    subject = f"FEMA risk report for {church['name'][:30]} ({tier})"

    body = make_body(church)
    
    print(f"[{i+1}/{len(emails)}] {church['name'][:35]:35s} -> {church['email']:35s} ${church['median_hh_income'] or 0:>8,.0f}", end="", flush=True)
    
    try:
        send_email(church['email'], subject, body)
        ok += 1
        with open(CHURCH_SENT, "a") as f:
            f.write(f"{church['id']}\n")
        print(f" OK ({ok}/{fail})")
    except Exception as e:
        fail += 1
        print(f" FAIL: {str(e)[:60]}")
        with open(FAIL_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()},{church['id']},{church['email']},{e}\n")

    if i < len(emails) - 1:
        mins = INTERVAL // 60
        print(f"  Next in {mins}min...", end="", flush=True)
        time.sleep(INTERVAL)

print(f"\n\nDone: {ok} sent, {fail} failed")

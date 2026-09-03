"""Send a real church teaser — with full enrichment — to self."""
import smtplib, sqlite3, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD: print("Set GMAIL_APP_PASSWORD"); exit(1)

db = sqlite3.connect("E:/grid/churches.db")
db.row_factory = sqlite3.Row

# Find a church with FULL enrichment data
c = db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.tradition, c.address,
           ca.acs_median_income, ca.acs_total_pop, ca.acs_poverty_rate,
           ca.acs_median_home_value, ca.acs_median_age,
           ca.acs_bachelors_count, ca.acs_masters_count,
           ce.rucc_description, ce.county_name,
           cb.broadband_pct,
           (SELECT COUNT(*) FROM churches c2 WHERE c2.city=c.city AND c2.state=c.state AND c2.id!=c.id) as nearby_churches,
           (SELECT COUNT(*) FROM churches c2 WHERE c2.city=c.city AND c2.state=c.state AND c2.faith!=c.faith AND c2.id!=c.id) as other_faith
    FROM churches c
    JOIN church_census_us ca ON ca.church_id = c.id
    LEFT JOIN church_enrichment ce ON ce.church_id = c.id
    LEFT JOIN church_broadband cb ON cb.church_id = c.id
    WHERE c.country = 'US'
      AND c.id IN (SELECT church_id FROM church_contact_values WHERE contact_type = 'email')
      AND ca.acs_median_income > 0
      AND c.tradition LIKE '%Baptist%'
      AND c.city != ''
    ORDER BY RANDOM() LIMIT 1
""").fetchone()

SIG = """Charles Prescott
Creator, GRID Community Intelligence
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com"""

name = c["name"]
city = c["city"]
state = c["state"]
tradition = c["tradition"]
location = f"{city}, {state}"
county = c["county_name"] or "your county"
nearby = c["nearby_churches"]
other_faith = c["other_faith"]

income_str = f"${c['acs_median_income']:,.0f}"
pop_str = f"{c['acs_total_pop']:,.0f}"
poverty_str = f"{c['acs_poverty_rate']*100:.1f}%"
home_str = f"${c['acs_median_home_value']:,.0f}"
age_str = f"{c['acs_median_age']:.0f}"
rucc = c["rucc_description"] or "Metropolitan area"
bb_str = f"{c['broadband_pct']:.1f}%" if c["broadband_pct"] else "85%"
edu_pct = f"{(c['acs_bachelors_count']+c['acs_masters_count'])/c['acs_total_pop']*100:.0f}%" if c['acs_total_pop'] and c['acs_bachelors_count'] else "varies"

subject = f"📊 Community Snapshot for {name} — {location}"

body = f"""Hi {name},

I put together a quick community intelligence snapshot for your church in {location} ({county}):

📊 Median household income: {income_str}
🏠 Poverty rate: {poverty_str} of your neighbors live below the poverty line
🏡 Median home value: {home_str}
🎓 College-educated: {edu_pct} of adults hold a bachelor's or higher
👤 Median age: {age_str} years
🌐 Broadband access: {bb_str} of households have high-speed internet
🏙️ Community type: {rucc}
⛪ Religious landscape: {nearby} worship sites in {city} — {other_faith} are non-{tradition}

This is a preview from the GRID Community Intelligence Report — a $250 data-rich analysis built from:

• Census ACS tract-level demographics
• FCC broadband availability maps
• USDA rural/urban classifications
• 2024 election results by precinct
• Complete religious infrastructure mapping

The full report includes religious landscape maps, outreach opportunity heatmaps, peer comparisons against similar churches, and strategic recommendations for grant writing and community engagement.

👉 Get your full report: https://buymeacoffee.com/CharlesPrescott

After purchase, I'll email your complete custom report within 24 hours.

Blessings,

{SIG}

P.S. If you have a specific question about {city} before purchasing — like where the nearest food desert is, or which neighborhoods lack broadband — just reply and I'll answer."""

msg = MIMEMultipart()
msg["From"] = "Charles Prescott <charlesaprescottjr@gmail.com>"
msg["To"] = "charlesaprescottjr@gmail.com"
msg["Reply-To"] = "charlesaprescott@outlook.com"
msg["Subject"] = f"TEST: {subject}"
msg.attach(MIMEText(body, "plain"))

with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
    s.starttls()
    s.login("charlesaprescottjr@gmail.com", PWD)
    s.send_message(msg)

print(f"✅ SENT to self!")
print(f"   Church: {name} ({tradition})")
print(f"   Location: {location} ({county})")
print(f"   Income: {income_str} | Poverty: {poverty_str} | Homes: {home_str}")
print(f"   Nearby: {nearby} churches ({other_faith} other faith)")
print(f"   Broadband: {bb_str} | Type: {rucc}")
print()
print("Check Gmail inbox for the test email.")
db.close()

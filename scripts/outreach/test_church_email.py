"""Send a test church teaser email to self for review."""
import smtplib, sqlite3, os, random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    print("Set GMAIL_APP_PASSWORD"); exit(1)

db = sqlite3.connect("E:/grid/churches.db")
db.row_factory = sqlite3.Row

# Get a random church with enrichment data
c = db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.tradition,
           ca.acs_median_income, ca.acs_total_pop, ca.acs_poverty_rate,
           ca.acs_median_home_value, ca.acs_median_age,
           ce.rucc_description, cb.broadband_pct
    FROM churches c
    LEFT JOIN church_census_us ca ON ca.church_id = c.id
    LEFT JOIN church_enrichment ce ON ce.church_id = c.id
    LEFT JOIN church_broadband cb ON cb.church_id = c.id
    WHERE c.country = 'US'
      AND c.id IN (SELECT church_id FROM church_contact_values WHERE contact_type = 'email')
    ORDER BY RANDOM() LIMIT 1
""").fetchone()

SIG = """Charles Prescott
Creator, GRID Community Intelligence
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com"""

name = c["name"]
city = c["city"] or "your area"
state = c["state"] or ""
location = f"{city}, {state}" if state else city
income_str = f"${c['acs_median_income']:,.0f}" if c["acs_median_income"] else "varies"
pop_str = f"{c['acs_total_pop']:,.0f}" if c["acs_total_pop"] else "varies"
poverty_str = f"{c['acs_poverty_rate']:.1f}%" if c["acs_poverty_rate"] else "varies"
home_str = f"${c['acs_median_home_value']:,.0f}" if c["acs_median_home_value"] else "varies"
age_str = f"{c['acs_median_age']:.0f}" if c["acs_median_age"] else "varies"
rucc = c["rucc_description"] or "varies"
bb_str = f"{c['broadband_pct']:.1f}%" if c["broadband_pct"] else "varies"

subject = f"📊 Community Snapshot for {name} — {location}"

body = f"""Hi {name},

I put together a quick community snapshot for your church in {location}:

📊 Neighborhood median income: {income_str}
👥 Area population: {pop_str}
🏠 Poverty rate: {poverty_str}
🏡 Median home value: {home_str}
👤 Median age: {age_str}
🌐 Broadband access: {bb_str}
🏙️ Community type: {rucc}

This is a preview from the GRID Community Intelligence Report — built from Census ACS data, FCC broadband maps, and religious infrastructure mapping.

The full $250 report includes:

• Complete demographic profile of your surrounding community
• Religious landscape map — every church, mosque, temple, and synagogue near you
• Outreach opportunity heatmap — where are the underserved populations?
• Political & cultural landscape — voting patterns 2016-2024
• Broadband & technology access — how reachable is your community online?
• Peer comparison — how does your area compare to similar churches in your denomination?

👉 Get the full report: https://buymeacoffee.com/CharlesPrescott

After purchase, I'll email your complete report within 24 hours.

Blessings,

{SIG}

P.S. Reply with any specific data question about {city} — happy to share a custom preview."""

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

print(f"✅ TEST SENT!")
print(f"   Church: {name}")
print(f"   Location: {location}")
print(f"   Tradition: {c['tradition']}")
print(f"   Income: {income_str} | Pop: {pop_str} | Poverty: {poverty_str}")
print(f"   Home: {home_str} | Age: {age_str} | Broadband: {bb_str} | Type: {rucc}")
print()
print("Check your Gmail inbox. Reply with any changes needed.")
db.close()

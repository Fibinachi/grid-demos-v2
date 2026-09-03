"""Send Data Axle pitch email to Ben Weeks with BQ links + visualizations."""
import smtplib, os, sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    print("Set GMAIL_APP_PASSWORD first")
    sys.exit(1)

BQ_BASE = "https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure"

body = """Hi Ben,

Kevin Dunn at Salesgenie suggested I reach out to you about Data Axle licensing GRID, the Global Religious Infrastructure Database.

GRID is the world's most comprehensive religious infrastructure dataset — 3.4 million worship sites across 291 countries. I've set up three live BigQuery demo slices so you can explore the data directly:

VERMONT (2,456 records) — US rural/suburban slice:
  {bq}/demo_vermont&page=table

NORTHWEST TERRITORIES (117 records) — Remote Canada:
  {bq}/demo_northwest_territories&page=table

TAMIL NADU, INDIA (28,356 records) — Dense international:
  {bq}/demo_tamil_nadu&page=table

What makes GRID different from your current church list:

• 2.9× more US churches: 1.02M vs ~350K in your current product
• 2.4M international churches — a market you currently have zero coverage in
• 96% GPS coverage with Census tract income, poverty, and home value data
• 301,814 organizational hierarchy rows across 7 denominations (who reports to whom)
• Full faith classification: 12 faiths × 206 traditions × 303 movements
• Provenance-tracked: every record has a source trail

I've also attached preview maps showing what the data looks like visualized:
— Church income heatmap: every dot colored by neighborhood wealth
— Denominational dominance: which tradition controls each US county
— Church density: where the underserved markets are
— Global faith distribution: dominant religion by country

The business case: your church product is ~350K US-only records. GRID gives you 10× that with international coverage and enrichment layers your competitors don't have. At your retail pricing, that's a $500K–$1M revenue opportunity.

I'm looking for a data licensing partner. Happy to discuss pricing and terms — I'm at 843-504-4542.

Best,
Charles Prescott
GRID — Global Religious Infrastructure Database
charlesaprescottjr@gmail.com
843-504-4542
""".format(bq=BQ_BASE)

msg = MIMEMultipart()
msg["From"] = "Charles Prescott <charlesaprescottjr@gmail.com>"
msg["To"] = "ben.weeks@data-axle.com"
msg["Reply-To"] = "charlesaprescott@outlook.com"
msg["Subject"] = "GRID: 3.4M Religious Sites — BigQuery Demos + Licensing (via Kevin Dunn)"
msg.attach(MIMEText(body, "plain"))

try:
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
        s.starttls()
        s.login("charlesaprescottjr@gmail.com", PWD)
        s.send_message(msg)
    print("✅ SENT to ben.weeks@data-axle.com")
except Exception as e:
    print(f"❌ FAILED: {e}")

"""
Queue and send the GRID press release to media contacts.
Uses the existing email infrastructure (Gmail SMTP).
Sends to Religion News Service + AP Global Religion team as primary targets.
"""
import json, smtplib, time, os
from pathlib import Path
from email.message import EmailMessage

OUT = Path("outputs/outreach")
PRESS_DIR = OUT / "press_releases"
SENT_LOG = OUT / "press_release_sent.txt"

GMAIL_USER = "charlesaprescottjr@gmail.com"
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD") or os.popen(
    'powershell -c "[Environment]::GetEnvironmentVariable(\'GMAIL_APP_PASSWORD\',\'User\')"'
).read().strip()

if not GMAIL_PASS:
    print("ERROR: GMAIL_APP_PASSWORD not set")
    exit(1)

# Load the press release
pr_path = PRESS_DIR / "press_release_religion_wire.md"
pr_text = pr_path.read_text(encoding="utf-8")

# Load sent log
sent = set()
if SENT_LOG.exists():
    sent = set(line.strip() for line in SENT_LOG.read_text().split("\n") if line.strip())

# Primary targets: RNS distribution + AP Global Religion
TARGETS = [
    # Press release distribution (paid service — first contact to inquire)
    {"org": "Religion News Service — Sales", "email": "Sales@religionnews.com", "type": "inquiry", "notes": "Ask about press release distribution pricing"},
    # News tips (free)
    {"org": "Religion News Service — News Tips", "email": "info@religionnews.com", "type": "press_release"},
    {"org": "Associated Press — Global Religion Team", "email": "info@ap.org", "type": "press_release", "notes": "AP has dedicated Global Religion team (Tiffany Stanley, Deepa Bharath, Peter Smith)"},
    {"org": "Religion Dispatches", "email": "submissions@religiondispatches.org", "type": "pitch"},
    {"org": "Al Jazeera English — Press Office", "email": "press.int@aljazeera.net", "type": "press_release"},
]

def send_email(to_addr, to_name, subject, body):
    """Send one email via Gmail SMTP."""
    msg = EmailMessage()
    msg["From"] = f"Charles Prescott <{GMAIL_USER}>"
    msg["To"] = to_addr
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Subject"] = subject
    msg.set_content(body)
    
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(GMAIL_USER, GMAIL_PASS)
        s.send_message(msg)
    
    SENT_LOG.write_text("\n".join(sorted(sent | {to_addr})))
    print(f"  ✅ Sent to {to_name} <{to_addr}>")

print("=" * 60)
print("GRID PRESS RELEASE DISTRIBUTION")
print("=" * 60)
print()

# First: send press release to news tip contacts
for target in TARGETS:
    if target["email"] in sent:
        print(f"  ⏭ Already sent to {target['org']} <{target['email']}>")
        continue
    
    if target["type"] == "inquiry":
        # Send a shorter inquiry about distribution
        subject = "Inquiry: Press release distribution for global religious database"
        body = f"""Hi RNS Sales Team,

I have a press release announcing the GRID (Global Religious Infrastructure Database) — 3.5 million geocoded religious sites worldwide — that I'd like to distribute through RNS's press release service. Could you let me know pricing and submission requirements?

The release covers: 3.5M worship sites, 20+ faiths, 240+ countries, including recent milestones like 100% Jain classification and 1,700+ ancient sites from Pleiades.

Happy to send the full release text.

Best,
Charles Prescott
Certificate in Theology — University of Toronto
Creator, GRID (Global Religious Infrastructure Database)
charlesaprescott@outlook.com
""" 
    elif target["type"] == "press_release":
        subject = "PRESS RELEASE: World's Largest Religious Infrastructure Database Reaches 3.5M Sites"
        body = pr_text
    elif target["type"] == "pitch":
        subject = "Pitch: World's most comprehensive map of religious infrastructure"
        body = f"""Hi {target['org'].split('—')[0].strip()} editors,

I'm writing to introduce GRID (Global Religious Infrastructure Database) — the world's most comprehensive geocoded map of religious infrastructure: 3.5 million sites, 20+ faiths, 240+ countries.

I thought your readers might be interested in a story or data-driven article. Highlights:

• 3.5M worship sites — every church, mosque, temple, gurdwara, and shrine
• 20 faiths classified with 1,066 tradition nodes (Digambar vs Shwetambar Jain, ELCA vs LCMS Lutheran, etc.)
• 1,700+ ancient sites from the Pleiades gazetteer
• Free BigQuery demo dataset available

I'm happy to write or co-author a piece, provide data for a story, or set up a call.

Best,
Charles Prescott
Certificate in Theology — University of Toronto
Creator, GRID
charlesaprescott@outlook.com
"""
    
    try:
        send_email(target["email"], target["org"], subject, body)
        print(f"  Waiting 30s between sends...")
        time.sleep(30)
    except Exception as e:
        print(f"  ❌ Failed: {target['org']} — {e}")

print(f"\n{'='*60}")
print("DONE — Press release distribution complete")
print(f"{'='*60}")

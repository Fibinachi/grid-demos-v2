"""
Send curated priority list (foundations_outreach.csv) via Gmail API
with 45-second delays between sends.
"""
import csv, os, sys, json, base64, time
from email.message import EmailMessage
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

TOKEN_FILE = os.path.join(SCRIPT_DIR, "gmail_token.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "gmail_credentials.json")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
SENDER_NAME = "Charles Prescott"
SENDER_EMAIL = "charlesaprescottjr@gmail.com"

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

LOG_FILE = os.path.join(SCRIPT_DIR, "curated_sent_log.txt")

# Category-specific hooks for the curated list
CATEGORY_HOOKS = {
    "Theology Foundation": """I am writing to introduce myself and to inquire about your foundation's grantmaking priorities for the current funding cycle. I am beginning a Certificate in Theological Studies at Trinity College, University of Toronto in Fall 2026, following a 15-year career practicing tax law and forming nonprofit and religious organizations.

My proposed research — which I call a "Theology of Risk Management" — examines how institutions manage moral and legal risk, and how theological ethics can speak to the gaps that law and policy leave unaddressed. This work sits at the intersection of law, theology, and institutional ethics.""",
    
    "Research-Aligned Foundation": """I am writing to inquire whether my proposed research might align with your foundation's current funding priorities. I am beginning graduate study at Trinity College, University of Toronto in Fall 2026, following a 15-year legal career.

My proposed research — a "Theology of Risk Management" — uses game theory and institutional ethics to examine how theological frameworks can inform institutional accountability, legal ethics, and moral decision-making in complex systems. This interdisciplinary work bridges law, theology, and social science.""",
    
    "National Anglican Funding Body": """I am writing as a member of the Anglican tradition to inquire about funding opportunities that might support my theological studies. I will be beginning a Certificate in Theological Studies at Trinity College, University of Toronto in Fall 2026 — an institution founded in the Anglican heritage that has been my spiritual home.

My proposed research develops a "Theology of Risk Management" that examines how institutions navigate moral and legal risk, with particular attention to how faith traditions can guide ethical institutional practice. I believe this work has particular relevance for Anglican institutions navigating questions of reconciliation, Indigenous justice, and institutional accountability.""",
    
    "Small Family Foundation": """I am writing to introduce myself and to inquire about your foundation's current giving priorities. I am beginning theological study at Trinity College, University of Toronto in Fall 2026, following a 15-year legal career practicing tax law and forming nonprofit and religious organizations.

My proposed research — which I call a "Theology of Risk Management" — examines how theological ethics can inform institutional accountability and moral decision-making. After years of helping institutions navigate legal risk, I found myself drawn to deeper questions about what justice and integrity require when the law is silent.""",
    
    "Canadian Theological Foundation": """I am writing as a future student at Trinity College, University of Toronto to inquire about funding opportunities that might support my theological studies. I will be moving from South Carolina to begin a Certificate in Theological Studies at Trinity College in Fall 2026 — following a 15-year career as a tax attorney in the United States.

My proposed research develops a "Theology of Risk Management" that examines how institutions navigate moral and legal risk. I am particularly interested in how Canadian theological institutions and funding bodies support research at the intersection of faith, ethics, and institutional practice.""",
    
    "Reconciliation & Residential School Fund": """I am writing to inquire about funding opportunities that might support theological research related to reconciliation and Indigenous justice. I will be beginning a Certificate in Theological Studies at Trinity College, University of Toronto in Fall 2026.

My research interests include exploring how theological frameworks can inform the work of truth, reconciliation, and institutional accountability — particularly as faith communities grapple with their own histories and seek to build just relationships for the future.""",
}

DEFAULT_HOOK = """I am writing to introduce myself and to inquire about your foundation's current funding priorities. I am beginning a Certificate in Theological Studies at Trinity College, University of Toronto in Fall 2026, following a 15-year career practicing tax law and forming nonprofit and religious organizations.

My proposed research — which I call a "Theology of Risk Management" — examines how institutions navigate moral and legal risk, and how theological ethics can speak to the gaps that law and policy leave unaddressed."""

OUTRO = """If your foundation considers requests from individual scholars or supports educational initiatives that align with your mission, I would be grateful for any guidance on application procedures, eligibility, or upcoming opportunities. I am happy to provide a brief proposal, CV, or any additional information.

Thank you for your time and for the important work your foundation does.

Warm regards,

Charles Prescott
JD, LLM in Taxation
Certificate in Theological Studies (beginning Fall 2026)
Trinity College, University of Toronto
Columbia, South Carolina
charlesaprescottjr@gmail.com
843-504-4542"""

# ── Auth ──
creds = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE) as f:
        creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())
if not creds or not creds.valid:
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)
    with open(TOKEN_FILE, 'w') as f:
        json.dump(json.loads(creds.to_json()), f)
service = build('gmail', 'v1', credentials=creds)
print("✅ Gmail authenticated")

# ── Load curated list ──
csv_path = os.path.join(SCRIPT_DIR, "foundations_outreach.csv")
rows = []
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print(f"📋 Loaded {len(rows)} curated funders")

# ── Load sent log ──
sent_ids = set()
if os.path.exists(LOG_FILE):
    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split('|')
                if len(parts) >= 1:
                    sent_ids.add(parts[0])

print(f"📝 Already sent: {len(sent_ids)}")

# ── Send each ──
DELAY = 45  # seconds
sent_count = 0
skip_count = 0

for i, row in enumerate(rows):
    name = row.get('Name', '').strip()
    email = row.get('Primary Email', '').strip()
    category = row.get('Category', '').strip()
    reason = row.get('Reason to Contact', '').strip()
    
    if not email:
        print(f"  ⏭️  [{i+1}/{len(rows)}] {name} — no email")
        skip_count += 1
        continue
    
    if name in sent_ids:
        print(f"  ⏭️  [{i+1}/{len(rows)}] {name} — already sent")
        skip_count += 1
        continue
    
    # Build email
    hook = CATEGORY_HOOKS.get(category, DEFAULT_HOOK)
    reason_line = f"\n\nWhy I am contacting you: {reason}" if reason else ""
    
    body = f"Dear {name} Team,\n\n{hook}{reason_line}\n\n{OUTRO}"
    
    msg = EmailMessage()
    msg.set_content(body)
    msg['To'] = email
    msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg['Subject'] = f"Inquiry: Theology of Risk Management — Research & Funding Inquiry"
    
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    send_body = {'raw': encoded}
    
    try:
        sent = service.users().messages().send(userId='me', body=send_body).execute()
        msg_id = sent.get('id', '')
        print(f"  ✅ [{i+1}/{len(rows)}] {name[:45]:45s} -> {email}")
        sent_count += 1
        
        # Log
        with open(LOG_FILE, 'a') as f:
            f.write(f"{name}|{email}|{category}|{datetime.now().isoformat()}|{msg_id}\n")
        
        # Delay
        if i < len(rows) - 1:
            print(f"     ⏳ Waiting {DELAY}s...")
            time.sleep(DELAY)
            
    except HttpError as e:
        print(f"  ❌ [{i+1}/{len(rows)}] {name} — {e}")

print(f"\n{'='*50}")
print(f"  Done! Sent: {sent_count}, Skipped: {skip_count}")
print(f"  Log: {LOG_FILE}")

"""Send church funding appeals via Gmail API with 45s delays."""
import csv, os, sys, json, base64, time, re
from email.message import EmailMessage
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
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

LOG_FILE = os.path.join(SCRIPT_DIR, "church_sent_log.txt")

# ── Email templates ──
ANGLICAN_BODY = """Grace and peace to you in the name of our Lord Jesus Christ.

My name is Charles Prescott, and I write to introduce myself as a fellow Anglican who will soon begin theological studies at Trinity College, University of Toronto — an institution founded in the Anglican heritage.

After 15 years practicing tax law and forming nonprofit and religious organizations, I felt called to deepen my theological understanding. I am pursuing a Certificate in Theological Studies beginning Fall 2026.

To be honest with you: I am seeking God, and I am not entirely sure where I will find Him. After a career spent navigating legal systems and institutional structures, I have come to realize that the questions I carry — about justice, about institutional morality, about what it means to be faithful — cannot be answered from a statute book. They require the kind of sustained theological reflection that only a community of faith and a rigorous academic program can provide.

My proposed research — what I call a "Theology of Risk Management" — examines how institutions navigate moral and legal risk, and how the Anglican tradition's emphasis on liturgy, scripture, reason, and tradition can speak to the ethical challenges facing modern institutions. I believe this work has particular relevance for Anglican and Episcopal communities navigating questions of reconciliation, justice, and faithful institutional practice.

I am reaching out to Anglican and Episcopal communities to ask: does your parish have a discretionary fund, outreach budget, or educational support program that might assist a member of the wider Anglican communion pursuing theological education?

I would be grateful for any guidance, and I am happy to share more about my work, my background, or my research proposal. Even a small contribution would make a meaningful difference in my ability to answer this calling.

Thank you for your time and for the faithful work your congregation does in building God's kingdom.

Yours in Christ,

Charles Prescott
JD, LLM in Taxation
Certificate in Theological Studies (beginning Fall 2026)
Trinity College, University of Toronto
Columbia, South Carolina
charlesaprescottjr@gmail.com
843-504-4542"""

INTERDENOM_BODY = """Dear friends in Christ,

My name is Charles Prescott, and I write to introduce myself as a Christian preparing to begin theological studies at Trinity College, University of Toronto in Fall 2026.

After 15 years practicing tax law — forming churches as an attorney, serving as Founding Director of the Midlands Light Opera Society, working with cancer charities, and helping individuals navigate complex legal systems — I felt called to deepen my theological understanding.

To be honest with you: I am seeking God, and I am not entirely sure where I will find Him. I left a stable legal career because the questions I was carrying — about justice, about institutional failure, about what it means to live faithfully — kept pressing, and I could no longer ignore them. Theological study feels like the only honest response. I am pursuing a Certificate in Theological Studies to explore these questions with the rigor and depth they deserve.

My faith journey has taken me from Baptist roots through the Methodist tradition of social holiness to the Anglican liturgical tradition — and I believe that the body of Christ is at its best when Christians from different traditions support one another in responding to God's call.

I am reaching out to ask: does your congregation have a discretionary fund, outreach budget, or educational support program that might assist a fellow Christian pursuing theological education? Even a small contribution would make a meaningful difference.

I would be grateful for any guidance, and I am happy to share more about my work, my background, or my research proposal.

Thank you for your time and for the faithful work your congregation does in building God's kingdom.

In Christ,

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

# ── Load churches ──
csv_path = os.path.join(SCRIPT_DIR, "church_clean_send.csv")
rows = []
with open(csv_path, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)
print(f"📋 Loaded {len(rows)} churches")

# ── Load sent log ──
sent_emails = set()
if os.path.exists(LOG_FILE):
    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split('|')
                if len(parts) >= 1:
                    sent_emails.add(parts[0])

print(f"📝 Already sent: {len(sent_emails)}")

# ── Also cross-ref against curated sent so we don't double-send ──
curated_sent = set()
curated_log = os.path.join(SCRIPT_DIR, "curated_sent_log.txt")
if os.path.exists(curated_log):
    with open(curated_log) as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split('|')
                if len(parts) >= 1:
                    curated_sent.add(parts[0])

# ── Send ──
DELAY = 45
sent_count = 0
skip_count = 0

for i, row in enumerate(rows):
    name = row.get('church_name', '').strip()
    email = row.get('email', '').strip().lower()
    ctype = row.get('type', '').strip()
    
    if not email or '@' not in email:
        skip_count += 1
        continue
    
    if email in sent_emails:
        print(f"  ⏭️  [{i+1}/{len(rows)}] {name[:45]:45s} — already sent")
        skip_count += 1
        continue
    
    body = ANGLICAN_BODY if ctype == 'Anglican/Episcopal' else INTERDENOM_BODY
    subject = "Support for Theological Education — Inquiry from a Fellow Christian"
    if ctype == 'Anglican/Episcopal':
        subject = "Support for Anglican Theological Education — Inquiry from a Fellow Anglican"
    
    msg = EmailMessage()
    msg.set_content(body)
    msg['To'] = email
    msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg['Subject'] = subject
    
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    send_body = {'raw': encoded}
    
    try:
        sent = service.users().messages().send(userId='me', body=send_body).execute()
        print(f"  ✅ [{i+1}/{len(rows)}] {name[:45]:45s} -> {email[:30]}")
        sent_count += 1
        
        with open(LOG_FILE, 'a') as f:
            f.write(f"{email}|{name}|{ctype}|{datetime.now().isoformat()}\n")
        
        if i < len(rows) - 1:
            time.sleep(DELAY)
            
    except HttpError as e:
        print(f"  ❌ [{i+1}/{len(rows)}] {name} — {e}")

print(f"\n{'='*50}")
print(f"  Done! Sent: {sent_count}, Skipped: {skip_count}")
print(f"  Log: {LOG_FILE}")

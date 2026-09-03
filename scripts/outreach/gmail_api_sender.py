"""
Gmail API Foundation Sender
===========================
Uses the Gmail API (not SMTP) to send foundation emails.
1,000,000 emails/day limit vs SMTP's 2,000.
OAuth 2.0 authentication — no passwords to manage.

One-time setup required (2 minutes):
  1. Go to https://console.cloud.google.com/
  2. Create a project (or select existing)
  3. Search "Gmail API" → Enable
  4. Go to Credentials → Create Credentials → OAuth client ID
  5. Application type: Desktop app → Name: "Foundation Sender"
  6. Download the JSON → save as "gmail_credentials.json" in this folder
  7. In Gmail settings, add charles@charlesprescott.net as "Send mail as"
  8. Run this script — browser will open for one-time authorization
  9. Done. Token auto-refreshes forever.

Usage:
  python gmail_api_sender.py --tier theology --workers 5
  python gmail_api_sender.py --tier tier1 --workers 10
"""

import csv
import os
import sys
import time
import random
import json
import argparse
import threading
import base64
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

# Declined foundation tracker
from declined_foundations import load_declined_eins

# ── Google API imports ─────────────────────────────────────────────────────
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Configuration ──────────────────────────────────────────────────────────
SENDER_NAME = "Charles Prescott"
SENDER_EMAIL = "charlesaprescottjr@gmail.com"
GMAIL_USER = "me"  # The authenticated Gmail account

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "gmail_credentials.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "gmail_token.json")

TIER_FILES = {
    "tier1":   os.path.join(SCRIPT_DIR, "foundations_tier1_10m_plus.csv"),
    "tier2":   os.path.join(SCRIPT_DIR, "foundations_tier2_1m_10m.csv"),
    "tier3":   os.path.join(SCRIPT_DIR, "foundations_tier3_500k_1m.csv"),
    "theology": os.path.join(SCRIPT_DIR, "theology_final_send.csv"),
    "all":     os.path.join(SCRIPT_DIR, "foundations_master_list.csv"),
}

# Per-worker timing
DEFAULT_WORKERS = 5
PER_WORKER_MIN_DELAY = 20   # seconds (can be tighter with API)
PER_WORKER_MAX_DELAY = 60

LOG_DIR = os.path.join(SCRIPT_DIR, "gmail_api_logs")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# ── Foundation-specific personalization ──────────────────────────────────
# Builds a tailored hook paragraph based on NTEE code, name keywords, and location

NTEE_HOOKS = {
    # Single-letter fallbacks (broad category)
    'T': "I understand that your foundation supports philanthropic initiatives and systemic change efforts. My own work has involved examining how institutions — legal, religious, and charitable — can be held accountable not just legally, but morally. After 15 years practicing tax law, I found myself drawn to questions the law couldn't answer: what does justice look like when systems fail?",
    'B': "I understand that your foundation values educational initiatives and supporting scholars. As a first-generation student who went from a rural South Carolina upbringing to earn a JD and an LLM in Taxation — and who now, at 44, is pursuing theological study at Trinity College, University of Toronto — I know first-hand the transformative power of education and the importance of investing in those who seek deeper understanding.",
    'X': "I understand that your foundation supports faith-based and spiritual initiatives. My own faith journey has taken me from Baptist roots through Methodist action to the Anglican liturgical tradition — which is what drew me to Trinity College, an institution founded in the Anglican heritage. I am exploring how theological ethics can speak to the moral challenges facing modern institutions.",
    'A': "I understand that your foundation supports arts and cultural initiatives. As the Founding Director of the Midlands Light Opera Society, I have seen how the arts can transform communities and shape the human spirit. I am now pursuing theological study to deepen my understanding of how creativity, faith, and justice intersect.",
    'I': "I understand that your foundation supports legal and justice-related initiatives. As a licensed attorney with a JD from Rutgers Law and an LLM in Taxation from the University of Alabama, I spent 15 years practicing law before realizing that the deepest questions I was wrestling with — about institutional morality, justice, and systemic sin — required theological as well as legal training.",
    'P': "I understand that your foundation supports human services and community well-being. Through my work with Healthy Connections, cancer charity initiatives, and pro bono legal representation for domestic violence survivors, I have seen both the resilience of the human spirit and the structural challenges facing vulnerable communities. Theological study is deepening my ability to address those challenges holistically.",
    'E': "I understand that your foundation supports health-related initiatives. Both of my parents have faced cancer, and I have worked with children's cancer charities. These experiences, combined with my own journey living with ADHD and major depressive disorder, have shaped my conviction that human flourishing requires tending to body, mind, and spirit together.",
    'H': "I understand that your foundation supports health and medical research. Both of my parents have faced cancer, and I have worked with children's cancer charities. These experiences have shaped my conviction that true healing requires attention to spiritual as well as physical wellbeing.",
    'S': "I understand that your foundation supports community improvement and development. My mother's family comes from Appalachian Ohio — I remember using an outhouse at a relative's home. That experience of rural poverty shaped my understanding of community and my commitment to serving the common good through both legal practice and theological reflection.",
    'O': "I understand that your foundation supports youth development. As the father of three children — two of whom are on the autism spectrum — I am deeply invested in creating communities where every young person can flourish. My theological studies are part of a broader commitment to building institutions that truly serve the next generation.",
    'U': "I understand that your foundation supports scientific and research initiatives. My academic interests include exploring game theory as a framework for understanding institutional ethics and moral decision-making — work that sits at the intersection of social science, law, and theology. I am eager to bring rigorous, interdisciplinary thinking to questions of systemic morality.",
    'D': "I understand that your foundation supports animal-related causes. While my primary work has been in law and theology, I believe that all of creation deserves compassionate stewardship — a value that shapes my understanding of ethical institutional practice.",
    'C': "I understand that your foundation supports environmental causes. My legal background in tax and nonprofit formation has given me a unique perspective on how institutions can be structured to serve the common good and environmental stewardship.",
    'F': "I understand that your foundation supports mental health initiatives. I live with ADHD and major depressive disorder, and I am committed to destigmatizing mental health challenges — especially in professional and faith communities where silence too often remains the default. My theological studies are helping me explore the spiritual dimensions of mental health and human flourishing.",
    'J': "I understand that your foundation supports employment and workforce initiatives. As someone who left a stable legal career at 44 to pursue theological study as a first-generation student, I understand both the courage and the challenge involved in professional transformation. I am exploring how institutions can better support people through meaningful career and life transitions.",
    'L': "I understand that your foundation supports housing and shelter initiatives. My move from South Carolina to Toronto for theological study has given me a new appreciation for the importance of community, belonging, and having a place to call home.",
}

# Two-letter NTEE code hooks (more specific than single-letter)
NTEE2_HOOKS = {
    'T20': "I understand that your foundation operates as a private grantmaking foundation. My own path from legal practice to theological study has given me a deep appreciation for the role that thoughtful philanthropy plays in supporting meaningful work — and I hope my journey might resonate with your foundation's mission of supporting transformative initiatives.",
    'T21': "I understand that yours is a corporate foundation, supporting initiatives that align with a company's values and community engagement. My background includes legal practice, nonprofit formation, and a commitment to ethical institutional practice — areas where corporate philanthropy can have significant impact.",
    'T22': "I understand that your foundation is a private independent foundation, with the freedom to support initiatives that align with its founders' vision. My own decision to step away from a legal career to pursue theological study reflects a similar commitment to following a deeper sense of purpose.",
    'T23': "I understand that your foundation is a private operating foundation, directly conducting your own charitable programs rather than solely making grants. My background includes founding and directing the Midlands Light Opera Society and working with cancer charities — hands-on work that has shaped my understanding of institutional mission.",
    'T30': "I understand that your foundation engages in public charitable activity. My own work — from forming churches as an attorney to directing a light opera society — has always been rooted in a commitment to public benefit and community service.",
    'T50': "I understand that your foundation focuses on institutional philanthropy. With my background in law, institutional formation, and theological ethics, I have a particular interest in how institutions can be structured to serve the common good with integrity and moral clarity.",
    'T90': "I understand that yours is a named trust, created to honor a specific philanthropic vision. My own journey has been shaped by a desire to ask the deep questions that a career in law left unanswered — and I respect foundations that carry forward a specific, intentional vision.",
    'B82': "I understand that your foundation supports scholarships and educational financial aid. As a first-generation graduate student who went from a rural upbringing to earn a JD and LLM, and who now seeks theological education, I have experienced first-hand the transformative power of educational support.",
    'B12': "I understand that your foundation supports graduate and professional education. My own educational path — BA, JD, LLM, and now a Certificate in Theological Studies — reflects a lifelong commitment to learning and to the integration of knowledge across disciplines.",
    'B90': "I understand that your foundation supports educational services and institutional development. My work forming churches as an attorney and directing a nonprofit arts organization has given me practical experience in educational and institutional development.",
    'B99': "I understand that your foundation supports education in its many forms. My journey from law to theology represents a belief that true education encompasses not just professional training but the formation of the whole person — mind, spirit, and moral imagination.",
    'X20': "I understand that your foundation supports Christian initiatives and ministries. My own faith journey has taken me from Baptist roots through the Methodist tradition of social holiness to the Anglican liturgical tradition — and I am now pursuing theological study at Trinity College, an institution founded in the Anglican heritage.",
    'X21': "I understand that your foundation supports Jewish initiatives and community life. The Jewish intellectual and ethical tradition's emphasis on justice, study, and communal responsibility has deeply informed my understanding of what it means to live a life of meaning and service.",
    'X30': "I understand that your foundation supports religious media and communications. My background in public legal education and as a CLE instructor has given me experience communicating complex ideas to diverse audiences — skills I hope to bring to theological discourse.",
    'X40': "I understand that your foundation supports religious social services. My pro bono work with domestic violence survivors and my involvement with cancer charities has shown me the vital importance of faith-informed social service in building just and compassionate communities.",
    'X50': "I understand that your foundation supports religious schools and educational institutions. Trinity College at the University of Toronto — an institution founded in the Anglican tradition — represents exactly this kind of faith-informed academic community, which is why I have chosen to study there.",
    'X83': "I understand that your foundation supports religiously-affiliated education. Trinity College's Anglican heritage and its commitment to integrating faith and learning make it a natural home for my theological studies.",
    'P20': "I understand that your foundation supports human service organizations. Through my work with Healthy Connections, cancer charities, and pro bono legal representation, I have seen first-hand how vital human services are to community wellbeing — and how theological reflection can deepen this work.",
}

NAME_KEYWORD_HOOKS = {
    'METHODIST': "As a member of a Methodist-tradition church (Emmaus Church in Columbia, SC) whose faith has been shaped by the Wesleyan emphasis on social holiness and active service, I am particularly drawn to foundations that share this commitment to faith in action.",
    'ANGLICAN': "As someone whose spiritual home has increasingly become the Anglican liturgical tradition — which is what drew me to Trinity College, founded in the Anglican heritage — I am particularly drawn to foundations that support this tradition's educational and spiritual mission.",
    'EPISCOPAL': "As someone whose spiritual home has increasingly become the Anglican/Episcopal liturgical tradition — which is what drew me to Trinity College, an Anglican foundation — I am particularly drawn to foundations that share this heritage.",
    'CATHOLIC': "While my personal journey has been in the Protestant tradition, I have deep respect for the Catholic intellectual and social justice tradition and would welcome the opportunity to connect with foundations that share a commitment to faith-informed service and inquiry.",
    'BAPTIST': "Raised in the Baptist tradition, I have deep roots in the emphasis on personal faith, scripture, and conscientious engagement with the world. I am grateful for the formative role this tradition has played in my spiritual journey.",
    'LUTHERAN': "I deeply respect the Lutheran tradition's emphasis on grace, vocation, and the service of the neighbor. These values resonate strongly with my own sense of calling to bridge law and theology in service of institutional renewal.",
    'PRESBYTERIAN': "The Reformed tradition's emphasis on the sovereignty of God and the importance of education and discernment resonates deeply with my own journey from legal practice to theological study.",
    'CHRISTIAN': "My faith journey across multiple Christian traditions — from Baptist roots through Methodist action to Anglican liturgy — has taught me that the heart of the Christian calling is the integration of belief, practice, and service to others.",
    'FAITH': "My faith journey — from Baptist roots through Methodist action to Anglican liturgy — has shaped every significant decision in my life, including my decision to leave a legal career to pursue theological study at Trinity College.",
    'JEWISH': "The Jewish intellectual and ethical tradition's emphasis on justice, study, and community responsibility has deeply influenced my understanding of what it means to live a life of meaning and service.",
    'THEOLOG': "Theological education is at the center of my current journey. I am pursuing a Certificate in Theological Studies at Trinity College, University of Toronto, to deepen my understanding of how faith traditions can guide institutions toward justice and moral integrity.",
    'MISSION': "I am drawn to foundations with a mission-centered approach to philanthropy. My own journey from tax attorney to theology student has been driven by a desire to understand and serve the deepest purposes of human community.",
    'ORTHODOX': "The Orthodox Christian tradition — with its deep roots in patristic theology, liturgical worship, and the mystical tradition — is a significant part of my academic study. I intend to study Orthodoxy academically as part of my theological program at Trinity College, University of Toronto, and am particularly drawn to foundations that support this ancient tradition.",
}

# Asset-based personalization
def get_asset_hook(asset_amt):
    """Generate a tone-appropriate sentence based on foundation size."""
    try:
        assets = int(asset_amt or '0')
    except:
        assets = 0
    if assets >= 10_000_000_000:
        return "Your foundation's significant resources and global reach mean your funding decisions have an extraordinary capacity to shape the future of your chosen fields."
    elif assets >= 1_000_000_000:
        return "Your foundation's substantial resources position you to make transformative investments in the causes that matter most to your mission."
    elif assets >= 100_000_000:
        return "Your foundation's strong asset base allows you to provide meaningful support to initiatives that align with your philanthropic vision."
    elif assets >= 10_000_000:
        return "Your foundation's resources enable you to make a genuine difference in the areas you've chosen to prioritize."
    return ""

# Default hook for unclassified foundations
DEFAULT_HOOK = "After 15 years practicing tax law — forming churches as an attorney, serving as Founding Director of the Midlands Light Opera Society, working with cancer charities, and helping individuals navigate complex legal systems — I found myself asking questions the law couldn't answer. That's why I am now pursuing theological study at Trinity College, University of Toronto."

# Bridge sentence
BRIDGE = "I am writing to explore whether my academic and professional background might align with your foundation's current funding priorities."


def personalize_intro(row):
    """
    Generate a tailored opening paragraph based on foundation metadata.
    Priority: 2-letter NTEE code > name keywords > 1-letter NTEE > default
    Then appends an asset-based sentence and optional location hook.
    """
    name = row.get('NAME', '')
    ntee = (row.get('NTEE_CD', '') or '').strip()
    state = row.get('STATE', '')
    city = row.get('CITY', '')
    assets = row.get('ASSET_AMT', '0')
    name_upper = name.upper()

    # Step 1: Check for name keyword overrides (most specific)
    for keyword, keyword_hook in NAME_KEYWORD_HOOKS.items():
        if keyword in name_upper:
            hook = keyword_hook
            break
    else:
        # Step 2: Try 2-letter NTEE code
        hook = NTEE2_HOOKS.get(ntee)
        
        # Step 3: Fall back to 1-letter NTEE code
        if not hook and ntee and len(ntee) >= 1:
            hook = NTEE_HOOKS.get(ntee[0])
        
        # Step 4: Default
        if not hook:
            hook = DEFAULT_HOOK

    # Step 5: Add asset-based sentence for larger foundations
    asset_hook = get_asset_hook(assets)
    
    # Step 6: Add location hook (Southeast foundations get a local connection)
    southeast = {'SC', 'NC', 'GA', 'TN', 'AL', 'FL', 'VA'}
    location_hook = ""
    if state in southeast and city:
        location_hook = f" As a fellow Southerner based in Columbia, South Carolina — now preparing to study at the University of Toronto — I have a particular appreciation for {city}-area foundations that support educational and spiritual formation."

    # Build the full intro
    parts = [hook]
    if asset_hook:
        parts.append(asset_hook)
    if location_hook:
        parts.append(location_hook)
    
    return " ".join(parts) + (f" {BRIDGE}" if BRIDGE else "")


# ── Body template (the paragraphs after the personalized hook) ────────────
BODY_MIDDLE = """I am beginning graduate study in Fall 2026 and am seeking to identify external foundations whose mission, values, or donor-directed interests intersect with my work. My background includes legal practice (JD, LLM in Taxation), public legal education, mediation, and interdisciplinary research at the intersection of law, society, and theology.

If your foundation considers requests from individual scholars or supports educational or research-oriented initiatives, I would be grateful for any guidance on eligibility, application procedures, or upcoming opportunities. I am happy to provide a brief proposal, CV, or any additional information that would assist in determining potential fit.

Thank you for your time and for the work your foundation does in supporting meaningful initiatives. I appreciate any direction you can offer."""

# Subject line
SUBJECT = "Inquiry Regarding Alignment With Your Foundation's Funding Priorities"


# ── Gmail API Auth ────────────────────────────────────────────────────────
def authenticate_gmail():
    """Authenticate with Gmail API via OAuth 2.0.
    First run opens browser for authorization.
    Subsequent runs use saved token.
    """
    creds = None

    # Load saved token
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
        except Exception:
            creds = None

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            print("  Token refreshed successfully")
        except Exception:
            creds = None

    # First-time auth
    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"\n⚠️  MISSING: {CREDENTIALS_FILE}")
            print()
            print("  You need to create this file from Google Cloud Console.")
            print("  Here's exactly what to do (2 minutes):")
            print()
            print("  1. Go to https://console.cloud.google.com/")
            print("  2. Click 'Create Project' → name it 'Foundation Sender'")
            print("  3. Search for 'Gmail API' → click Enable")
            print("  4. Go to Credentials (left menu)")
            print("  5. Click 'Create Credentials' → 'OAuth client ID'")
            print("  6. Application type: 'Desktop app'")
            print("  7. Name: 'Foundation Sender' → Create")
            print("  8. Click 'Download JSON' → save as 'gmail_credentials.json'")
            print(f"     in: {SCRIPT_DIR}")
            print()
            print("  Then run this script again.")
            sys.exit(1)

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        print("  Authorization successful!")

        # Save token
        with open(TOKEN_FILE, 'w') as f:
            json.dump(json.loads(creds.to_json()), f)
        print(f"  Token saved to {TOKEN_FILE}")

    return creds


# ── Send via Gmail API ─────────────────────────────────────────────────────
def send_via_api(service, to_email, row):
    """Send a personalized email via Gmail API, with foundation-specific hook."""
    foundation_name = row['NAME']
    intro = personalize_intro(row)
    body = f"Dear {foundation_name} Team,\n\n{intro}\n\n{BODY_MIDDLE}\n\nWarm regards,\nCharles Prescott\nColumbia, SC\n8435044542\ncharlesaprescottjr@gmail.com"

    msg = EmailMessage()
    msg.set_content(body)
    msg['To'] = to_email
    msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg['Subject'] = SUBJECT

    # Encode for API
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    send_body = {'raw': encoded}
    try:
        sent = service.users().messages().send(userId=GMAIL_USER, body=send_body).execute()
        return True, sent.get('id', '')
    except HttpError as e:
        return False, str(e)


# ── Email Guessing ─────────────────────────────────────────────────────────
def guess_email(name):
    """Generate a likely info@ email from foundation name."""
    slug = name.strip().replace(',', '').lower()
    slug = slug.replace('the ', '')
    for suffix in [' foundation', ' foundation inc', ' foundation corporation',
                   ' inc', ' corp', ' llc', ', inc.', ', llc']:
        slug = slug.replace(suffix, '')

    words = slug.split()
    if not words:
        return ''

    connectors = {'and', 'the', 'of', 'for', '&', 'de', 'la', 'del'}
    meaningful = [w for w in words if w not in connectors and len(w) > 2]
    if not meaningful:
        meaningful = words

    if len(meaningful) >= 2:
        domain = f"{meaningful[-1]}foundation.org"
    else:
        domain = f"{meaningful[0]}foundation.org"

    return f"info@{domain}"


# ── Shared State ───────────────────────────────────────────────────────────
class SharedState:
    def __init__(self, total):
        self.total = total
        self.sent = 0
        self.errors = 0
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        os.makedirs(LOG_DIR, exist_ok=True)
        self.sent_log = os.path.join(LOG_DIR, "sent.txt")
        self.error_log = os.path.join(LOG_DIR, "errors.txt")

    def record_send(self, ein, name, worker_id, msg_id=''):
        with self.lock:
            self.sent += 1
            count = self.sent
        with open(self.sent_log, "a") as f:
            f.write(f"{ein}|{name[:80]}|W{worker_id}|{msg_id}|{datetime.now().isoformat()}\n")
        return count

    def record_error(self, ein, name, worker_id, error):
        with self.lock:
            self.errors += 1
        with open(self.error_log, "a") as f:
            f.write(f"{datetime.now().isoformat()}|W{worker_id}|{ein}|{name[:60]}|{str(error)[:150]}\n")

    def status(self, worker_id="*"):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.sent / elapsed * 3600 if elapsed > 0 else 0
        remaining = self.total - self.sent
        eta_sec = remaining / rate * 3600 if rate > 0 else 0
        eta = str(timedelta(seconds=int(eta_sec)))
        return (f"[W{worker_id}] {self.sent:,}/{self.total:,} sent | "
                f"{self.errors:,} err | {rate:.0f}/hr | ETA: {eta}")


# ── Worker ─────────────────────────────────────────────────────────────────
def worker_send(worker_id, foundations, state, service):
    """Worker thread: sends its slice of foundations via Gmail API."""
    print(f"  [Worker {worker_id}] Starting: {len(foundations)} foundations")
    sys.stdout.flush()

    for idx, row in enumerate(foundations):
        ein = row['EIN']
        name = row['NAME']
        to_email = guess_email(name)
        if not to_email:
            state.record_error(ein, name, worker_id, "Could not guess email")
            continue

        success, result = send_via_api(service, to_email, row)

        if success:
            count = state.record_send(ein, name, worker_id, result)
            if count % 10 == 0:
                print(f"  {state.status(worker_id)}")
                sys.stdout.flush()
        else:
            state.record_error(ein, name, worker_id, result)
            # If it's a quota/auth error, stop this worker
            if "403" in result or "429" in result:
                print(f"  [Worker {worker_id}] QUOTA ERROR — stopping: {result[:100]}")
                break

        # Jittered delay
        if idx < len(foundations) - 1:
            delay = random.randint(PER_WORKER_MIN_DELAY, PER_WORKER_MAX_DELAY)
            time.sleep(delay)

    print(f"  [Worker {worker_id}] Finished ({len(foundations)} assigned)")
    sys.stdout.flush()


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Gmail API Foundation Sender")
    parser.add_argument("--tier", default="theology",
                        choices=["tier1", "tier2", "tier3", "theology", "all"],
                        help="Foundation tier (default: theology)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Parallel workers (default: {DEFAULT_WORKERS})")
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-sent EINs")
    parser.add_argument("--skip-declined", action="store_true",
                        help="Skip foundations that have politely declined")
    args = parser.parse_args()

    print("=" * 70)
    print("  GMAIL API FOUNDATION SENDER")
    print("  Limits: 1,000,000 emails/day via API")
    print("=" * 70)
    print(f"  Tier:     {args.tier}")
    print(f"  Workers:  {args.workers}")
    print(f"  Resend:       {'Skip sent' if args.resume else 'Full run'}")
    print(f"  Skip declined:{'YES' if args.skip_declined else 'No'}")
    print(f"  Jitter:   {PER_WORKER_MIN_DELAY}-{PER_WORKER_MAX_DELAY}s per worker")
    thr = 3600 // ((PER_WORKER_MIN_DELAY + PER_WORKER_MAX_DELAY) // 2) * args.workers
    print(f"  Throughput: ~{thr:,}/hour (~{thr*24:,}/day)")
    print("=" * 70)

    # ── Authenticate ───────────────────────────────────────────────────
    print("\nAuthenticating with Gmail API...")
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    print("  Gmail API ready!")

    # ── Load foundations ──────────────────────────────────────────────
    csv_path = TIER_FILES[args.tier]
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found!")
        return

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_foundations = list(reader)

    print(f"\nLoaded {len(all_foundations):,} foundations")

    # ── Resume ────────────────────────────────────────────────────────
    if args.resume:
        sent_log = os.path.join(LOG_DIR, "sent.txt")
        if os.path.exists(sent_log):
            with open(sent_log, 'r') as f:
                sent_eins = set(line.split('|')[0] for line in f if line.strip() and '|' in line)
            before = len(all_foundations)
            all_foundations = [r for r in all_foundations if r['EIN'] not in sent_eins]
            print(f"Resume: skipped {len(sent_eins):,} already sent "
                  f"({before:,} -> {len(all_foundations):,})")

    # ── Skip declined ─────────────────────────────────────────────────
    if args.skip_declined:
        declined = load_declined_eins()
        if declined:
            before = len(all_foundations)
            all_foundations = [r for r in all_foundations if r['EIN'] not in declined]
            print(f"Skip declined: skipped {len(declined):,} declined "
                  f"({before:,} -> {len(all_foundations):,})")

    total = len(all_foundations)
    if total == 0:
        print("Nothing to send!")
        return

    # ── Distribute round-robin ────────────────────────────────────────
    worker_slices = [[] for _ in range(args.workers)]
    for i, f in enumerate(all_foundations):
        worker_slices[i % args.workers].append(f)

    sizes = [len(s) for s in worker_slices]
    print(f"Distribution: min={min(sizes):,} max={max(sizes):,}")

    # ── Countdown ─────────────────────────────────────────────────────
    print(f"\n🚀 Launching {args.workers} workers in 3 seconds...")
    sys.stdout.flush()
    time.sleep(3)

    state = SharedState(total)
    executor = ThreadPoolExecutor(max_workers=args.workers)

    # Each worker needs its own service instance
    futures = []
    for w_id in range(args.workers):
        svc = build('gmail', 'v1', credentials=creds)
        futures.append(executor.submit(
            worker_send, w_id, worker_slices[w_id], state, svc
        ))

    try:
        all_done = False
        while not all_done:
            all_done = all(f.done() for f in futures)
            if not all_done:
                print(f"  ── {state.status('*')} ──")
                sys.stdout.flush()
                time.sleep(15)
    except KeyboardInterrupt:
        print("\n⚠️  Ctrl+C — letting workers finish current send...\n")

    executor.shutdown(wait=True)

    # ── Final ─────────────────────────────────────────────────────────
    elapsed = (datetime.now() - state.start_time).total_seconds()
    print(f"\n{'=' * 70}")
    print(f"  ✅ BATCH COMPLETE")
    print(f"  Sent:   {state.sent:,}")
    print(f"  Errors: {state.errors:,}")
    print(f"  Time:   {str(timedelta(seconds=int(elapsed)))}")
    print(f"  Rate:   {(state.sent / elapsed * 3600):.0f}/hour")
    print(f"  Logs:   {LOG_DIR}\\")
    print(f"{'=' * 70}")
    print(f"\nNext: python gmail_api_sender.py --tier tier2 --resume")


if __name__ == '__main__':
    main()

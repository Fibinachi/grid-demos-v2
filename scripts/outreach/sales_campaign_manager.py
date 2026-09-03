"""
GRID SALES CAMPAIGN MANAGER
============================
Master orchestrator for the automated sales campaign.
Tracks leads through pipeline stages, manages multi-touch sequences,
processes replies, and generates pipeline reports.

Usage:
    python scripts/outreach/sales_campaign_manager.py --build     # Build/refresh campaign queues
    python scripts/outreach/sales_campaign_manager.py --send      # Send next batch from queue
    python scripts/outreach/sales_campaign_manager.py --monitor   # Check for replies & advance stages
    python scripts/outreach/sales_campaign_manager.py --report    # Print pipeline report
    python scripts/outreach/sales_campaign_manager.py --status    # Quick status overview
    python scripts/outreach/sales_campaign_manager.py --daemon    # Run continuously (send + monitor)

Author: Charles Prescott — GRID
Created: 2026-07-08
"""

import sqlite3
import json
import os
import sys
import time
import csv
import smtplib
import email
import imaplib
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict
from typing import Optional, Dict, List, Tuple

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import config
from scripts.outreach.sales_campaign_config import (
    PRODUCTS, PERSONAS, CAMPAIGN_SEQUENCES, EMAIL_TEMPLATES,
    LEAD_SOURCES, PIPELINE_STAGES, MONTHLY_TARGETS, SIGNATURE,
    GRID_STATS_SHORT, GRID_STATS_FULL
)

# ══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "churches.db"
OUT_DIR = PROJECT_ROOT / "outputs" / "outreach"
CRM_DB = OUT_DIR / "sales_crm.db"
QUEUE_FILE = OUT_DIR / "unified_queue.jsonl"
SENT_LOG = OUT_DIR / "gmail_sent.txt"
BOUNCE_FILE = OUT_DIR / "gmail_bounced.txt"
FAIL_LOG = OUT_DIR / "gmail_failed.txt"
CAMPAIGN_STATE = OUT_DIR / "campaign_state.json"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
FROM_EMAIL = "charlesaprescottjr@gmail.com"
FROM_NAME = f"Charles Prescott <{FROM_EMAIL}>"
REPLY_TO = "charlesaprescott@outlook.com"
INTERVAL = 180  # 3 minutes between sends

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════
# CRM DATABASE
# ══════════════════════════════════════════════════════════════════════════

def get_crm_db() -> sqlite3.Connection:
    """Get or create the sales CRM database."""
    db = sqlite3.connect(str(CRM_DB))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    _init_crm_schema(db)
    return db

def _init_crm_schema(db: sqlite3.Connection):
    """Initialize CRM tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_name TEXT NOT NULL,
            contact_name TEXT,
            contact_email TEXT NOT NULL UNIQUE,
            contact_phone TEXT,
            dept TEXT,
            persona TEXT NOT NULL,
            source TEXT NOT NULL,
            lead_source_detail TEXT,
            priority INTEGER DEFAULT 5,
            pipeline_stage TEXT DEFAULT 'queued',
            assigned_product TEXT,
            deal_size_estimate REAL,
            notes TEXT,
            church_id INTEGER,  -- FK to churches if applicable
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            last_contacted_at TEXT,
            next_touch_at TEXT,
            sequence_name TEXT,
            sequence_step INTEGER DEFAULT 0,
            total_touches_sent INTEGER DEFAULT 0,
            replies_received INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS touch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER REFERENCES leads(id),
            touch_type TEXT NOT NULL,
            template_name TEXT,
            subject TEXT,
            body TEXT,
            sent_at TEXT DEFAULT (datetime('now')),
            delivered INTEGER DEFAULT 1,
            opened INTEGER DEFAULT 0,
            replied INTEGER DEFAULT 0,
            reply_text TEXT,
            reply_classification TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER REFERENCES leads(id),
            product_id TEXT NOT NULL,
            deal_amount REAL,
            stage TEXT DEFAULT 'proposal',
            probability REAL DEFAULT 0.25,
            expected_close_date TEXT,
            closed_date TEXT,
            is_won INTEGER DEFAULT 0,
            payment_link TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS pipeline_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT DEFAULT (date('now')),
            stage TEXT NOT NULL,
            lead_count INTEGER,
            total_value REAL,
            snapshot_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(pipeline_stage);
        CREATE INDEX IF NOT EXISTS idx_leads_persona ON leads(persona);
        CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
        CREATE INDEX IF NOT EXISTS idx_leads_next_touch ON leads(next_touch_at);
        CREATE INDEX IF NOT EXISTS idx_touch_log_lead ON touch_log(lead_id);
        CREATE INDEX IF NOT EXISTS idx_deals_lead ON deals(lead_id);
    """)
    db.commit()

# ══════════════════════════════════════════════════════════════════════════
# EMAIL UTILITIES
# ══════════════════════════════════════════════════════════════════════════

def get_gmail_password() -> str:
    """Get Gmail app password from environment."""
    pwd = os.environ.get("GMAIL_APP_PASSWORD")
    if not pwd:
        import subprocess
        r = subprocess.run(
            ["powershell", "-c",
             "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"],
            capture_output=True, text=True
        )
        pwd = r.stdout.strip()
    if not pwd:
        print("ERROR: GMAIL_APP_PASSWORD not set")
        sys.exit(1)
    return pwd

def validate_email(email_addr: str) -> str:
    """Validate email via ZeroBounce."""
    zb_key = os.environ.get("ZEROBOUNCE_API_KEY", "")
    if not zb_key or not email_addr:
        return "no_key"
    url = f"https://api.zerobounce.net/v2/validate?api_key={zb_key}&email={urllib.parse.quote(email_addr)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRID/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return data.get("status", "error")
    except Exception:
        return "error"

def send_email(to_addr: str, subject: str, body: str, pwd: str) -> Tuple[bool, str]:
    """Send a single email via Gmail SMTP. Returns (success, error_message)."""
    try:
        msg = MIMEMultipart()
        msg["From"] = FROM_NAME
        msg["To"] = to_addr
        msg["Reply-To"] = REPLY_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login(FROM_EMAIL, pwd)
            s.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)

def check_inbox(pwd: str, since_date: str = None) -> List[Dict]:
    """Check Gmail inbox for replies. Returns list of reply dicts."""
    if since_date is None:
        since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")

    replies = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(FROM_EMAIL, pwd)
        mail.select("INBOX")

        # Search for replies (emails that are replies, not bounces)
        status, messages = mail.search(None, f'(SINCE "{since_date}")')
        if status != "OK":
            return replies

        for num in messages[0].split()[-50:]:  # Last 50 emails
            status, data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue

            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            # Skip automated/bounce messages
            subject = str(msg["Subject"] or "")
            if any(x in subject.lower() for x in ["undeliverable", "out of office", "auto-reply", "automatic reply"]):
                continue

            from_addr = str(msg["From"] or "")
            to_addr = str(msg["To"] or "")

            # Only process replies TO us
            if FROM_EMAIL not in to_addr:
                continue

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        except:
                            pass
                        break
            else:
                try:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    pass

            replies.append({
                "from": from_addr,
                "subject": subject,
                "body": body[:2000],
                "date": msg["Date"]
            })

        mail.logout()
    except Exception as e:
        print(f"  ⚠️ Inbox check failed: {e}")

    return replies

# ══════════════════════════════════════════════════════════════════════════
# LEAD MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════

def load_leads_from_csv(csv_path: Path, persona: str, source: str) -> List[Dict]:
    """Load leads from a CSV file."""
    leads = []
    with open(csv_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            leads.append({
                "org_name": row.get("org", row.get("organization", "")),
                "contact_name": row.get("contact", row.get("name", "")),
                "contact_email": row.get("email", row.get("contact_value", "")),
                "dept": row.get("dept", row.get("department", "")),
                "persona": persona,
                "source": source,
                "lead_source_detail": row.get("category", ""),
                "notes": row.get("pitch", row.get("notes", ""))
            })
    return leads

def load_leads_from_db(persona: str, source: str) -> List[Dict]:
    """Load leads from churches.db for a given persona."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    leads = []

    if persona == "church_admin":
        # US churches with email + address
        rows = db.execute("""
            SELECT c.id, c.name, c.address, c.city, c.state, c.zip5, c.faith,
                   cv.value as email, c.tradition
            FROM churches c
            JOIN church_contact_values cv ON c.id = cv.church_id
            WHERE c.country = 'US'
              AND cv.contact_type = 'email'
              AND cv.value LIKE '%@%'
              AND c.address IS NOT NULL AND c.address != ''
              AND c.city IS NOT NULL AND c.city != ''
              AND c.zip5 IS NOT NULL AND c.zip5 != ''
            ORDER BY RANDOM()
        """).fetchall()

        for r in rows:
            leads.append({
                "org_name": r["name"],
                "contact_email": r["email"],
                "persona": persona,
                "source": source,
                "church_id": r["id"],
                "priority": 6,
                "notes": json.dumps({
                    "address": r["address"],
                    "city": r["city"],
                    "state": r["state"],
                    "zip5": r["zip5"],
                    "faith": r["faith"],
                    "tradition": r["tradition"]
                })
            })

    elif persona == "insurance":
        # Find insurance-related orgs or use specific lists
        rows = db.execute("""
            SELECT c.id, c.name, c.city, c.state, c.tradition,
                   (SELECT value FROM church_contact_values
                    WHERE church_id=c.id AND contact_type='email' LIMIT 1) as email
            FROM churches c
            WHERE c.country = 'US'
              AND c.id IN (SELECT church_id FROM church_contact_values WHERE contact_type='email')
              AND (c.name LIKE '%INSURANCE%' OR c.name LIKE '%BROTHERHOOD%'
                   OR c.tradition LIKE '%Catholic%')
            LIMIT 500
        """).fetchall()

        for r in rows:
            if not r["email"]:
                continue
            leads.append({
                "org_name": r["name"],
                "contact_email": r["email"],
                "persona": persona,
                "source": source,
                "church_id": r["id"],
                "priority": 3
            })

    db.close()
    return leads

def upsert_lead(crm: sqlite3.Connection, lead: Dict) -> Optional[int]:
    """Insert or update a lead. Returns lead_id."""
    existing = crm.execute(
        "SELECT id, pipeline_stage FROM leads WHERE contact_email=?",
        (lead["contact_email"].lower().strip(),)
    ).fetchone()

    if existing:
        # Don't re-add leads that are already engaged or won/lost
        if existing["pipeline_stage"] in ("engaged", "won", "lost", "negotiating"):
            return None
        # Update existing
        crm.execute("""
            UPDATE leads SET
                org_name=?, contact_name=?, dept=?, persona=?, source=?,
                priority=?, notes=?, updated_at=datetime('now')
            WHERE id=?
        """, (
            lead.get("org_name", ""),
            lead.get("contact_name", ""),
            lead.get("dept", ""),
            lead.get("persona", "unknown"),
            lead.get("source", "unknown"),
            lead.get("priority", 5),
            lead.get("notes", ""),
            existing["id"]
        ))
        return existing["id"]
    else:
        crm.execute("""
            INSERT INTO leads (org_name, contact_name, contact_email, dept,
                             persona, source, lead_source_detail, priority, notes, church_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            lead.get("org_name", ""),
            lead.get("contact_name", ""),
            lead["contact_email"].lower().strip(),
            lead.get("dept", ""),
            lead.get("persona", "unknown"),
            lead.get("source", "unknown"),
            lead.get("lead_source_detail", ""),
            lead.get("priority", 5),
            lead.get("notes", ""),
            lead.get("church_id")
        ))
        return crm.execute("SELECT last_insert_rowid()").fetchone()[0]

def assign_sequence(crm: sqlite3.Connection, lead_id: int, persona: str):
    """Assign a campaign sequence to a lead."""
    seq = CAMPAIGN_SEQUENCES.get(persona)
    if not seq:
        return

    crm.execute("""
        UPDATE leads SET
            sequence_name=?, sequence_step=0,
            next_touch_at=datetime('now'),
            pipeline_stage='queued'
        WHERE id=?
    """, (seq["name"], lead_id))
    crm.commit()

def advance_lead(crm: sqlite3.Connection, lead_id: int, new_stage: str, notes: str = ""):
    """Advance a lead to a new pipeline stage."""
    crm.execute("""
        UPDATE leads SET
            pipeline_stage=?, notes=notes || ? || char(10), updated_at=datetime('now')
        WHERE id=?
    """, (new_stage, f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {notes}", lead_id))
    crm.commit()

def create_deal(crm: sqlite3.Connection, lead_id: int, product_id: str,
                amount: float = None, probability: float = 0.25) -> int:
    """Create a deal for a lead."""
    product = PRODUCTS.get(product_id, {})
    if amount is None:
        amount = product.get("price_usd", 0)
        if isinstance(amount, str):
            amount = 500  # Default for custom pricing

    crm.execute("""
        INSERT INTO deals (lead_id, product_id, deal_amount, probability, stage)
        VALUES (?,?,?,?,?)
    """, (lead_id, product_id, amount, probability, "proposal"))
    crm.commit()
    return crm.execute("SELECT last_insert_rowid()").fetchone()[0]

# ══════════════════════════════════════════════════════════════════════════
# CAMPAIGN BUILDING
# ══════════════════════════════════════════════════════════════════════════

def _safe_parse_notes(notes_raw) -> Dict:
    """Parse notes field — handles JSON, plain text, None, and empty."""
    if not notes_raw:
        return {}
    try:
        parsed = json.loads(notes_raw)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}

def render_template(template_name: str, lead: Dict, crm: sqlite3.Connection) -> Tuple[str, str]:
    """Render an email template for a lead. Returns (subject, body)."""
    tmpl = EMAIL_TEMPLATES.get(template_name)
    if not tmpl:
        return "", ""

    notes = _safe_parse_notes(lead.get("notes"))

    # Build template variables
    vars_ = {
        "org": lead.get("org_name", "there"),
        "dept": lead.get("dept", "Team"),
        "church_name": lead.get("org_name", "your church"),
        "address": notes.get("address", "your address"),
        "city": notes.get("city", "your city"),
        "state": notes.get("state", ""),
        "zip5": notes.get("zip5", ""),
        "company": lead.get("org_name", ""),
        "signature": SIGNATURE,
        "stats": GRID_STATS_FULL if "full" in template_name else GRID_STATS_SHORT,
        "count": "1M+",
    }

    subject = tmpl["subject"].format(**vars_)
    body = tmpl["body"].format(**vars_)

    return subject, body

def build_campaign_batch(crm: sqlite3.Connection, persona: str = None,
                         max_new: int = 50, preview: bool = False):
    """Build a batch of campaign emails and add to unified queue."""
    where = "WHERE pipeline_stage='queued' AND is_active=1"
    params = []
    if persona:
        where += " AND persona=?"
        params.append(persona)

    leads = crm.execute(
        f"SELECT * FROM leads {where} ORDER BY priority ASC, created_at ASC LIMIT ?",
        params + [max_new]
    ).fetchall()

    if not leads:
        print(f"No queued leads to process" + (f" for persona={persona}" if persona else ""))
        return []

    queue_entries = []
    for lead in leads:
        lead_dict = dict(lead)
        seq = CAMPAIGN_SEQUENCES.get(lead["persona"])
        if not seq:
            continue

        step = lead["sequence_step"]
        if step >= len(seq["touches"]):
            # Sequence complete — mark as no_response
            advance_lead(crm, lead["id"], "no_response", "Sequence complete")
            continue

        touch = seq["touches"][step]
        template_name = touch.get("template")

        if template_name and template_name in EMAIL_TEMPLATES:
            subject, body = render_template(template_name, lead_dict, crm)
        else:
            # Skip non-email touches (LinkedIn, web forms)
            crm.execute("""
                UPDATE leads SET sequence_step=sequence_step+1,
                next_touch_at=datetime('now', '+3 days')
                WHERE id=?
            """, (lead["id"],))
            crm.commit()
            continue

        if not subject:
            continue

        if preview:
            print(f"\n{'='*60}")
            print(f"TO: {lead['contact_email']} ({lead['org_name']})")
            print(f"SUBJECT: {subject}")
            print(f"PERSONA: {lead['persona']} | STEP: {step+1}/{len(seq['touches'])}")
            print(f"{'='*60}")
            print(body[:500])
            continue

        queue_entries.append({
            "to": lead["contact_email"],
            "subject": subject,
            "body": body,
            "campaign": f"sales_{lead['persona']}",
            "lead_id": lead["id"],
            "org_name": lead["org_name"],
            "persona": lead["persona"],
            "sequence_step": step,
            "template": template_name
        })

    return queue_entries

def append_to_queue(entries: List[Dict]):
    """Append entries to the unified queue JSONL file."""
    # Read existing queue
    existing = []
    existing_emails = set()
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    existing.append(e)
                    existing_emails.add(e.get("to", "").lower())

    # Load sent log
    sent_emails = set()
    if SENT_LOG.exists():
        sent_emails = {l.strip().lower() for l in SENT_LOG.read_text().splitlines() if l.strip()}

    # Filter — don't re-queue already sent or queued
    new_entries = []
    for entry in entries:
        email_lower = entry["to"].lower()
        if email_lower in existing_emails or email_lower in sent_emails:
            continue
        new_entries.append(entry)
        existing_emails.add(email_lower)

    # Write merged queue
    merged = existing + new_entries
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        for entry in merged:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    return len(new_entries)

# ══════════════════════════════════════════════════════════════════════════
# REPLY PROCESSING
# ══════════════════════════════════════════════════════════════════════════

def classify_reply(body: str, subject: str) -> str:
    """Classify a reply: interested, not_interested, question, unsubscribe, other."""
    text = (body + " " + subject).lower()

    interest_signals = [
        "interested", "tell me more", "would like to", "please send",
        "how much", "pricing", "demo", "sample", "yes", "sounds interesting",
        "let's talk", "schedule", "call", "learn more", "details"
    ]

    negative_signals = [
        "not interested", "unsubscribe", "remove me", "stop emailing",
        "do not contact", "no thanks", "not now", "delete", "spam"
    ]

    question_signals = ["?", "what", "how", "when", "where", "who", "which", "can you"]

    negative_count = sum(1 for s in negative_signals if s in text)
    interest_count = sum(1 for s in interest_signals if s in text)
    question_count = sum(1 for s in question_signals if s in text)

    if negative_count > 0:
        return "not_interested" if "unsubscribe" not in text and "remove" not in text else "unsubscribe"
    if interest_count >= 2:
        return "interested"
    if question_count >= 2:
        return "question"
    if interest_count == 1:
        return "interested"
    return "other"

def process_replies(crm: sqlite3.Connection, pwd: str):
    """Check inbox for replies and update lead stages."""
    print("\n=== CHECKING FOR REPLIES ===")
    replies = check_inbox(pwd)

    if not replies:
        print("  No new replies found.")
        return

    print(f"  Found {len(replies)} potential replies")

    for reply in replies:
        from_addr = reply["from"]
        # Extract email from "Name <email>" format
        if "<" in from_addr:
            from_email = from_addr.split("<")[1].split(">")[0].strip().lower()
        else:
            from_email = from_addr.strip().lower()

        # Find matching lead
        lead = crm.execute(
            "SELECT * FROM leads WHERE contact_email=?",
            (from_email,)
        ).fetchone()

        if not lead:
            # Try fuzzy match
            lead = crm.execute(
                "SELECT * FROM leads WHERE contact_email LIKE ?",
                (f"%{from_email.split('@')[0]}%",)
            ).fetchone()

        if not lead:
            continue

        classification = classify_reply(reply["body"], reply["subject"])
        lead_dict = dict(lead)

        # Log the touch
        crm.execute("""
            INSERT INTO touch_log (lead_id, touch_type, replied, reply_text, reply_classification)
            VALUES (?, 'reply', 1, ?, ?)
        """, (lead["id"], reply["body"][:2000], classification))

        # Update lead
        new_stage = lead["pipeline_stage"]
        product = PRODUCTS.get(lead_dict.get("assigned_product") or
                               PERSONAS.get(lead["persona"], {}).get("primary_product", ""))

        if classification == "interested":
            new_stage = "engaged"
            # Auto-create deal if none exists
            existing_deal = crm.execute(
                "SELECT id FROM deals WHERE lead_id=?", (lead["id"],)
            ).fetchone()
            if not existing_deal and product:
                create_deal(crm, lead["id"],
                           PERSONAS.get(lead["persona"], {}).get("primary_product", "researcher_basic"))

        elif classification == "question":
            new_stage = "engaged"

        elif classification == "not_interested":
            new_stage = "lost"

        elif classification == "unsubscribe":
            new_stage = "unsubscribed"
            crm.execute("UPDATE leads SET is_active=0 WHERE id=?", (lead["id"],))

        advance_lead(crm, lead["id"], new_stage,
                    f"Reply received: {classification} — {reply['subject']}")
        crm.execute("""
            UPDATE leads SET replies_received=replies_received+1,
            last_contacted_at=datetime('now'), updated_at=datetime('now')
            WHERE id=?
        """, (lead["id"],))

        print(f"  📩 {lead['org_name']}: {classification.upper()}")
        if product:
            print(f"     Product: {product.get('name', 'N/A')} — ${product.get('price_usd', 'N/A')}")

    crm.commit()

# ══════════════════════════════════════════════════════════════════════════
# PIPELINE REPORTING
# ══════════════════════════════════════════════════════════════════════════

def pipeline_report(crm: sqlite3.Connection) -> str:
    """Generate a pipeline report."""
    now = datetime.now()
    lines = []
    lines.append("=" * 70)
    lines.append(f"  GRID SALES PIPELINE REPORT — {now.strftime('%B %d, %Y %H:%M')}")
    lines.append("=" * 70)

    # Stage breakdown
    lines.append("\n── PIPELINE BY STAGE ──")
    stages = crm.execute("""
        SELECT pipeline_stage, COUNT(*) as cnt
        FROM leads WHERE is_active=1
        GROUP BY pipeline_stage
        ORDER BY CASE pipeline_stage
            WHEN 'queued' THEN 1
            WHEN 'sent' THEN 2
            WHEN 'engaged' THEN 3
            WHEN 'sample_sent' THEN 4
            WHEN 'proposal_sent' THEN 5
            WHEN 'negotiating' THEN 6
            WHEN 'won' THEN 7
            WHEN 'lost' THEN 8
            ELSE 9 END
    """).fetchall()

    total = sum(s["cnt"] for s in stages)
    for s in stages:
        pct = (s["cnt"] / total * 100) if total > 0 else 0
        bar = "█" * int(pct / 2) + "░" * (25 - int(pct / 2))
        lines.append(f"  {s['pipeline_stage']:20s} {s['cnt']:5d} ({pct:5.1f}%) {bar}")

    lines.append(f"  {'─'*20} {'─'*5}")
    lines.append(f"  {'TOTAL':20s} {total:5d}")

    # Persona breakdown
    lines.append("\n── PIPELINE BY PERSONA ──")
    personas = crm.execute("""
        SELECT persona, pipeline_stage, COUNT(*) as cnt
        FROM leads WHERE is_active=1
        GROUP BY persona, pipeline_stage
        ORDER BY persona, CASE pipeline_stage
            WHEN 'queued' THEN 1 WHEN 'sent' THEN 2 WHEN 'engaged' THEN 3
            WHEN 'won' THEN 4 ELSE 5 END
    """).fetchall()

    persona_summary = defaultdict(lambda: defaultdict(int))
    for p in personas:
        persona_summary[p["persona"]][p["pipeline_stage"]] = p["cnt"]

    for persona, stages_dict in sorted(persona_summary.items()):
        total_p = sum(stages_dict.values())
        won = stages_dict.get("won", 0)
        engaged = stages_dict.get("engaged", 0) + stages_dict.get("negotiating", 0)
        lines.append(f"  {persona:25s} total={total_p:4d}  won={won:2d}  active={engaged:2d}")

    # Deal summary
    lines.append("\n── DEALS ──")
    deals = crm.execute("""
        SELECT d.*, l.org_name, l.persona
        FROM deals d JOIN leads l ON d.lead_id=l.id
        ORDER BY d.stage, d.deal_amount DESC
    """).fetchall()

    total_value = 0
    won_value = 0
    for d in deals:
        stage_icon = "✅" if d["is_won"] else "🔵" if d["stage"] == "proposal" else "🟡"
        lines.append(f"  {stage_icon} {d['org_name']:30s} {d['product_id']:20s} "
                    f"${d['deal_amount']:>8,.0f}  {d['stage']}")
        total_value += d["deal_amount"] or 0
        if d["is_won"]:
            won_value += d["deal_amount"] or 0

    if deals:
        lines.append(f"  {'─'*65}")
        lines.append(f"  Pipeline total: ${total_value:,.0f}  |  Won: ${won_value:,.0f}")

    # Monthly targets
    lines.append("\n── MONTHLY TARGETS ──")
    mt = MONTHLY_TARGETS
    sent_count = crm.execute(
        "SELECT COUNT(*) FROM touch_log WHERE sent_at >= date('now','start of month')"
    ).fetchone()[0]
    replied = crm.execute(
        "SELECT COUNT(*) FROM touch_log WHERE replied=1 AND sent_at >= date('now','start of month')"
    ).fetchone()[0]
    won = crm.execute(
        "SELECT COUNT(*) FROM deals WHERE is_won=1 AND closed_date >= date('now','start of month')"
    ).fetchone()[0]
    won_rev = crm.execute(
        "SELECT COALESCE(SUM(deal_amount),0) FROM deals WHERE is_won=1 AND closed_date >= date('now','start of month')"
    ).fetchone()[0]

    lines.append(f"  Emails sent (MTD):  {sent_count:5d} / {mt['emails_sent']:>6,}  ({sent_count/max(1,mt['emails_sent'])*100:.0f}%)")
    lines.append(f"  Reply rate:          {replied:5d} / {max(1,sent_count):5d}  ({replied/max(1,sent_count)*100:.1f}%)")
    lines.append(f"  Deals won (MTD):     {won:5d} / {mt['deals_closed']:>5}")
    lines.append(f"  Revenue (MTD):       ${won_rev:>8,.0f} / ${mt['revenue_target']:>,}")

    # Quick stats
    lines.append(f"\n── QUICK STATS ──")
    lines.append(f"  Total leads:        {total}")
    active_seq_sql = """SELECT COUNT(*) FROM leads WHERE is_active=1
        AND pipeline_stage NOT IN ('won','lost','unsubscribed','no_response')"""
    lines.append(f"  Active sequences:   {crm.execute(active_seq_sql).fetchone()[0]}")
    lines.append(f"  Payment link:       https://buymeacoffee.com/CharlesPrescott")

    lines.append("=" * 70)
    return "\n".join(lines)

def short_status(crm: sqlite3.Connection) -> str:
    """Quick one-line status."""
    total = crm.execute("SELECT COUNT(*) FROM leads WHERE is_active=1").fetchone()[0]
    engaged = crm.execute(
        "SELECT COUNT(*) FROM leads WHERE is_active=1 AND pipeline_stage IN ('engaged','negotiating','proposal_sent')"
    ).fetchone()[0]
    won = crm.execute("SELECT COUNT(*) FROM leads WHERE pipeline_stage='won'").fetchone()[0]

    won_rev = crm.execute(
        "SELECT COALESCE(SUM(deal_amount),0) FROM deals WHERE is_won=1"
    ).fetchone()[0]

    # Queue status
    queue_count = 0
    if QUEUE_FILE.exists():
        queue_count = sum(1 for _ in open(QUEUE_FILE, encoding='utf-8'))

    return (f"📊 Leads: {total} | 🔵 Active: {engaged} | ✅ Won: {won} | "
            f"💰 Won: ${won_rev:,.0f} | 📬 Queue: {queue_count}")

# ══════════════════════════════════════════════════════════════════════════
# DAILY SNAPSHOT
# ══════════════════════════════════════════════════════════════════════════

def take_snapshot(crm: sqlite3.Connection):
    """Save a daily pipeline snapshot."""
    stages = crm.execute("""
        SELECT pipeline_stage, COUNT(*) as cnt
        FROM leads WHERE is_active=1
        GROUP BY pipeline_stage
    """).fetchall()

    deals = crm.execute("""
        SELECT SUM(CASE WHEN is_won=0 THEN deal_amount ELSE 0 END) as pipeline_value,
               SUM(CASE WHEN is_won=1 THEN deal_amount ELSE 0 END) as won_value
        FROM deals
    """).fetchone()

    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "stages": {s["pipeline_stage"]: s["cnt"] for s in stages},
        "pipeline_value": deals["pipeline_value"] or 0,
        "won_value": deals["won_value"] or 0
    }

    crm.execute("""
        INSERT INTO pipeline_snapshots (snapshot_date, stage, lead_count, total_value, snapshot_json)
        VALUES (date('now'), 'summary',
                (SELECT COUNT(*) FROM leads WHERE is_active=1),
                ?,
                ?)
    """, (snapshot["pipeline_value"], json.dumps(snapshot)))
    crm.commit()

# ══════════════════════════════════════════════════════════════════════════
# MAIN COMMANDS
# ══════════════════════════════════════════════════════════════════════════

def cmd_build(args: List[str]):
    """Build campaign queues."""
    crm = get_crm_db()
    preview = "--preview" in args

    # Load broker leads from predefined list
    from scripts.outreach.build_broker_pipeline import CONTACTS as broker_contacts
    for c in broker_contacts:
        upsert_lead(crm, {
            "org_name": c["org"],
            "contact_name": c.get("dept", ""),
            "contact_email": c.get("email", ""),
            "dept": c.get("dept", ""),
            "persona": "data_broker",
            "source": "broker_pipeline",
            "priority": {"T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 5}.get(c["tier"], 5),
            "notes": c.get("pitch", "")
        })

    # Load outreach_emails.csv for various personas
    csv_path = OUT_DIR / "outreach_emails.csv"
    if csv_path.exists():
        with open(csv_path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row.get("contact_type") == "Email" and row.get("contact_value", "").count("@") == 1:
                    # Determine persona from category
                    cat = row.get("category", "").lower()
                    persona = "academic"
                    if "broker" in cat or "data" in cat:
                        persona = "data_broker"
                    elif "research" in cat:
                        persona = "academic"
                    elif "foundation" in cat:
                        persona = "nonprofit"
                    elif "insurance" in cat:
                        persona = "insurance"
                    elif "mapping" in cat or "map" in cat:
                        persona = "mapping_company"

                    upsert_lead(crm, {
                        "org_name": row.get("org", ""),
                        "contact_name": row.get("contact", ""),
                        "contact_email": row.get("contact_value", ""),
                        "dept": row.get("dept", ""),
                        "persona": persona,
                        "source": "outreach_csv",
                        "lead_source_detail": row.get("category", ""),
                        "priority": LEAD_SOURCES.get(persona.replace(" ", "_"), {}).get("priority", 5)
                    })

    # Assign sequences to new leads
    new_leads = crm.execute(
        "SELECT id, persona FROM leads WHERE sequence_name IS NULL AND is_active=1"
    ).fetchall()
    for lead in new_leads:
        assign_sequence(crm, lead["id"], lead["persona"])

    # Build batch
    print("\n=== BUILDING CAMPAIGN BATCH ===")
    entries = build_campaign_batch(crm, max_new=100, preview=preview)

    if preview:
        return

    added = append_to_queue(entries)
    print(f"✅ Added {added} emails to unified queue")

    # Mark leads as sent (they'll actually send via the unified sender)
    for entry in entries:
        crm.execute("""
            UPDATE leads SET pipeline_stage='sent', sequence_step=sequence_step+1,
            total_touches_sent=total_touches_sent+1,
            last_contacted_at=datetime('now'),
            next_touch_at=datetime('now', '+5 days'),
            updated_at=datetime('now')
            WHERE id=?
        """, (entry["lead_id"],))

        crm.execute("""
            INSERT INTO touch_log (lead_id, touch_type, template_name, subject, sent_at)
            VALUES (?, 'email', ?, ?, datetime('now'))
        """, (entry["lead_id"], entry.get("template", ""), entry["subject"]))

    crm.commit()

    # Status
    print(short_status(crm))
    crm.close()

def cmd_monitor(args: List[str]):
    """Check replies and advance pipeline."""
    crm = get_crm_db()
    pwd = get_gmail_password()
    process_replies(crm, pwd)
    take_snapshot(crm)
    print(short_status(crm))
    crm.close()

def cmd_report(args: List[str]):
    """Print pipeline report."""
    crm = get_crm_db()
    print(pipeline_report(crm))
    crm.close()

def cmd_status(args: List[str]):
    """Quick status."""
    crm = get_crm_db()
    print(short_status(crm))
    crm.close()

def cmd_daemon(args: List[str]):
    """Run continuously: monitor replies, build new batches, and send."""
    print("🔄 GRID Sales Campaign Daemon starting...")
    print(f"   Interval: {INTERVAL}s between sends")
    print(f"   Queue: {QUEUE_FILE}")
    print(f"   CRM: {CRM_DB}")
    print()

    crm = get_crm_db()
    pwd = get_gmail_password()

    cycle = 0
    try:
        while True:
            cycle += 1
            now_str = datetime.now().strftime("%H:%M:%S")

            # Every cycle: check for replies
            process_replies(crm, pwd)

            # Every 12 cycles (~36 min): rebuild queue if low
            if cycle % 12 == 0:
                queue_count = 0
                if QUEUE_FILE.exists():
                    queue_count = sum(1 for _ in open(QUEUE_FILE, encoding='utf-8'))

                if queue_count < 10:
                    print(f"\n  📦 Queue low ({queue_count}), rebuilding...")
                    entries = build_campaign_batch(crm, max_new=50)
                    added = append_to_queue(entries)
                    print(f"  ✅ Added {added} new emails")

                    for entry in entries:
                        crm.execute("""
                            UPDATE leads SET pipeline_stage='sent',
                            sequence_step=sequence_step+1,
                            total_touches_sent=total_touches_sent+1,
                            last_contacted_at=datetime('now'),
                            next_touch_at=datetime('now', '+5 days')
                            WHERE id=?
                        """, (entry["lead_id"],))
                    crm.commit()

            # Every 24 cycles (~72 min): snapshot
            if cycle % 24 == 0:
                take_snapshot(crm)
                print(f"\n  📸 Daily snapshot saved")

            # Every 48 cycles (~2.4 hrs): print status
            if cycle % 48 == 0:
                print(f"\n  [{now_str}] {short_status(crm)}")

            time.sleep(60)  # Check every minute

    except KeyboardInterrupt:
        print(f"\n\n👋 Daemon stopped. {short_status(crm)}")
        crm.close()

def cmd_import(args: List[str]):
    """Import leads from a CSV file."""
    if len(args) < 2:
        print("Usage: sales_campaign_manager.py --import <csv_path> <persona> <source>")
        return

    csv_path = Path(args[0])
    persona = args[1] if len(args) > 1 else "unknown"
    source = args[2] if len(args) > 2 else "imported"

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    crm = get_crm_db()
    leads = load_leads_from_csv(csv_path, persona, source)
    added = 0
    for lead in leads:
        lid = upsert_lead(crm, lead)
        if lid:
            assign_sequence(crm, lid, persona)
            added += 1

    crm.commit()
    print(f"✅ Imported {added} leads (persona={persona}, source={source})")
    print(short_status(crm))
    crm.close()

def cmd_add_lead(args: List[str]):
    """Manually add a single lead."""
    if len(args) < 3:
        print("Usage: sales_campaign_manager.py --add-lead <org_name> <email> <persona> [dept]")
        return

    org = args[0]
    email = args[1]
    persona = args[2]
    dept = args[3] if len(args) > 3 else ""

    crm = get_crm_db()
    lid = upsert_lead(crm, {
        "org_name": org,
        "contact_email": email,
        "persona": persona,
        "source": "manual",
        "dept": dept
    })
    if lid:
        assign_sequence(crm, lid, persona)
        print(f"✅ Added: {org} ({persona}) — stage: queued")

    crm.commit()
    crm.close()

# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "--build": cmd_build,
        "--send": lambda a: cmd_build(a),  # build + add to queue
        "--monitor": cmd_monitor,
        "--report": cmd_report,
        "--status": cmd_status,
        "--daemon": cmd_daemon,
        "--import": cmd_import,
        "--add-lead": cmd_add_lead,
    }

    if cmd in commands:
        commands[cmd](args)
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {list(commands.keys())}")

if __name__ == "__main__":
    main()

"""
SMART INBOX CLEANER — classifies every Gmail inbox message, marks bad senders,
and archives everything. Uses IMAP.

Categories:
  ❌ BOUNCE       — mailer-daemon, undelivered, returned mail → extract recipient, add to gmail_bounced.txt
  🗑️  SPAM/MKTG   — no-reply, newsletters, marketing, promotions
  🔔 NOTIFICATION  — Google alerts, GitHub, LinkedIn, social
  📤 SENT COPY     — own sent messages (Gmail keeps copies in inbox)
  👎 DECLINE       — outreach reply with rejection language → add to bounced
  👍 POSITIVE      — outreach reply with interest/positive language
  📨 PERSONAL      — human reply, not outreach-related
  ❓ UNKNOWN       — can't classify
"""

import imaplib, email, sys, os, re, time
from email.header import decode_header
from pathlib import Path
from collections import Counter

# ── Setup ──────────────────────────────────────────────
import subprocess
r = subprocess.run(["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"],
                   capture_output=True, text=True)
PWD = r.stdout.strip()
if not PWD:
    print("No GMAIL_APP_PASSWORD found"); sys.exit(1)

USER = "charlesaprescottjr@gmail.com"
OUT_DIR = Path("outputs/outreach")
BOUNCE_FILE = OUT_DIR / "gmail_bounced.txt"
DRY_RUN = "--execute" not in sys.argv

# ── Classification patterns ────────────────────────────
BOUNCE_PATTERNS = [
    "mailer-daemon", "mail delivery", "undelivered", "returned mail",
    "delivery status", "delivery has failed", "postmaster@",
    "mail delivery subsystem", "failure notice", "permanent failure",
    "address not found", "user unknown", "mailbox full",
    "over quota", "rejected", "blocked",
]

SPAM_DOMAINS = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "bounce", "bounces", "email", "mail", "mg.", "sendgrid",
    "mailchimp", "campaign", "marketing", "newsletter",
}

SPAM_SENDERS = [
    "noreply@", "no-reply@", "donotreply@", "do-not-reply@",
]

NOTIFICATION_SENDERS = [
    "google.com", "youtube.com", "github.com", "linkedin.com",
    "amazon.com", "paypal.com", "notifications@", "alerts@",
    "info@zoom.us", "no-reply@zoom.us",
]

DECLINE_PHRASES = [
    "does not support", "do not support", "cannot support",
    "unable to support", "not able to", "regret to inform",
    "unfortunately", "not a fit", "not a good fit",
    "not currently funding", "no longer funding",
    "does not align", "not aligned", "not within our",
    "outside our scope", "outside our mission",
    "not currently accepting", "limited resources",
    "not in a position to", "unable to accommodate",
    "decline", "declined", "not interested",
    "funding priorities have changed",
    "focus our resources", "carefully considered",
    "many worthy requests", "limited budget",
    "not this cycle", "not this year",
    "does not provide funding for",
    "do not fund individuals",
    "only fund organizations",
    "only support organizations",
    "remove me", "unsubscribe", "stop emailing",
    "do not contact", "do not email",
]

POSITIVE_PHRASES = [
    "interested", "tell me more", "would like to learn",
    "schedule a call", "let's talk", "please send",
    "would love to", "intrigued", "fascinating",
    "impressive", "great work", "happy to",
    "let's connect", "how can we", "tell us more",
]

def decode_hdr(h):
    if h is None: return ""
    parts = decode_header(h)
    return " ".join(p[0].decode(p[1] or "utf-8", errors="ignore") if isinstance(p[0], bytes) else str(p[0]) for p in parts)

def extract_email(from_hdr):
    """Extract email address from From header like 'Name <email>'."""
    m = re.search(r'<([^>]+@[^>]+)>', from_hdr)
    if m: return m.group(1).strip().lower()
    # Maybe it's just the email
    m2 = re.search(r'([\w.+-]+@[\w-]+\.\w+)', from_hdr)
    if m2: return m2.group(1).strip().lower()
    return from_hdr.strip().lower()

def extract_bounced_recipient(body_text):
    """From a bounce body, extract the original intended recipient."""
    # Look for common bounce patterns
    for pattern in [
        r'<([^>]+@[^>]+)>',  # angle-bracket email
        r'([\w.+-]+@[\w-]+\.\w+)',  # any email
    ]:
        emails = re.findall(pattern, body_text)
        # Skip mailer-daemon, postmaster, etc.
        real = [e.lower() for e in emails if not any(x in e.lower() for x in 
            ['mailer-daemon', 'postmaster', 'amazonses', 'google', 'gmail',
             'smtp', 'mta', 'bounce', 'noreply', 'no-reply'])]
        if real:
            return real[0]
    return ""

def get_body_preview(msg, max_chars=3000):
    """Extract text body from email message (first max_chars chars)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass
                break
            elif ct == "text/html" and not body:
                try:
                    html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    # Strip HTML tags
                    body = re.sub(r'<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body)
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            pass
    return body[:max_chars].strip()

# ── Connect ────────────────────────────────────────────
print("Connecting to Gmail IMAP...")
M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
M.login(USER, PWD)
M.select("INBOX")

status, ids = M.search(None, "ALL")
all_ids = ids[0].split() if ids[0] else []
total = len(all_ids)
print(f"Total inbox: {total} messages")
print()

# ── Load existing bounces ──────────────────────────────
existing_bounces = set()
if BOUNCE_FILE.exists():
    existing_bounces = {l.strip().lower() for l in BOUNCE_FILE.read_text().splitlines() if l.strip()}
print(f"Existing bounces: {len(existing_bounces)}")

# ── Scan all messages ──────────────────────────────────
results = []
categories = Counter()
new_bounces = set()
stats = {"bounce": 0, "spam": 0, "notification": 0, "self": 0, 
         "decline": 0, "positive": 0, "personal": 0, "unknown": 0}

print(f"\nScanning {total} messages...")
print(f"{'='*120}")

processed = 0
# Process newest first
for num in reversed(all_ids):
    processed += 1
    try:
        s, d = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE REPLY-TO)])")
        if s != "OK": continue
        hdr_raw = d[0][1].decode("utf-8", errors="ignore") if isinstance(d[0][1], bytes) else str(d[0][1])
    except:
        continue

    from_v = subj_v = date_v = reply_to = ""
    for line in hdr_raw.split("\n"):
        l = line.strip()
        if l.lower().startswith("from:"): from_v = decode_hdr(l[5:].strip())
        if l.lower().startswith("subject:"): subj_v = decode_hdr(l[8:].strip())
        if l.lower().startswith("date:"): date_v = l[5:].strip()
        if l.lower().startswith("reply-to:"): reply_to = decode_hdr(l[9:].strip())

    from_email = extract_email(from_v)
    h_lower = hdr_raw.lower()
    subj_lower = subj_v.lower()
    
    # ── CLASSIFY ──
    category = None
    detail = ""
    
    # 1. Check bounce first
    is_bounce = any(x in h_lower for x in BOUNCE_PATTERNS) or \
                any(x in subj_lower for x in ["undelivered", "returned mail", "delivery failed", "failure notice"])
    if is_bounce:
        category = "bounce"
        # Get body to extract the original recipient
        try:
            s2, d2 = M.fetch(num, "(BODY.PEEK[TEXT])")
            if s2 == "OK":
                body_raw = d2[0][1].decode("utf-8", errors="ignore") if isinstance(d2[0][1], bytes) else str(d2[0][1])
                bounced_addr = extract_bounced_recipient(body_raw)
                if bounced_addr and bounced_addr not in existing_bounces and bounced_addr != from_email:
                    new_bounces.add(bounced_addr)
                    detail = f"→ bounced: {bounced_addr}"
        except:
            pass
    
    # 2. Self-sent
    elif "charlesaprescott" in from_v.lower() or USER in from_email:
        category = "self"
    
    # 3. Spam/Marketing
    elif any(x in from_email.lower() for x in SPAM_SENDERS) or \
         any(x in h_lower for x in ["unsubscribe", "opt-out", "preferences"]):
        # Check if it's also a real reply
        if any(x in subj_lower for x in ["re:", "reply"]):
            # Could be a real reply from someone using a noreply address (unlikely but possible)
            category = "unknown"
        else:
            category = "spam"
    
    # 4. Notifications
    elif any(x in from_email.lower() for x in NOTIFICATION_SENDERS):
        category = "notification"
    
    # 5. The rest need body analysis
    else:
        # Fetch body for classification
        try:
            s2, d2 = M.fetch(num, "(BODY.PEEK[TEXT])")
            body_text = ""
            if s2 == "OK":
                body_raw = d2[0][1].decode("utf-8", errors="ignore") if isinstance(d2[0][1], bytes) else str(d2[0][1])
                body_text = body_raw[:3000].lower()
        except:
            body_text = ""
        
        # Check for decline language
        if body_text:
            decline_hits = [p for p in DECLINE_PHRASES if p in body_text]
            positive_hits = [p for p in POSITIVE_PHRASES if p in body_text]
            
            if decline_hits:
                category = "decline"
                detail = f"rejected: {', '.join(decline_hits[:3])}"
                if from_email and '@' in from_email and from_email not in existing_bounces:
                    new_bounces.add(from_email)
                    detail += f" → added {from_email}"
            elif positive_hits:
                category = "positive"
                detail = f"interested: {', '.join(positive_hits[:3])}"
            elif any(x in body_text for x in ["unsubscribe", "opt-out", "marketing"]):
                category = "spam"
            elif any(x in from_email.lower() for x in NOTIFICATION_SENDERS):
                category = "notification"
            elif "re:" in subj_lower or "reply" in subj_lower:
                category = "personal"
            else:
                category = "unknown"
        else:
            if "re:" in subj_lower:
                category = "personal"
            else:
                category = "unknown"

    # ── Store result ──
    categories[category] += 1
    stats[category] = stats.get(category, 0) + 1
    result = {
        "num": num.decode() if isinstance(num, bytes) else num,
        "from": from_v, "from_email": from_email,
        "subject": subj_v, "date": date_v,
        "category": category, "detail": detail,
    }
    results.append(result)
    
    # Print live
    emoji = {"bounce": "❌", "spam": "🗑️", "notification": "🔔", "self": "📤",
             "decline": "👎", "positive": "👍", "personal": "📨", "unknown": "❓"}.get(category, "❓")
    print(f"  {emoji} {category:12s} | {date_v[:25]:25s} | {from_email[:45]:45s} | {subj_v[:60]}")
    if detail:
        print(f"     {'':12s} | {'':25s} | {'':45s} | {detail}")

# ── Summary ────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"Total scanned:   {total:>6}")
for cat in ["bounce", "spam", "notification", "self", "decline", "positive", "personal", "unknown"]:
    if stats.get(cat, 0) > 0:
        emoji = {"bounce": "❌", "spam": "🗑️", "notification": "🔔", "self": "📤",
                 "decline": "👎", "positive": "👍", "personal": "📨", "unknown": "❓"}.get(cat, "")
        print(f"  {emoji} {cat:14s}: {stats.get(cat, 0):>6}")

print(f"\nNew bounce addresses: {len(new_bounces)}")
if new_bounces:
    for addr in sorted(new_bounces):
        print(f"  🚫 {addr}")

if DRY_RUN:
    print(f"\n{'='*60}")
    print(f"DRY RUN — no changes made.")
    print(f"Run with --execute to archive all and add bounces.")
else:
    # ── Execute: Add bounces ──
    if new_bounces:
        with open(BOUNCE_FILE, "a") as f:
            for addr in sorted(new_bounces):
                f.write(f"{addr}\n")
        print(f"\n✅ Added {len(new_bounces)} addresses to {BOUNCE_FILE}")
    
    # ── Execute: Archive all inbox messages ──
    print(f"\nArchiving {total} messages from inbox...")
    archived = 0
    for i, r in enumerate(results):
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{total}...")
        try:
            # Remove INBOX label (archive) and add Trash
            M.store(r["num"], "+X-GM-LABELS", "\\Trash")
            M.store(r["num"], "+FLAGS", "\\Deleted")
            archived += 1
        except Exception as e:
            print(f"  Failed on msg {r['num']}: {e}")
    
    M.expunge()
    print(f"Archived {archived}/{total} messages")
    
    # Verify
    M.select("INBOX")
    s, ids = M.search(None, "ALL")
    remaining = ids[0].split() if ids[0] else []
    print(f"Inbox now: {len(remaining)} messages")

M.close()
M.logout()
print("\n✅ Done!")

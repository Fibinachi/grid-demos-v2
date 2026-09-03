"""  
UNIFIED CONTINUOUS SENDER — processes queue 24/7 at 1 email per 3 minutes.
Reads from unified_queue.jsonl, skips already-sent, sends continuously.
Validates emails via ZeroBounce before sending to prevent bounces.
When queue is empty, waits and re-checks for new campaigns.
"""
import json, smtplib, time, os, sys, urllib.request, urllib.parse, imaplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    import subprocess
    r = subprocess.run(["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"], capture_output=True, text=True)
    PWD = r.stdout.strip()
if not PWD:
    print("Set GMAIL_APP_PASSWORD"); sys.exit(1)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
INTERVAL = 180  # 3 minutes
ZB_KEY = os.environ.get("ZEROBOUNCE_API_KEY", "")
ZB_WARNED = False  # Only warn once about bad key

def validate_email(email: str) -> str:
    """Validate email via ZeroBounce. Returns status: 'valid', 'invalid', 'catch-all', 'unknown', 'do_not_mail', 'error', 'bad_key'."""
    global ZB_WARNED
    if not ZB_KEY or not email:
        return "no_key"
    url = f"https://api.zerobounce.net/v2/validate?api_key={ZB_KEY}&email={urllib.parse.quote(email)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if "error" in data:
            if not ZB_WARNED:
                print(f"  ⚠️ ZeroBounce: {data['error']} — check ZEROBOUNCE_API_KEY and credits")
                ZB_WARNED = True
            return "bad_key"
        return data.get("status", "error")
    except Exception as e:
        if not ZB_WARNED:
            print(f"  ⚠️ ZeroBounce request failed: {e}")
            ZB_WARNED = True
        return "error"

# When to skip: invalid, catch-all, do_not_mail, spam-trap
SKIP_STATUSES = {"invalid", "catch-all", "do_not_mail", "spamtrap"}

OUT = Path("outputs/outreach")
QUEUE_FILE = OUT / "unified_queue.jsonl"
SENT_LOG = OUT / "gmail_sent.txt"
CHURCH_SENT = OUT / "church_campaign_sent.txt"
FAIL_LOG = OUT / "gmail_failed.txt"
BOUNCE_FILE = OUT / "gmail_bounced.txt"

def now(): return datetime.now().strftime("%H:%M:%S")

def load_bounces():
    """Load set of bounced email addresses."""
    bounces = set()
    if BOUNCE_FILE.exists():
        for line in BOUNCE_FILE.read_text().strip().split("\n"):
            if line.strip():
                bounces.add(line.strip().lower())
    return bounces

def mark_bounced(to_addr):
    """Add an address to the permanent bounce list."""
    bounced_set.add(to_addr.strip().lower())
    with open(BOUNCE_FILE, "a") as f:
        f.write(f"{to_addr.strip().lower()}\n")

def load_sent():
    sent = set()
    for log in [SENT_LOG, CHURCH_SENT]:
        if log.exists():
            for line in log.read_text().strip().split("\n"):
                if line.strip():
                    sent.add(line.strip())
    return sent

def mark_sent(org, church_id=None):
    with open(SENT_LOG, "a") as f:
        f.write(f"{org}\n")
    if church_id:
        with open(CHURCH_SENT, "a") as f:
            f.write(f"{church_id}\n")

def mark_failed(to_addr, error):
    """Log failure and add to permanent bounce list."""
    with open(FAIL_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()},{to_addr},{str(error)[:100]}\n")
    mark_bounced(to_addr)

def load_queue():
    if not QUEUE_FILE.exists():
        return []
    items = []
    with open(QUEUE_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    # Also load bounce retry queue
    retry_file = OUT / "bounce_retry_queue.jsonl"
    if retry_file.exists():
        with open(retry_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
    return items

def send_email(to_addr, subject, body):
    msg = MIMEMultipart()
    msg["From"] = FROM
    msg["To"] = to_addr
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Disposition-Notification-To"] = FROM  # Request read receipt
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls()
        s.login("charlesaprescottjr@gmail.com", PWD)
        s.send_message(msg)

# ============================================================
# INBOX BOUNCE CLEANER
# ============================================================

def sweep_inbox():
    """Check inbox for new bounces, archive them, and return count."""
    BOUNCE_PATTERNS = [
        "mailer-daemon", "mail delivery", "undelivered", "returned mail",
        "delivery status", "delivery has failed", "postmaster@",
        "mail delivery subsystem", "failure notice",
    ]
    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=15)
        M.login("charlesaprescottjr@gmail.com", PWD)
        M.select("INBOX")
        s, ids = M.search(None, "ALL")
        all_ids = ids[0].split() if ids[0] else []
        if not all_ids:
            M.logout(); return 0, 0

        to_trash = []
        for num in all_ids:
            s2, d2 = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            if s2 != "OK": continue
            hdr = d2[0][1].decode("utf-8", errors="ignore") if isinstance(d2[0][1], bytes) else str(d2[0][1])
            if any(x in hdr.lower() for x in BOUNCE_PATTERNS):
                to_trash.append(num)

        bounce_count = len(to_trash)
        for num in to_trash:
            M.store(num, "+X-GM-LABELS", "\\Trash")
            M.store(num, "+FLAGS", "\\Deleted")
        M.expunge()

        M.select("INBOX")
        s, ids = M.search(None, "ALL")
        remaining = len(ids[0].split()) if ids[0] else 0
        M.logout()
        return bounce_count, remaining
    except:
        return 0, -1

# ============================================================
# MAIN LOOP
# ============================================================
print(f"[{now()}] Unified Sender starting...")
print(f"  Queue: {QUEUE_FILE}")
print(f"  Rate: 1 per {INTERVAL}s ({3600/INTERVAL:.0f}/hr)")
print(f"  Features: countdown + auto-bounce-sweep")
print()

sent_set = load_sent()
bounced_set = load_bounces()
print(f"  Already sent: {len(sent_set)}")
print(f"  Bounced: {len(bounced_set)}")
print()

ok = fail = skipped = sweep_bounces = 0
batch_num = 0

while True:
    queue = load_queue()
    
    # Filter to unsent and not bounced
    unsent = []
    for item in queue:
        key = item.get("org", item.get("to", ""))
        to_addr = (item.get("email") or item.get("to") or "").strip().lower()
        if key in sent_set:
            continue
        if to_addr in bounced_set:
            skipped += 1
            continue
        unsent.append(item)
    
    if not unsent:
        remaining_q = len(queue)
        print(f"[{now()}] Queue empty ({remaining_q} total, {ok} sent, {fail} fail, {skipped} skipped, {sweep_bounces} bounces swept)")
        print(f"  Waiting for new campaigns...")
        time.sleep(300)  # Check every 5 min
        sent_set = load_sent()
        bounced_set = load_bounces()
        continue
    
    batch_num += 1
    item = unsent[0]
    to_addr = item.get("email") or item.get("to") or ""
    org = item.get("org", to_addr)
    source = item.get("source", "unknown")
    remaining = len(unsent)
    
    # Live status line
    eta = (remaining * INTERVAL) / 3600
    print(f"\n[{now()}] #{batch_num} | left: {remaining} | sent: {ok} | fail: {fail} | bounces swept: {sweep_bounces} | ETA: {eta:.1f}h")
    print(f"  [{source}] {org[:55]} -> {to_addr[:45]}")

    # Pre-validate with ZeroBounce
    status = validate_email(to_addr)
    if status in SKIP_STATUSES:
        print(f"  🚫 ZeroBounce: {status}")
        fail += 1
        mark_failed(to_addr, f"ZeroBounce: {status}")
        skipped += 1
        time.sleep(INTERVAL)
        continue
    
    # Send
    try:
        send_email(to_addr, item["subject"], item["body"])
        ok += 1
        mark_sent(org, item.get("church_id"))
        sent_set.add(org)
    except Exception as e:
        fail += 1
        mark_failed(to_addr, e)
        sent_set.add(org)
        print(f"  ❌ FAIL: {e}")
    
    # Countdown timer
    secs = INTERVAL
    while secs > 0:
        mins, s = divmod(secs, 60)
        print(f"\r  ⏳ Next send in {mins:02d}:{s:02d}  ", end="", flush=True)
        time.sleep(1)
        secs -= 1
    print("\r" + " " * 40 + "\r", end="", flush=True)
    
    # Sweep inbox for bounces
    new_bounces, inbox_left = sweep_inbox()
    if new_bounces > 0:
        sweep_bounces += new_bounces
        print(f"  🧹 Swept {new_bounces} bounces from inbox ({inbox_left} remaining)")

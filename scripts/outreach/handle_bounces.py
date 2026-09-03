"""
BOUNCE HANDLER — Scan Gmail inbox for mailer-daemon bounces, identify failed emails,
log them, and if an alternative email exists for the org, queue a retry.

Run daily: .\.venv\Scripts\python.exe scripts\outreach\handle_bounces.py
"""
import imaplib, email, re, json, os, time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# --- CONFIG ---
PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    PWD = os.popen("powershell -c \"[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','Machine')\"").read().strip()
if not PWD:
    print("Set GMAIL_APP_PASSWORD"); exit(1)

OUT = Path("outputs/outreach")
BOUNCE_LOG = OUT / "bounces.txt"
RETRY_QUEUE = OUT / "bounce_retry_queue.jsonl"
SENT_LOG = OUT / "gmail_sent.txt"

# Load all lead files for email → org lookup
LEAD_FILES = [
    "faith_media_leads.json", "faith_hunger_leads.json",
    "seminaries_leads.json", "academic_leads.json",
    "buddhist_sikh_bahai_leads.json", "embassy_leads.json"
]

email_to_org = {}  # email → {org, source_file}
org_alts = defaultdict(list)  # org → [alt emails]

for fname in LEAD_FILES:
    fp = OUT / fname
    if not fp.exists(): continue
    leads = json.load(open(fp))
    for l in leads:
        e = l.get('email', '').lower().strip()
        o = l.get('org', '')
        if e and o:
            email_to_org[e] = {'org': o, 'source': fname}
            org_alts[o.lower()].append(e)

print(f"Loaded {len(email_to_org)} email→org mappings from {len(LEAD_FILES)} lead files")
orgs_with_alts = sum(1 for v in org_alts.values() if len(v) > 1)
print(f"  {orgs_with_alts} orgs have multiple email addresses for fallback")

# --- SCAN INBOX ---
print(f"\n[{datetime.now().strftime('%H:%M')}] Scanning Gmail inbox for bounces...")
try:
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
    M.login("charlesaprescottjr@gmail.com", PWD)
    M.select("INBOX")
    
    # Search for bounces from various sources
    bounce_senders = [
        "mailer-daemon@googlemail.com",
        "postmaster@",
        "MAILER-DAEMON@",
        "mailchannels@",
    ]
    
    seen_ids = set()
    bounces_found = []
    
    for sender in bounce_senders:
        status, ids = M.search(None, "FROM", sender)
        if status != "OK" or not ids[0]: continue
        for num in ids[0].split():
            n = num.decode() if isinstance(num, bytes) else num
            if n in seen_ids: continue
            seen_ids.add(n)
            
            s, d = M.fetch(num, "(RFC822)")
            if s != "OK": continue
            msg = email.message_from_bytes(d[0][1])
            subj = msg.get("Subject", "")
            body = ""
            if msg.is_multipart():
                for p in msg.walk():
                    if p.get_content_type() == "text/plain":
                        body = p.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            
            # Extract failed email addresses from bounce body
            found_emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", body)
            targets = [e.strip('.,;:)>]') for e in found_emails 
                      if e.lower().strip('.,;:)>]') not in ("charlesaprescottjr@gmail.com", "mailer-daemon@googlemail.com")
                      and not e.lower().strip('.,;:)>]').startswith("mailer-daemon")]
            
            # Extract failure reason
            reason = ""
            for line in body.split("\n"):
                l = line.strip().lower()
                for keyword in ["5.1.1", "5.1.0", "5.2.2", "5.7.1", "address rejected",
                                "doesn't exist", "not found", "unrouteable", "disabled",
                                "inactive", "mailbox full", "blocked", "spam", "550",
                                "552", "554", "user unknown", "no such user"]:
                    if keyword in l:
                        reason = line.strip()[:150]
                        break
                if reason: break
            if not reason:
                # Try to find diagnostic code
                for line in body.split("\n"):
                    if any(x in line for x in ("Diagnostic-Code", "remote-mta", "Status:")):
                        reason = line.strip()[:150]
                        break
            
            for t in targets:
                bounces_found.append({
                    "email": t.lower(),
                    "reason": reason or "unknown",
                    "subject": subj[:100],
                    "timestamp": datetime.now().isoformat()
                })
    
    M.logout()
    
except Exception as e:
    print(f"IMAP error: {e}")
    exit(1)

# --- PROCESS BOUNCES ---
print(f"\nFound {len(bounces_found)} bounced addresses")

new_bounces = 0
retry_entries = []

for b in bounces_found:
    email_addr = b['email']
    reason = b['reason']
    
    # Check if already logged
    if BOUNCE_LOG.exists():
        existing = BOUNCE_LOG.read_text()
        if email_addr in existing:
            continue
    
    # Log the bounce
    with open(BOUNCE_LOG, "a") as f:
        f.write(f"{email_addr}|{reason}|{b['timestamp']}\n")
    new_bounces += 1
    
    # Look up org
    info = email_to_org.get(email_addr)
    if info:
        org = info['org']
        print(f"\n❌ BOUNCE: {email_addr}")
        print(f"   Org: {org}")
        if reason: print(f"   Reason: {reason[:120]}")
        
        # Check for alternative email for this org
        org_key = org.lower()
        alts = [e for e in org_alts.get(org_key, []) if e != email_addr]
        
        if alts:
            alt = alts[0]
            print(f"   ➡ Alternative: {alt}")
            retry_entries.append({
                "to": alt,
                "org": org,
                "bounced_email": email_addr,
                "reason": reason,
                "source": "bounce_retry",
                "timestamp": b['timestamp']
            })
        else:
            print(f"   ⚠ No alternative email found for {org}")
    else:
        # Check if it matches any org by fuzzy domain match
        domain = email_addr.split('@')[1] if '@' in email_addr else ''
        matches = [org for e, org in email_to_org.items() if domain in e]
        if matches:
            print(f"\n❌ BOUNCE: {email_addr} (similar to: {matches[0]['org']})")
            print(f"   Reason: {reason[:120]}")
        else:
            print(f"\n❌ BOUNCE: {email_addr} (no matching org in leads)")
            if reason: print(f"   Reason: {reason[:120]}")

# --- SAVE RETRY QUEUE ---
if retry_entries:
    with open(RETRY_QUEUE, "a") as f:
        for entry in retry_entries:
            f.write(json.dumps(entry) + "\n")
    print(f"\n📋 {len(retry_entries)} retries appended to {RETRY_QUEUE}")

# --- MARK BOUNCED EMAILS AS SENT (to prevent re-send) ---
# Update gmail_sent.txt with bounced emails so senders skip them
bounced_emails = {b['email'] for b in bounces_found}
if bounced_emails and SENT_LOG.exists():
    # Also append bounces to sent log with marker
    with open(SENT_LOG, "a") as f:
        for b in bounces_found:
            f.write(f"{b['email']} (BOUNCED: {b['reason'][:60]})\n")
    print(f"   {len(bounced_emails)} bounced emails marked in sent log to prevent re-send")

# --- DATABASE CLEANUP: Remove bad emails from church_contact_values ---
import sqlite3
print(f"\n{'='*50}")
print(f"DATABASE CLEANUP")
print(f"{'='*50}")

db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Collect all unique bounced emails (new + previously logged)
all_bounced = set(b['email'] for b in bounces_found)
if BOUNCE_LOG.exists():
    for line in BOUNCE_LOG.read_text().strip().split('\n'):
        if line.strip():
            all_bounced.add(line.split('|')[0].strip())

cleaned = 0
deleted_churches = set()

for email_addr in sorted(all_bounced):
    # Find matching rows in church_contact_values
    rows = db.execute(
        "SELECT id, church_id, value FROM church_contact_values WHERE value = ? AND contact_type = 'email'",
        (email_addr,)
    ).fetchall()
    
    if not rows:
        continue
    
    for row in rows:
        cv_id = row['id']
        church_id = row['church_id']
        value = row['value']
        
        # Log to enrichment_change_log before deleting
        db.execute(
            "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (church_id, 'email', value, '(BOUNCED)', 'bounce_handler',)
        )
        
        # Delete the bad email
        db.execute("DELETE FROM church_contact_values WHERE id = ?", (cv_id,))
        deleted_churches.add(church_id)
        cleaned += 1

db.commit()

# Log provenance
if cleaned:
    import sys
    db.execute(
        "INSERT INTO provenance_log (source, script_name, churches_updated, churches_inserted, fields_populated, status, notes, started_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        ('bounce_cleanup', 'handle_bounces.py', len(deleted_churches), 0,
         json.dumps(['email']), 'completed',
         f'Removed {cleaned} bounced email(s) from {len(deleted_churches)} church(es)')
    )
    db.commit()

db.close()

if cleaned:
    print(f"  🗑️  Removed {cleaned} bounced email(s) from {len(deleted_churches)} church(es)")
else:
    print(f"  ✓ No bounced emails found in church_contact_values")

# --- SUMMARY ---
print(f"\n{'='*50}")
print(f"BOUNCE SCAN COMPLETE")
print(f"{'='*50}")
print(f"  New bounces logged: {new_bounces}")
print(f"  Retries queued:     {len(retry_entries)}")
print(f"  DB emails cleaned:  {cleaned}")
print(f"  Total bounce log:   {len(BOUNCE_LOG.read_text().split(chr(10))) if BOUNCE_LOG.exists() else 0} entries")
print(f"\nRun retries with: .\\.venv\\Scripts\\python.exe scripts\\outreach\\send_unified.py")
print(f"(retries will be picked up from bounce_retry_queue.jsonl)")

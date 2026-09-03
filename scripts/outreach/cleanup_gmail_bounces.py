"""
Gmail Inbox Cleanup — delete bounce/failure notifications from outreach.
Connects via IMAP with Gmail App Password, finds all delivery failure emails,
extracts bounced addresses for the bounce log, and trashes them.

Usage:
    python scripts/outreach/cleanup_gmail_bounces.py --preview   # Just count, don't delete
    python scripts/outreach/cleanup_gmail_bounces.py             # Delete bounces
    python scripts/outreach/cleanup_gmail_bounces.py --days 7    # Only last 7 days
"""

import imaplib, email, os, re, sys, time
from email.header import decode_header
from pathlib import Path

EMAIL = "charlesaprescottjr@gmail.com"
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# Bounce indicators in subject or from
BOUNCE_FROM = ["mailer-daemon@googlemail.com", "mailer-daemon@", "postmaster@",
               "MAILER-DAEMON", "Mail Delivery Subsystem"]
BOUNCE_SUBJECT = ["undelivered", "delivery status", "failure notice",
                  "returned mail", "mail delivery failed", "delivery failure",
                  "could not be delivered", "undeliverable", "message blocked",
                  "address rejected", "not found", "does not exist",
                  "mail delivery system", "delayed delivery",
                  "warning: could not send", "postmaster notify"]

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
BOUNCE_LOG = OUT / "gmail_bounced.txt"

# ── Progress bar ──
def progress_bar(current, total, label='', width=40):
    if total == 0: return
    pct = current / total
    filled = int(width * pct)
    bar = chr(0x2588) * filled + chr(0x2591) * (width - filled)
    sys.stderr.write(f'\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)')
    sys.stderr.flush()
    if current >= total: sys.stderr.write('\n')

def decode_str(s):
    """Decode email header value."""
    if s is None: return ""
    decoded = decode_header(s)
    result = []
    for part, charset in decoded:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8', errors='ignore'))
            except:
                result.append(part.decode('utf-8', errors='ignore'))
        else:
            result.append(str(part))
    return ' '.join(result)

def is_bounce(msg):
    """Check if an email is a bounce/failure notification."""
    subject = decode_str(msg.get("Subject", "")).lower()
    from_addr = decode_str(msg.get("From", "")).lower()

    # Check from address
    for pattern in BOUNCE_FROM:
        if pattern.lower() in from_addr:
            return True

    # Check subject
    for pattern in BOUNCE_SUBJECT:
        if pattern in subject:
            return True

    return False

def extract_bounced_address(msg):
    """Try to extract the bounced email address from the bounce message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(errors="ignore")
                except:
                    pass
                break
    else:
        try:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        except:
            pass

    # Common patterns in Gmail bounce messages
    patterns = [
        r"The email account that you tried to reach does not exist[.\s]*.*?<([^>]+@[^>]+)>",
        r"address not found[.\s]*.*?<([^>]+@[^>]+)>",
        r"recipient address rejected[.\s]*.*?<([^>]+@[^>]+)>",
        r"couldn't be delivered to.*?<([^>]+@[^>]+)>",
        r"could not be delivered.*?<([^>]+@[^>]+)>",
        r"Your message to ([^\s]+@[^\s]+) couldn't be delivered",
        r"Delivery to ([^\s]+@[^\s]+) failed",
        r"Message blocked[.\s]*.*?<([^>]+@[^>]+)>",
        r"<([^>]+@[^>]+)>:\s*(?:Recipient address rejected|User unknown|No such user|Mailbox not found)",
    ]

    for pat in patterns:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            return m.group(1).strip().lower()

    # Fallback: look for X-Failed-Recipients header
    failed = msg.get("X-Failed-Recipients", "")
    if failed:
        return failed.strip().lower()

    return None

def main():
    preview = "--preview" in sys.argv
    days_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            days_filter = int(sys.argv[i + 1])

    # Get password
    pwd = os.environ.get("GMAIL_APP_PASSWORD")
    if not pwd:
        pwd = os.popen('powershell -c "[Environment]::GetEnvironmentVariable(\'GMAIL_APP_PASSWORD\',\'User\')"').read().strip()
    if not pwd:
        print("ERROR: GMAIL_APP_PASSWORD not set")
        sys.exit(1)

    print("=" * 60)
    print("GMAIL BOUNCE CLEANUP")
    print("=" * 60)

    # Connect
    print(f"\nConnecting to {EMAIL} via IMAP...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL, pwd)
    mail.select("inbox")
    print("  Connected.")

    # Build search criteria — search for mailer-daemon FROM + bounce subjects
    search_query = 'OR OR FROM "mailer-daemon@googlemail.com" FROM "mailer-daemon" FROM "MAILER-DAEMON"'

    if days_filter:
        search_query = f"({search_query}) SINCE {days_filter}d"

    print(f"\nSearching for bounces{' (last '+str(days_filter)+' days)' if days_filter else ''}...")
    status, msg_ids = mail.search(None, search_query)
    if status != "OK":
        print("  No matching messages.")
        mail.logout()
        return

    all_ids = msg_ids[0].split()
    print(f"  Found {len(all_ids)} bounce messages")

    # Also search with simplified subject queries individually
    for subj in ["undelivered", "returned mail", "delivery failed"]:
        try:
            status, sj_ids = mail.search(None, f'SUBJECT "{subj}"')
            if status == "OK" and sj_ids[0]:
                extra = sj_ids[0].split()
                new = [x for x in extra if x not in all_ids]
                all_ids.extend(new)
                if new:
                    print(f"  + {len(new)} from subject '{subj}'")
        except Exception:
            pass

    print(f"  Total candidates: {len(all_ids)}")

    # Fetch and classify
    print(f"\nFetching and classifying {len(all_ids)} messages...")
    bounces = []
    bounced_addresses = set()
    t0 = time.time()

    for i, msg_id in enumerate(all_ids):
        try:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            if is_bounce(msg):
                subject = decode_str(msg.get("Subject", ""))
                from_addr = decode_str(msg.get("From", ""))
                bounced_addr = extract_bounced_address(msg)

                bounces.append({
                    "msg_id": msg_id,
                    "subject": subject[:80],
                    "from": from_addr[:60],
                    "bounced": bounced_addr,
                })

                if bounced_addr:
                    bounced_addresses.add(bounced_addr)
        except Exception:
            pass

        if (i + 1) % 50 == 0:
            progress_bar(i + 1, len(all_ids), "  Classifying")

    progress_bar(len(all_ids), len(all_ids), "  Classifying")
    elapsed = time.time() - t0

    print(f"\n  Confirmed bounces: {len(bounces)} (in {elapsed:.1f}s)")
    print(f"  Unique bounced addresses: {len(bounced_addresses)}")

    # Show sample
    print(f"\n  Sample bounces:")
    for b in bounces[:10]:
        addr = f" → {b['bounced']}" if b['bounced'] else ""
        print(f"    {b['subject'][:60]}{addr}")

    if preview:
        print(f"\n⚠️  PREVIEW ONLY — {len(bounces)} bounces identified. Remove --preview to delete.")
        mail.logout()

        # Still update bounce log in preview
        if bounced_addresses:
            existing = set()
            if BOUNCE_LOG.exists():
                existing = set(BOUNCE_LOG.read_text().strip().split("\n"))
            new = bounced_addresses - existing
            print(f"  Would add {len(new)} new addresses to bounce log:")
            for a in sorted(new)[:10]:
                print(f"    {a}")
        return

    # Delete bounces
    if not bounces:
        print("\n  No bounces to delete.")
        mail.logout()
        return

    confirm = input(f"\nDelete {len(bounces)} bounce messages? (y/n): ").strip().lower()
    if confirm != 'y':
        print("  Cancelled.")
        mail.logout()
        return

    print(f"\nMoving {len(bounces)} messages to trash...")
    for i, b in enumerate(bounces):
        try:
            mail.store(b['msg_id'], '+X-GM-LABELS', '\\Trash')
        except Exception:
            pass
        if (i + 1) % 50 == 0:
            progress_bar(i + 1, len(bounces), "  Trashing")

    progress_bar(len(bounces), len(bounces), "  Trashing")
    mail.expunge()
    print(f"  ✅ {len(bounces)} messages moved to Trash")

    # Update bounce log
    if bounced_addresses:
        existing = set()
        if BOUNCE_LOG.exists():
            existing = set(BOUNCE_LOG.read_text().strip().split("\n"))
        new = bounced_addresses - existing
        if new:
            all_bounces = existing | bounced_addresses
            BOUNCE_LOG.write_text("\n".join(sorted(all_bounces)) + "\n")
            print(f"  ✅ Added {len(new)} new bounced addresses to {BOUNCE_LOG}")

    mail.logout()
    print(f"\nDone. Check Gmail Trash to permanently delete.")

if __name__ == "__main__":
    main()

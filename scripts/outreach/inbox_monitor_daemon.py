"""
Auto Inbox Monitor + Bounce Tracker + Decline Detector
=======================================================
Runs continuously, checking inbox every 30 minutes for:
  1. Bounce notifications -> extracts bounced emails -> updates bounce list
  2. Real replies from foundations -> logs & checks for polite declines
  3. Auto-adds decliners to declined_foundations.txt so senders skip them
  4. Maintains clean contact list by removing bounces

Usage:
  python inbox_monitor_daemon.py              # Run once
  nohup python3 inbox_monitor_daemon.py &     # Background on EC2
"""

import imaplib
import os
import re
import time
import json
import csv
import sys
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import the shared decline tracker
sys.path.insert(0, SCRIPT_DIR)
from declined_foundations import (
    add_declined, is_decline, is_human_reply, lookup_ein_by_email,
    extract_body_text, load_declined_eins
)

KNOWN_FILE = os.path.join(SCRIPT_DIR, "known_message_ids.txt")
BOUNCE_LOG = os.path.join(SCRIPT_DIR, "bounced_emails.txt")
REPLY_LOG = os.path.join(SCRIPT_DIR, "foundation_replies.json")
CHECK_LOG = os.path.join(SCRIPT_DIR, "inbox_check_log.txt")
ENRICHED_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
CLEAN_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts_clean.csv")

IMAP_HOST = "imap.hostinger.com"
IMAP_USER = "charles@columbiataxlawyer.com"
IMAP_PASS = os.environ.get("EMAIL_PASSWORD", "FlorenceFlamingo1!")
CHECK_INTERVAL = 1800  # 30 minutes


def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        with open(CHECK_LOG, "a") as f:
            f.write(line + "\n")
    except:
        pass


def check_inbox():
    """Check inbox for new messages, extract bounces, replies, and declines."""
    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=30)
        M.login(IMAP_USER, IMAP_PASS)
        M.select("INBOX")

        status, ids = M.search(None, "ALL")
        all_ids = ids[0].split() if ids[0] else []

        # Load known IDs
        known = set()
        try:
            with open(KNOWN_FILE) as f:
                known = set(line.strip() for line in f)
        except:
            pass

        # Load existing bounces
        existing_bounces = set()
        try:
            with open(BOUNCE_LOG) as f:
                for line in f:
                    existing_bounces.add(line.strip())
        except:
            pass

        new_bounces = set()
        new_replies = []
        new_declines = 0

        for num in all_ids:
            nid = num.decode() if isinstance(num, bytes) else str(num)
            if nid in known:
                continue

            # Fetch just headers first
            st, d = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if st != "OK":
                continue
            header_text = ""
            if isinstance(d[0][1], bytes):
                header_text = d[0][1].decode("utf-8", "ignore")
            elif len(d) > 1 and d[1] and isinstance(d[1][0], bytes):
                header_text = d[1][0].decode("utf-8", "ignore")

            from_v = subj_v = ""
            for line in header_text.split("\n"):
                l = line.strip()
                if l.lower().startswith("from:"):
                    from_v = l[5:].strip()
                if l.lower().startswith("subject:"):
                    subj_v = l[8:].strip()

            hl = (from_v + " " + subj_v).lower()

            # --- BOUNCE DETECTION ---
            if "mailer-daemon" in from_v.lower() or "amazonses" in from_v.lower():
                st2, d2 = M.fetch(num, "(BODY[])")
                if st2 == "OK":
                    msg_bytes = b""
                    for part in d2:
                        if isinstance(part, tuple):
                            msg_bytes += part[1] if isinstance(part[1], bytes) else b""
                    body = msg_bytes.decode("utf-8", "ignore")
                    for m in re.finditer(r'Final-Recipient:\s*rfc822;\s*([\w.+-]+@[\w.-]+\.\w{2,4})', body, re.IGNORECASE):
                        a = m.group(1).lower()
                        if a not in existing_bounces:
                            new_bounces.add(a)
                    for m in re.finditer(r'Original-Recipient:\s*rfc822;\s*([\w.+-]+@[\w.-]+\.\w{2,4})', body, re.IGNORECASE):
                        a = m.group(1).lower()
                        if a not in existing_bounces:
                            new_bounces.add(a)
                log("Bounce: %s - %d new" % (from_v[:40], len(new_bounces)))

            # --- REAL REPLY DETECTION ---
            elif any(
                kw in from_v.lower()
                for kw in ["foundation", "charities", "philanthropy", "grant"]
            ) and "columbiataxlawyer" not in from_v.lower():
                new_replies.append({"from": from_v[:80], "subject": subj_v[:100]})
                log("REPLY: %s - %s" % (from_v[:50], subj_v[:70]))

                # --- DECLINE DETECTION ---
                if is_human_reply(subj_v, from_v):
                    st2, d2 = M.fetch(num, "(BODY[])")
                    if st2 == "OK":
                        msg_bytes = b""
                        for part in d2:
                            if isinstance(part, tuple):
                                msg_bytes += part[1] if isinstance(part[1], bytes) else b""
                        body_text = extract_body_text(msg_bytes)

                        if is_decline(body_text):
                            sender_email = ""
                            m = re.search(r'<([\w.+-]+@[\w.-]+\.\w{2,4})>', from_v)
                            if m:
                                sender_email = m.group(1).lower()
                            elif '@' in from_v:
                                sender_email = from_v.split()[-1].strip('<>').lower()

                            ein, name = lookup_ein_by_email(sender_email, ENRICHED_CSV)

                            if ein:
                                reason = "Polite decline"
                                for phrase in [
                                    "does not support", "do not support", "cannot support",
                                    "unable to", "not able to", "mission does not",
                                    "unfortunately", "not a fit", "not aligned",
                                    "not funding", "does not fund", "do not fund",
                                    "not accepting", "not consider",
                                ]:
                                    if phrase in body_text.lower():
                                        idx = body_text.lower().find(phrase)
                                        reason = body_text[idx:idx+120].replace('\n', ' ').strip()
                                        break

                                if add_declined(ein, name, reason, source="inbox_monitor"):
                                    new_declines += 1
                                    log("DECLINED: %s (%s) - %s" % (name[:40], ein, reason[:60]))
                            else:
                                log("DECLINE from unknown foundation: %s" % from_v[:60])

        # Save known IDs
        with open(KNOWN_FILE, "w") as f:
            for n in all_ids:
                f.write((n.decode() if isinstance(n, bytes) else str(n)) + "\n")

        # Save new bounces
        if new_bounces:
            all_bounces = existing_bounces | new_bounces
            with open(BOUNCE_LOG, "w") as f:
                for b in sorted(all_bounces):
                    f.write(b + "\n")
            log("Bounced emails total: %d (+%d new)" % (len(all_bounces), len(new_bounces)))
            regenerate_clean_list(all_bounces)

        # Save new replies
        if new_replies:
            try:
                with open(REPLY_LOG) as f:
                    reply_history = json.load(f)
            except:
                reply_history = []
            reply_history.append({
                "timestamp": datetime.now().isoformat(),
                "new": len(new_replies),
                "replies": new_replies,
            })
            with open(REPLY_LOG, "w") as f:
                json.dump(reply_history, f, indent=2)
            for r in new_replies:
                log("  %s: %s" % (r["from"][:50], r["subject"][:60]))

        M.logout()

        if new_declines > 0:
            log("Auto-declined %d foundation(s) - they won't be contacted again" % new_declines)

        return len(new_bounces), len(new_replies), new_declines

    except Exception as e:
        log("ERROR: %s" % str(e)[:100])
        return -1, -1, 0


def regenerate_clean_list(bounced_set):
    """Remove bounced emails from enriched_contacts.csv and save clean version."""
    if not os.path.exists(ENRICHED_CSV):
        log("enriched_contacts.csv not found, skipping clean list")
        return

    try:
        with open(ENRICHED_CSV, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        original = len(rows)
        clean = []
        removed = 0
        for r in rows:
            email = r.get("EMAIL", "").strip().lower()
            if email in bounced_set:
                removed += 1
            else:
                clean.append(r)

        with open(CLEAN_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
            w.writeheader()
            w.writerows(clean)

        log("Clean list: %d contacts (%d removed, %d kept)" % (original, removed, len(clean)))
    except Exception as e:
        log("Clean list error: %s" % str(e)[:80])


def check_ses_status():
    """Check if SES is active by attempting to send a test email."""
    try:
        import smtplib, ssl
        context = ssl.create_default_context()
        server = smtplib.SMTP("email-smtp.us-east-1.amazonaws.com", 587, timeout=10)
        server.starttls(context=context)
        server.login("AKIASKQS5JXODSJERNES", "BCRaP22/Crmx5/SBb63vMJL3O2Tvm1oxwh+hgPPhW3xv")
        try:
            server.sendmail(
                "charles@columbiataxlawyer.com",
                "charles@columbiataxlawyer.com",
                "Subject: SES Health Check\n\nOK"
            )
            log("SES: ✅ ACTIVE - sending is working!")
            server.quit()
            return True
        except Exception as e:
            err = str(e)
            if "paused" in err.lower():
                log("SES: ⏸️ Still paused")
            else:
                log("SES: ❌ Error: %s" % err[:100])
            server.quit()
            return False
    except Exception as e:
        log("SES: ❌ Connection failed: %s" % str(e)[:80])
        return False


def scan_trash():
    """Check trash folder for foundation replies that were moved there."""
    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=20)
        M.login(IMAP_USER, IMAP_PASS)
        st, _ = M.select("INBOX.Trash")
        if st != "OK":
            M.logout()
            return 0
        
        st, ids = M.search(None, "ALL")
        if st != "OK" or not ids[0]:
            M.logout()
            return 0
        
        found = 0
        for num in ids[0].split():
            st2, d = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            if st2 != "OK":
                continue
            h = d[0][1].decode("utf-8","ignore") if isinstance(d[0][1], bytes) else ""
            hl = h.lower()
            if any(kw in hl for kw in ["foundation", "charities", "grant", "philanthropy"]):
                if "columbiataxlawyer" not in hl and "automatic reply" not in hl:
                    found += 1
        
        M.logout()
        if found:
            log("TRASH: %d foundation replies found in trash" % found)
        return found
    except Exception as e:
        log("TRASH scan error: %s" % str(e)[:60])
        return 0


def main():
    log("=" * 60)
    log("Inbox Monitor started")
    log("Check interval: %d minutes" % (CHECK_INTERVAL // 60))

    # Load current declined count
    declined = load_declined_eins()
    log("Declined foundations: %d" % len(declined))
    log("=" * 60)

    while True:
        log("Checking inbox...")
        bounces, replies, declines = check_inbox()
        
        # Check SES status every cycle
        ses_active = check_ses_status()
        
        # Scan trash for foundation replies
        trash_replies = scan_trash()

        status = "Bounces: %d" % bounces
        if bounces >= 0:
            status += " | Replies: %d" % replies
            status += " | Declined: %d" % declines
            status += " | SES: %s" % ("ACTIVE" if ses_active else "paused")

        log("Check complete: %s" % status)
        log("Sleeping %d minutes..." % (CHECK_INTERVAL // 60))

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()


def status():
    """Print current status."""
    try:
        with open(BOUNCE_LOG) as f:
            bounces = sum(1 for _ in f)
    except:
        bounces = 0

    try:
        with open(REPLY_LOG) as f:
            replies = len(json.load(f))
    except:
        replies = 0

    try:
        with open(CLEAN_CSV) as f:
            clean = sum(1 for _ in f) - 1  # minus header
    except:
        clean = 0

    print("")
    print("=" * 60)
    print("  INBOX MONITOR STATUS")
    print("=" * 60)
    print("  Bounced emails tracked: %d" % bounces)
    print("  Foundation replies logged: %d" % replies)
    print("  Clean contacts ready: %d" % clean)
    print("  Known message IDs: ", end="")
    try:
        with open(KNOWN_FILE) as f:
            print(sum(1 for _ in f))
    except:
        print("0")
    print("=" * 60)
    print("")


def run_loop():
    log("Inbox monitor started (interval: %d min)" % (CHECK_INTERVAL // 60))
    status()
    while True:
        log("Checking inbox...")
        bounces, replies = check_inbox()
        if bounces >= 0:
            log("Done: %d new bounces, %d new replies" % (bounces, replies))
        next_check = datetime.now() + timedelta(seconds=CHECK_INTERVAL)
        log("Next check at: %s" % next_check.strftime("%H:%M:%S"))
        log("")
        for _ in range(CHECK_INTERVAL // 10):
            time.sleep(10)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    args = parser.parse_args()

    if args.status:
        status()
    elif args.once:
        check_inbox()
        status()
    else:
        run_loop()

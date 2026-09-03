"""
INBOX SCAN & CLEAN — classify all messages, preserve real replies, trash the rest.
Usage: python scripts/outreach/scan_inbox.py          # Scan only
       python scripts/outreach/scan_inbox.py --clean  # Scan + trash junk
"""
import imaplib, email, os, subprocess, json, sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# ── Auth ──
pwd = os.environ.get("GMAIL_APP_PASSWORD", "")
if not pwd:
    r = subprocess.run(
        ["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"],
        capture_output=True, text=True
    )
    pwd = r.stdout.strip()
if not pwd:
    print("ERROR: GMAIL_APP_PASSWORD not set")
    sys.exit(1)

FROM_EMAIL = "charlesaprescottjr@gmail.com"
OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)

# ── Connect ──
print("Connecting to Gmail...")
mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(FROM_EMAIL, pwd)
mail.select("INBOX")

status, msgs = mail.search(None, "ALL")
all_ids = msgs[0].split()
print(f"Total inbox: {len(all_ids)} messages\n")

# ── Classify ALL messages ──
cats = defaultdict(list)
SCAN_ALL = len(all_ids)  # Do the whole inbox

for i, num in enumerate(all_ids):
    if i % 100 == 0:
        print(f"  Scanning {i}/{SCAN_ALL}...")

    try:
        # Fetch header only (fast)
        status, data = mail.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if status != "OK":
            continue

        raw = data[0][1]
        if not raw:
            continue

        header = raw.decode("utf-8", "replace")

        # Parse
        subj = ""
        from_addr = ""
        for line in header.split("\r\n"):
            low = line.lower()
            if low.startswith("subject:"):
                subj = line[8:].strip()
            elif low.startswith("from:"):
                from_addr = line[5:].strip()

        subj_lower = subj.lower()
        from_lower = from_addr.lower()

        # ── CLASSIFICATION RULES ──
        msg_id = num.decode()

        # BOUNCE: undeliverable, returned mail, postmaster
        if any(x in subj_lower for x in [
            "undeliverable", "delivery status", "returned mail",
            "mail delivery", "failed delivery", "postmaster",
            "mailer-daemon", "delivery failure", "returned post",
            "message undelivered", "could not be delivered",
            "failure notice", "warning: message"
        ]):
            cats["bounce"].append((msg_id, subj[:100], from_addr[:80]))

        # AUTO-REPLY: out of office, vacation
        elif any(x in subj_lower for x in [
            "out of office", "auto-reply", "automatic reply",
            "vacation", "ooo", "away from", "out of the office",
            "on leave", "extended absence"
        ]):
            cats["auto_reply"].append((msg_id, subj[:100], from_addr[:80]))

        # BOUNCE: from mailer-daemon/postmaster
        elif any(x in from_lower for x in [
            "mailer-daemon", "postmaster", "mail delivery system"
        ]):
            cats["bounce"].append((msg_id, subj[:100], from_addr[:80]))

        # NO-REPLY / SYSTEM
        elif any(x in from_lower for x in [
            "noreply@", "no-reply@", "no_reply@", "donotreply@",
            "notifications@", "alert@"
        ]):
            cats["system"].append((msg_id, subj[:100], from_addr[:80]))

        # NEWSLETTER / MARKETING / DIGEST
        elif any(x in subj_lower for x in [
            "newsletter", "digest", "weekly roundup", "daily briefing",
            "promotion", "save", "sale", "offer", "discount", "deal"
        ]):
            cats["newsletter"].append((msg_id, subj[:100], from_addr[:80]))

        # SPAM / PHISHING / SECURITY
        elif any(x in subj_lower for x in [
            "spf", "dkim", "dmarc", "phishing", "security alert",
            "verify your", "confirm your", "account suspended",
            "password reset", "login attempt", "sign-in"
        ]):
            cats["security"].append((msg_id, subj[:100], from_addr[:80]))

        # REPLY: Re: in subject = someone replying to us
        elif subj_lower.startswith("re:") or " re:" in subj_lower[:6]:
            cats["reply"].append((msg_id, subj[:100], from_addr[:80]))

        # GITHUB / DEV (likely legit notifications)
        elif any(x in from_lower for x in ["github", "gitlab", "bitbucket"]):
            cats["dev"].append((msg_id, subj[:100], from_addr[:80]))

        # GOOGLE / SYSTEM services
        elif any(x in from_lower for x in [
            "google", "accounts.google", "calendar", "drive",
            "analytics", "ads", "adwords"
        ]):
            cats["google"].append((msg_id, subj[:100], from_addr[:80]))

        else:
            cats["other"].append((msg_id, subj[:100], from_addr[:80]))

    except Exception as e:
        cats["error"].append((num.decode(), str(e)[:60], ""))

mail.logout()

# ── REPORT ──
print()
print("=" * 70)
print(f"  INBOX CLASSIFICATION — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 70)

SAFE_DELETE = {"bounce", "auto_reply", "newsletter", "security", "system"}
REVIEW = {"reply", "other", "dev", "google", "error"}

total_safe = 0
total_review = 0

for cat_name in sorted(cats.keys()):
    items = cats[cat_name]
    marker = "🗑️ DELETE" if cat_name in SAFE_DELETE else "👀 REVIEW"
    print(f"\n── {cat_name.upper()} ({len(items)}) {marker} ──")
    for msg_id, subj, frm in items[:10]:
        print(f"  [{msg_id}] {subj}")
        print(f"         From: {frm}")
    if len(items) > 10:
        print(f"  ... and {len(items)-10} more")

    if cat_name in SAFE_DELETE:
        total_safe += len(items)
    else:
        total_review += len(items)

# ── Save classification ──
json_path = OUT / "inbox_scan.json"
to_save = {k: [(a, b, c) for a, b, c in v] for k, v in cats.items()}
with open(json_path, "w") as f:
    json.dump(to_save, f, indent=2)

print(f"\n{'='*70}")
print(f"  SUMMARY")
print(f"  Safe to trash:  {total_safe}  (bounce + auto_reply + newsletter + security + system)")
print(f"  Needs review:   {total_review}  (reply + other + dev + google)")
print(f"  Total inbox:    {len(all_ids)}")
print(f"  Full report:    {json_path}")
print(f"{'='*70}")

# ── Optionally clean ──
if "--clean" in sys.argv:
    print("\n⚠️  PROCEEDING TO DELETE {total_safe} JUNK MESSAGES...")
    print("   (reply/other/dev/google messages are PRESERVED)")

    mail2 = imaplib.IMAP4_SSL("imap.gmail.com")
    mail2.login(FROM_EMAIL, pwd)
    mail2.select("INBOX")

    deleted = 0
    for cat_name in SAFE_DELETE:
        for msg_id, subj, frm in cats[cat_name]:
            try:
                # Move to Trash (not permanent delete)
                mail2.store(msg_id.encode(), "+X-GM-LABELS", "\\Trash")
                deleted += 1
                if deleted % 50 == 0:
                    print(f"  Moved {deleted} to trash...")
            except Exception as e:
                print(f"  ⚠️ Failed on {msg_id}: {e}")

    mail2.expunge()
    mail2.logout()
    print(f"\n✅ Moved {deleted} messages to Trash")
    print(f"   {total_review} real messages preserved in inbox")
    print(f"   To permanently delete: empty Trash in Gmail")

else:
    print("\n💡 Run with --clean to automatically trash the {total_safe} junk messages")
    print("   python scripts/outreach/scan_inbox.py --clean")

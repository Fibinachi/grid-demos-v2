"""
TARGETED INBOX CLEAN — with MIME-aware subject decoding.
Trashes read receipts, OOO, and junk. Preserves real replies.
"""
import imaplib, email, os, subprocess, json, sys
from email.header import decode_header, make_header
from datetime import datetime
from pathlib import Path

pwd = os.environ.get("GMAIL_APP_PASSWORD", "")
if not pwd:
    r = subprocess.run(
        ["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"],
        capture_output=True, text=True
    )
    pwd = r.stdout.strip()

FROM_EMAIL = "charlesaprescottjr@gmail.com"
mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(FROM_EMAIL, pwd)
mail.select("INBOX")

def decode_subj(raw_subj):
    if not raw_subj:
        return ""
    try:
        parts = decode_header(raw_subj)
        return str(make_header(parts))
    except:
        return raw_subj

status, msgs = mail.search(None, "ALL")
all_ids = msgs[0].split()
print(f"Total inbox: {len(all_ids)}\n")

KEEP = []
TRASH = []
EMAIL_UPDATES = []

for i, num in enumerate(all_ids):
    mid = num.decode()
    status, data = mail.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
    if status != "OK":
        continue
    raw = data[0][1]
    if not raw:
        continue
    header = raw.decode("utf-8", "replace")

    raw_subj = ""
    from_addr = ""
    for line in header.split("\r\n"):
        low = line.lower()
        if low.startswith("subject:"):
            raw_subj = line[8:].strip()
        elif low.startswith("from:"):
            from_addr = line[5:].strip()

    subj = decode_subj(raw_subj)
    subj_lower = subj.lower()
    from_lower = from_addr.lower()

    # BOUNCE
    if any(x in subj_lower for x in [
        "undeliverable", "delivery status", "returned mail",
        "mail delivery", "failed delivery", "postmaster",
        "mailer-daemon", "delivery failure", "message undelivered",
        "could not be delivered", "failure notice"
    ]) or any(x in from_lower for x in ["mailer-daemon", "postmaster"]):
        TRASH.append((mid, subj[:100], from_addr[:60], "bounce"))

    # OOO / AUTO-REPLY
    elif any(x in subj_lower for x in [
        "out of office", "auto-reply", "automatic reply",
        "vacation", "ooo", "away from", "out of the office",
        "on leave", "extended absence"
    ]):
        TRASH.append((mid, subj[:100], from_addr[:60], "auto_reply"))

    # READ RECEIPTS
    elif subj_lower.startswith("not read:") or subj_lower.startswith("read:"):
        TRASH.append((mid, subj[:100], from_addr[:60], "read_receipt"))

    # EMAIL UPDATE
    elif any(x in subj_lower for x in [
        "inactive email", "new email address", "email is no longer",
        "no longer active", "please update"
    ]):
        EMAIL_UPDATES.append((mid, subj[:100], from_addr[:60]))

    # REAL REPLY
    elif subj_lower.startswith("re:") or " re:" in subj_lower[:6]:
        KEEP.append((mid, subj[:100], from_addr[:60]))

    # NEWSLETTER
    elif any(x in subj_lower for x in [
        "newsletter", "digest", "weekly", "promotion",
        "save ", "sale", "offer", "discount", "deal"
    ]):
        TRASH.append((mid, subj[:100], from_addr[:60], "newsletter"))

    # SECURITY
    elif any(x in subj_lower for x in [
        "verify your", "confirm your", "security alert",
        "login attempt", "sign-in", "password"
    ]):
        TRASH.append((mid, subj[:100], from_addr[:60], "security"))

    # GOOGLE SYSTEM
    elif any(x in from_lower for x in [
        "accounts.google.com", "google.com", "googlecalendar",
        "google drive", "google analytics"
    ]):
        TRASH.append((mid, subj[:100], from_addr[:60], "google_system"))

    # GITHUB
    elif any(x in from_lower for x in ["github.com", "notifications@github"]):
        TRASH.append((mid, subj[:100], from_addr[:60], "github"))

    else:
        KEEP.append((mid, subj[:100], from_addr[:60]))

mail.logout()

# ── REPORT ──
print("=" * 70)
print("  INBOX CLEAN —", datetime.now().strftime("%Y-%m-%d %H:%M"))
print("=" * 70)

print(f"\n  ✅ KEEP ({len(KEEP)}) — REAL RESPONSES:")
for mid, subj, frm in KEEP:
    print(f"    [{mid}] {subj}")
    print(f"         {frm}")

if EMAIL_UPDATES:
    print(f"\n  📧 EMAIL UPDATES ({len(EMAIL_UPDATES)}) — NEED PROCESSING:")
    for mid, subj, frm in EMAIL_UPDATES:
        print(f"    [{mid}] {subj}")
        print(f"         {frm}")

print(f"\n  🗑️  TRASH ({len(TRASH)}) — will be removed:")
for mid, subj, frm, reason in TRASH:
    print(f"    [{mid}] ({reason}) {subj}")
    print(f"         {frm}")

print(f"\n{'='*70}")
print(f"  Total: {len(KEEP)} keep + {len(EMAIL_UPDATES)} updates + {len(TRASH)} trash = {len(all_ids)}")

# ── Save ──
out_path = Path("outputs/outreach/inbox_scan.json")
with open(out_path, "w") as f:
    json.dump({
        "keep": [(a, b, c) for a, b, c in KEEP],
        "email_updates": [(a, b, c) for a, b, c in EMAIL_UPDATES],
        "trash": [(a, b, c, d) for a, b, c, d in TRASH]
    }, f, indent=2)

# ── Clean ──
if "--clean" in sys.argv:
    if not TRASH:
        print("\nNothing to trash!")
        sys.exit(0)

    print(f"\n⚠️  Moving {len(TRASH)} messages to Trash...")

    mail2 = imaplib.IMAP4_SSL("imap.gmail.com")
    mail2.login(FROM_EMAIL, pwd)
    mail2.select("INBOX")

    moved = 0
    for mid, subj, frm, reason in TRASH:
        try:
            mail2.store(mid.encode(), "+X-GM-LABELS", "\\Trash")
            moved += 1
        except Exception as e:
            print(f"  ⚠️ Failed [{mid}]: {e}")

    mail2.expunge()
    mail2.logout()

    print(f"  ✅ Moved {moved} to Trash")
    print(f"  📬 {len(KEEP)} real replies + {len(EMAIL_UPDATES)} email updates preserved in Inbox")

elif "--clean-hard" in sys.argv:
    all_trash = TRASH + [(a, b, c, "email_update") for a, b, c in EMAIL_UPDATES]
    print(f"\n⚠️  HARD CLEAN: Moving {len(all_trash)} messages to Trash...")

    mail2 = imaplib.IMAP4_SSL("imap.gmail.com")
    mail2.login(FROM_EMAIL, pwd)
    mail2.select("INBOX")

    moved = 0
    for item in all_trash:
        mid = item[0]
        try:
            mail2.store(mid.encode(), "+X-GM-LABELS", "\\Trash")
            moved += 1
        except Exception as e:
            print(f"  ⚠️ Failed [{mid}]: {e}")

    mail2.expunge()
    mail2.logout()

    print(f"  ✅ Moved {moved} to Trash")
    print(f"  📬 {len(KEEP)} real replies preserved in Inbox")

else:
    print(f"\n💡 Run with --clean to trash the {len(TRASH)} junk messages")
    print("   python scripts/outreach/clean_inbox_2.py --clean")

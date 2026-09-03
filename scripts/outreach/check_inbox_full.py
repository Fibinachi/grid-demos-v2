import imaplib, email, os, subprocess
from email.header import decode_header

def decode_hdr(h):
    if h is None: return ""
    parts = decode_header(h)
    return " ".join(p[0].decode(p[1] or "utf-8", errors="ignore") if isinstance(p[0], bytes) else str(p[0]) for p in parts)

# Get password
import sys
r = subprocess.run(["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"], capture_output=True, text=True)
PWD = r.stdout.strip()
if not PWD:
    print("No GMAIL_APP_PASSWORD found"); sys.exit(1)

M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
M.login("charlesaprescottjr@gmail.com", PWD)
M.select("INBOX")

status, ids = M.search(None, "ALL")
all_ids = ids[0].split() if ids[0] else []
print(f"Total inbox: {len(all_ids)} messages\n")

# Show last 20
print("=== RECENT 20 MESSAGES ===\n")
for num in reversed(all_ids[-20:]):
    status2, data = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
    if status2 != "OK": continue
    h = data[0][1].decode("utf-8", errors="ignore") if isinstance(data[0][1], bytes) else str(data[0][1])
    
    from_v = subj_v = date_v = ""
    for line in h.split("\n"):
        l = line.strip()
        if l.startswith("From:"): from_v = decode_hdr(l[5:].strip())
        if l.startswith("Subject:"): subj_v = decode_hdr(l[8:].strip())
        if l.startswith("Date:"): date_v = l[5:].strip()
    
    # Flag bounces and replies
    is_self = "charlesaprescott" in from_v.lower()
    is_bounce = any(x in h.lower() for x in ["mailer-daemon", "mail delivery", "undelivered", "returned mail", "delivery status", "delivery has failed"])
    is_test = "TEST:" in subj_v
    
    prefix = ""
    if is_bounce: prefix = "❌ BOUNCE: "
    elif is_test: prefix = "🧪 TEST:   "
    elif is_self: prefix = "📤 SELF:   "
    else: prefix = "📨         "
    
    print(f"{prefix}{date_v[:25]:25s} | {from_v[:55]:55s} | {subj_v[:85]}")

# Check specifically for bounces
print("\n=== BOUNCES (last 100 msgs) ===")
bounces = 0
for num in all_ids[-100:]:
    status2, data = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
    if status2 != "OK": continue
    h = data[0][1].decode("utf-8", errors="ignore") if isinstance(data[0][1], bytes) else str(data[0][1])
    h_lower = h.lower()
    if any(x in h_lower for x in ["mailer-daemon", "mail delivery", "undelivered", "returned mail", "delivery has failed"]):
        bounces += 1
        subj = ""
        for line in h.split("\n"):
            if line.strip().startswith("Subject:"):
                subj = decode_hdr(line.strip()[8:].strip())
        print(f"  ❌ {subj[:90]}")

if bounces == 0:
    print("  None found.")

# Check for replies (not self, not bounce)
print("\n=== POTENTIAL REPLIES ===")
replies = 0
for num in all_ids[-100:]:
    status2, data = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
    if status2 != "OK": continue
    h = data[0][1].decode("utf-8", errors="ignore") if isinstance(data[0][1], bytes) else str(data[0][1])
    from_v = ""
    for line in h.split("\n"):
        if line.strip().startswith("From:"):
            from_v = decode_hdr(line.strip()[5:].strip())
    h_lower = h.lower()
    is_self = "charlesaprescott" in from_v.lower()
    is_bounce = any(x in h_lower for x in ["mailer-daemon", "mail delivery", "undelivered", "returned", "delivery has failed", "automatic reply", "out of office", "out-of-office"])
    if not is_self and not is_bounce and from_v:
        replies += 1
        subj = ""
        for line in h.split("\n"):
            if line.strip().startswith("Subject:"):
                subj = decode_hdr(line.strip()[8:].strip())
        print(f"  📨 {from_v[:60]} | {subj[:90]}")

if replies == 0:
    print("  No replies yet.")

M.logout()

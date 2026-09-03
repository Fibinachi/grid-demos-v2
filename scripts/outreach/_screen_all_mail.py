"""Screen all Gmail folders for replies worth human attention."""
import imaplib, email, subprocess, re
from email.header import decode_header

def decode_hdr(h):
    if h is None: return ""
    parts = decode_header(h)
    return " ".join(p[0].decode(p[1] or "utf-8", errors="ignore") if isinstance(p[0], bytes) else str(p[0]) for p in parts)

r = subprocess.run(
    ["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"],
    capture_output=True, text=True
)
PWD = r.stdout.strip()

M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
M.login("charlesaprescottjr@gmail.com", PWD)

folders = ["INBOX", "[Gmail]/All Mail", "[Gmail]/Sent Mail"]
replies = []

for folder in folders:
    try:
        M.select(folder, readonly=True)
        s, ids = M.search(None, "ALL")
        all_ids = ids[0].split() if ids[0] else []
    except:
        continue

    check_ids = all_ids[-200:] if len(all_ids) > 200 else all_ids

    for num in reversed(check_ids):
        try:
            s2, d2 = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if s2 != "OK": continue
            hdr = d2[0][1].decode("utf-8", errors="ignore") if isinstance(d2[0][1], bytes) else str(d2[0][1])
        except:
            continue

        from_v = subj_v = date_v = ""
        for line in hdr.split("\n"):
            ll = line.strip()
            if ll.lower().startswith("from:"): from_v = decode_hdr(ll[5:].strip())
            if ll.lower().startswith("subject:"): subj_v = decode_hdr(ll[8:].strip())
            if ll.lower().startswith("date:"): date_v = ll[5:].strip()

        h_lower = hdr.lower()
        from_lower = from_v.lower()

        # Skip bounces, self, noreply, google
        if any(x in h_lower for x in ["mailer-daemon", "postmaster@", "mail delivery",
            "undelivered", "returned mail", "delivery has failed", "delivery status"]):
            continue
        if "charlesaprescott" in from_lower or "charlesaprescottjr" in from_lower:
            continue
        if any(x in from_lower for x in ["noreply", "no-reply", "donotreply",
            "accounts.google", "google-noreply"]):
            continue

        is_reply = "re:" in subj_v.lower()

        replies.append({
            "folder": folder, "from": from_v, "subject": subj_v,
            "date": date_v, "is_reply": is_reply, "hdr": h_lower
        })

M.logout()

# Deduplicate by from + subject
seen = set()
unique = []
for r in replies:
    key = (r["from"].lower(), r["subject"].lower())
    if key not in seen:
        seen.add(key)
        unique.append(r)

important = [r for r in unique if r["is_reply"]]
other = [r for r in unique if not r["is_reply"]]

print("=" * 80)
print("POTENTIALLY WORTH HUMAN EYES")
print("=" * 80)

if important:
    print(f"\n--- REPLIES ({len(important)}) ---")
    for r in important:
        date = r["date"][:25] if r["date"] else "?"
        fr = r["from"][:50] if r["from"] else "?"
        subj = r["subject"][:70] if r["subject"] else "?"
        print(f"  [{date}] {fr}")
        print(f"      {subj}")

if other:
    print(f"\n--- OTHER HUMAN MAIL ({len(other)}) ---")
    for r in other:
        date = r["date"][:25] if r["date"] else "?"
        fr = r["from"][:50] if r["from"] else "?"
        subj = r["subject"][:70] if r["subject"] else "?"
        print(f"  [{date}] {fr}")
        print(f"      {subj}")

if not important and not other:
    print("\nNothing needs human attention.")
else:
    print(f"\nTotal unique senders screened: {len(unique)}")
    print(f"Replies worth checking: {len(important)}")
    if important:
        print("\nWant me to fetch the body of any specific reply?")

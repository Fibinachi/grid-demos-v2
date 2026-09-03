"""Archive all bounce/undeliverable messages from Gmail inbox."""
import imaplib, subprocess, sys, time

r = subprocess.run(["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"],
                   capture_output=True, text=True)
PWD = r.stdout.strip()
if not PWD:
    print("No GMAIL_APP_PASSWORD found")
    sys.exit(1)

M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
M.login("charlesaprescottjr@gmail.com", PWD)
M.select("INBOX")

status, ids = M.search(None, "ALL")
all_ids = ids[0].split() if ids[0] else []
print(f"Total inbox: {len(all_ids)} messages")

BOUNCE_PATTERNS = [
    "mailer-daemon", "mail delivery", "undelivered", "returned mail",
    "delivery status", "delivery has failed", "postmaster@",
    "mail delivery subsystem",
]

to_delete = []
keep = []
for num in all_ids:
    s, d = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
    if s != "OK":
        continue
    h = d[0][1].decode("utf-8", errors="ignore") if isinstance(d[0][1], bytes) else str(d[0][1])
    h_lower = h.lower()
    if any(x in h_lower for x in BOUNCE_PATTERNS):
        to_delete.append(num)
    else:
        keep.append(num)

print(f"Bounces to archive: {len(to_delete)}")
print(f"Messages to keep: {len(keep)}")

if keep:
    print("\nKeeping:")
    for num in keep:
        s2, d2 = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if s2 == "OK":
            h2 = d2[0][1].decode("utf-8", errors="ignore") if isinstance(d2[0][1], bytes) else str(d2[0][1])
            print(f"  {h2[:150]}")

if to_delete:
    print(f"\nArchiving {len(to_delete)} bounces to trash...")
    for i, num in enumerate(to_delete):
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(to_delete)}...")
        try:
            M.store(num, "+X-GM-LABELS", "\\Trash")
            M.store(num, "+FLAGS", "\\Deleted")
        except Exception as e:
            print(f"  Failed on msg {num}: {e}")
    M.expunge()
    print(f"Archived {len(to_delete)} messages")

M.select("INBOX")
s, ids = M.search(None, "ALL")
remaining = ids[0].split() if ids[0] else []
print(f"\nInbox now: {len(remaining)} messages")
M.close()
M.logout()
print("Done!")

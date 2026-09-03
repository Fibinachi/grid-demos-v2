"""Empty Gmail Trash."""
import imaplib, subprocess, sys

r = subprocess.run(
    ["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"],
    capture_output=True, text=True
)
PWD = r.stdout.strip()
if not PWD:
    print("No GMAIL_APP_PASSWORD"); sys.exit(1)

M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
M.login("charlesaprescottjr@gmail.com", PWD)

# Check inbox first
M.select("INBOX")
s, ids = M.search(None, "ALL")
inbox = len(ids[0].split()) if ids[0] else 0

# Empty trash
M.select("[Gmail]/Trash")
s, ids = M.search(None, "ALL")
trash_ids = ids[0].split() if ids[0] else []
print(f"Inbox: {inbox} | Trash: {len(trash_ids)}")

if trash_ids:
    for i, num in enumerate(trash_ids):
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(trash_ids)}...")
        M.store(num, "+FLAGS", "\\Deleted")
    M.expunge()
    print(f"Permanently deleted {len(trash_ids)} messages")

    # Also check [Gmail]/Bin for non-English Gmail accounts
    try:
        M.select("[Gmail]/Bin")
        s2, ids2 = M.search(None, "ALL")
        bin_ids = ids2[0].split() if ids2[0] else []
        if bin_ids:
            for num in bin_ids:
                M.store(num, "+FLAGS", "\\Deleted")
            M.expunge()
            print(f"Also deleted {len(bin_ids)} from Bin folder")
    except:
        pass

M.close()
M.logout()
print("Done!")

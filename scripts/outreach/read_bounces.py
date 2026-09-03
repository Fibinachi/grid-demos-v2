import imaplib, email, subprocess, re

r = subprocess.run(["powershell","-c","[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"],capture_output=True,text=True)
PWD = r.stdout.strip()

M = imaplib.IMAP4_SSL("imap.gmail.com",993,timeout=30)
M.login("charlesaprescottjr@gmail.com",PWD)
M.select("INBOX")

status, ids = M.search(None,"FROM","mailer-daemon@googlemail.com")
all_ids = ids[0].split()[-8:]
print("=== LAST 8 BOUNCES ===\n")

for num in all_ids:
    s,d = M.fetch(num,"(RFC822)")
    msg = email.message_from_bytes(d[0][1])
    subj = msg.get("Subject","")
    body = ""
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type()=="text/plain":
                body = p.get_payload(decode=True).decode("utf-8",errors="ignore")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8",errors="ignore")
    
    # Find failed email
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+",body)
    targets = [e for e in emails if e not in ("charlesaprescottjr@gmail.com","mailer-daemon@googlemail.com")]
    
    # Find reason
    reason = ""
    for line in body.split("\n"):
        l = line.strip().lower()
        if any(x in l for x in ["not found","doesn't exist","address rejected","unrouteable","disabled","inactive","mailbox full","blocked"]):
            reason = line.strip()[:120]
            break
    
    target = targets[0] if targets else "unknown"
    print(f"❌ {target}")
    if reason: print(f"   {reason}")
    print(f"   Subject: {subj[:80]}")
    print()

M.logout()

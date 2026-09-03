"""Check Hostinger email for Census API key and recent responses"""
import imaplib, email, os, re, json
from email.header import decode_header

EMAIL = "charles@columbiataxlawyer.com"
PASSWORD = os.environ.get("EMAIL_PASSWORD", "FlorenceFlamingo1!")
IMAP_SERVER = "imap.hostinger.com"

mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
mail.login(EMAIL, PASSWORD)
mail.select("inbox")

# Get recent emails
status, messages = mail.search(None, "ALL")
if status == "OK":
    ids = messages[0].split()
    recent = ids[-20:]  # last 20
    print(f"Total emails: {len(ids)}, showing last {len(recent)}")
    
    for num in reversed(recent):
        status, msg_data = mail.fetch(num, "(RFC822)")
        if status != "OK":
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        
        subj_raw = decode_header(msg["Subject"])[0][0]
        subject = subj_raw.decode() if isinstance(subj_raw, bytes) else subj_raw
        from_addr = msg["From"]
        date = msg["Date"][:25] if msg["Date"] else "?"
        
        # Get body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="ignore")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        
        # Flag census key emails
        is_census = "census" in subject.lower() or "api key" in subject.lower() or "census" in body.lower()[:200]
        tag = " *** CENSUS ***" if is_census else ""
        
        print(f"\n[{date}] From: {from_addr}{tag}")
        print(f"  Subject: {subject[:80]}")
        if is_census:
            # Show the full body to find the key
            print(f"  BODY: {body[:1000]}")
        else:
            # Show first 200 chars
            print(f"  Preview: {body.replace(chr(10),' ')[:200]}")

mail.logout()

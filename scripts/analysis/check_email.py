import imaplib
import email
import os
import re
from email.header import decode_header

EMAIL = "charles@columbiataxlawyer.com"
PASSWORD = os.environ.get("EMAIL_PASSWORD")
IMAP_SERVER = "imap.hostinger.com"
IMAP_PORT = 993

def check_inbox():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")
    
    status, messages = mail.search(None, "UNSEEN")
    if status != "OK":
        print("No unseen messages")
        return []
    
    results = []
    for num in messages[0].split()[-5:]:  # last 5 unseen
        status, msg_data = mail.fetch(num, "(RFC822)")
        if status != "OK":
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        subject = decode_header(msg["Subject"])[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()
        from_addr = msg["From"]
        
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="ignore")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        
        # Extract verification links
        links = re.findall(r'https?://[^\s"\']+', body)
        results.append({
            "subject": subject,
            "from": from_addr,
            "links": links[:3]
        })
    
    mail.logout()
    return results

if __name__ == "__main__":
    msgs = check_inbox()
    if msgs:
        print(f"Found {len(msgs)} unread messages:")
        for m in msgs:
            print(f"\nSubject: {m['subject']}")
            print(f"From: {m['from']}")
            for link in m['links']:
                print(f"Link: {link}")
    else:
        print("No unread messages found")

"""Clean Hostinger inbox via IMAP - move spam/declines to folder, keep leads."""
import imaplib
import email
import json
import os
import re
from email.header import decode_header

IMAP_HOST = "imap.hostinger.com"
IMAP_USER = "charles@columbiataxlawyer.com"
IMAP_PASS = os.environ.get("EMAIL_PASSWORD", "FlorenceFlamingo1!")

DECLINE_KEYWORDS = [
    "remote attorney", "remote paralegal", "legal assistant", "skilled legal",
    "hire a dedicated", "recruitment", "recruiter", "staffing",
    "helium", "crypto", "bitcoin", "investment opportunity",
    "verification", "verify your", "welcome to", "onboarding",
    "phone validation", "api now supports", "global numbers",
    "undeliverable", "delivery status", "mail delivery",
    "automatic reply", "out of office", "ooo:", "away from office",
    "unsubscribe", "newsletter", "you're receiving this",
    "linkedin", "connection request", "invitation to connect",
    "meeting scheduled", "calendar invitation", "zoom meeting",
    "your application", "application status", "job offer",
    "congratulations", "you have been selected",
]

def decode_str(s):
    """Decode email header string."""
    if not s:
        return ""
    try:
        decoded_parts = decode_header(s)
        return "".join(
            part.decode(charset or "utf-8", errors="replace") if isinstance(part, bytes) else str(part)
            for part, charset in decoded_parts
        )
    except:
        return str(s)

def get_body(msg):
    """Extract plain text body from email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
                except:
                    return str(part.get_payload(decode=True))
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except:
            return str(msg.get_payload(decode=True))
    return ""

def is_spam_or_decline(subject, sender, body):
    """Check if message is spam/decline/unimportant."""
    text = (subject + " " + sender + " " + body[:500]).lower()
    matches = sum(1 for kw in DECLINE_KEYWORDS if kw in text)
    return matches >= 1

print("Connecting to Hostinger IMAP...")
mail = imaplib.IMAP4_SSL(IMAP_HOST)
mail.login(IMAP_USER, IMAP_PASS)
mail.select("INBOX")

# Search all messages
status, data = mail.search(None, "ALL")
if status != "OK":
    print("No messages found")
    exit()

msg_ids = data[0].split()
print(f"Total inbox messages: {len(msg_ids)}")

# Create folder for declines if it doesn't exist
try:
    mail.create("Declines")
    print("Created 'Declines' folder")
except:
    print("'Declines' folder already exists")

spam_count = 0
keep_count = 0
spam_ids = []
keep_msgs = []

for num in msg_ids[-100:]:  # Process most recent 100 to avoid timeout
    status, data = mail.fetch(num, "(FLAGS BODY.PEEK[HEADER.FIELDS (From Subject Date)])")
    if status != "OK":
        continue
    
    # Parse headers
    msg = email.message_from_bytes(data[0][1])
    subject = decode_str(msg.get("Subject", ""))
    sender = decode_str(msg.get("From", ""))
    date = msg.get("Date", "")
    
    if is_spam_or_decline(subject, sender, ""):
        spam_count += 1
        spam_ids.append(num)
    else:
        keep_count += 1
        keep_msgs.append((sender, subject, date))

print(f"\nSpam/decline to move: {spam_count}")
print(f"Keeping in inbox: {keep_count}")

# Move spam to Declines folder
if spam_ids:
    for num in spam_ids:
        mail.copy(num, "Declines")
        mail.store(num, "+FLAGS", "\\Deleted")
    mail.expunge()
    print(f"\n✅ Moved {len(spam_ids)} messages to 'Declines' folder")

# Show what's left
print(f"\n=== REMAINING IN INBOX ({keep_count}) ===")
for sender, subject, date in sorted(keep_msgs, key=lambda x: x[2] or "", reverse=True)[:20]:
    print(f"  {sender[:40]:40s} | {subject[:55]:55s} | {str(date)[:10]}")

if keep_count > 20:
    print(f"  ... and {keep_count - 20} more")

mail.logout()
print("\n✅ Done!")

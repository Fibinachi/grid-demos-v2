#!/usr/bin/env python3
"""
Clean Hostinger Inbox & Trash
=============================
Scan charles@columbiataxlawyer.com via IMAP for:
1. Bounce/failure notifications
2. Decline replies
3. Move them to trash / delete
4. Update bounce list
"""
import imaplib
import email
import os
import re
import time
from email.header import decode_header
from datetime import datetime

IMAP_HOST = "imap.hostinger.com"
IMAP_USER = "charles@columbiataxlawyer.com"
IMAP_PASS = os.environ.get("EMAIL_PASSWORD", "FlorenceFlamingo1!")

DECLINED_FILE = "declined_foundations.txt"
BOUNCED_FILE = "bounced_emails.txt"

DECLINE_PHRASES = [
    "does not support", "do not support", "cannot support",
    "unable to support", "not able to", "regret to inform",
    "unfortunately", "not a fit", "not a good fit",
    "not currently funding", "no longer funding",
    "does not align", "not aligned", "not within our",
    "outside our scope", "outside our mission",
    "not currently accepting", "limited resources",
    "decline", "declined", "not interested",
    "do not fund individuals", "only fund organizations",
]

def decode_str(s):
    """Decode email header string."""
    if not s: return ''
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            except:
                result.append(part.decode('utf-8', errors='replace'))
        else:
            result.append(str(part))
    return ''.join(result)

def get_body(msg):
    """Extract plain text body."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                try:
                    return part.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    return str(part.get_payload(decode=True))
    else:
        try:
            return msg.get_payload(decode=True).decode('utf-8', errors='replace')
        except:
            return str(msg.get_payload(decode=True))
    return ''

def is_bounce(subject, sender, body):
    """Check if email is a bounce."""
    s = f"{subject} {sender}".lower()
    if 'mailer-daemon' in s or 'mail delivery failed' in s:
        return True
    if 'undelivered' in s or 'returned mail' in s:
        return True
    if 'bounce' in s or 'failure notice' in s:
        return True
    if 'delivery status' in s or '550' in body:
        return True
    return False

def extract_bounced_email(body):
    """Extract bounced address from bounce message."""
    if not body: return ''
    emails = re.findall(r'[\w.+-]+@[\w-]+\.\w+', body)
    for e in emails:
        el = e.lower()
        if 'mailer-daemon' not in el and 'amazonses' not in el and 'google' not in el:
            return e
    return emails[0] if emails else ''

def is_decline(body):
    """Check if email body contains decline language."""
    if not body: return False, ''
    bl = body.lower()
    for phrase in DECLINE_PHRASES:
        if phrase in bl:
            return True, phrase
    return False, ''

def main():
    print("=" * 60)
    print(f"  HOSTINGER INBOX CLEANUP")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Load existing bounced
    bounced = set()
    if os.path.exists(BOUNCED_FILE):
        with open(BOUNCED_FILE) as f:
            bounced = {l.strip().lower() for l in f if l.strip() and '@' in l}
    
    declined_eins = set()
    if os.path.exists(DECLINED_FILE):
        with open(DECLINED_FILE) as f:
            declined_eins = {l.split('|')[0].strip() for l in f if l.strip()}
    
    print(f"Existing bounced: {len(bounced)}, declined: {len(declined_eins)}")
    
    # Connect
    print(f"\nConnecting to {IMAP_HOST}...")
    M = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=30)
    M.login(IMAP_USER, IMAP_PASS)
    print("Connected!")
    
    new_bounces = []
    new_declines = []
    total_deleted = 0
    
    for folder in ['INBOX', 'INBOX.Trash']:
        print(f"\n--- {folder} ---")
        try:
            status, count = M.select(folder, readonly=False)
            if status != 'OK':
                print(f"  Cannot select: {count}")
                continue
            print(f"  Messages: {count[0].decode()}")
            
            status, msg_ids = M.search(None, 'ALL')
            if status != 'OK':
                print(f"  No messages")
                continue
            
            ids = msg_ids[0].split()
            print(f"  Found {len(ids)} messages")
            
            for i, mid in enumerate(ids):
                try:
                    status, data = M.fetch(mid, '(RFC822)')
                    if status != 'OK': continue
                    
                    raw = data[0][1]
                    msg = email.message_from_bytes(raw)
                    
                    subject = decode_str(msg.get('Subject', ''))
                    sender = decode_str(msg.get('From', ''))
                    body = get_body(msg)
                    
                    # Check bounce
                    if is_bounce(subject, sender, body):
                        bounced_addr = extract_bounced_email(body)
                        if bounced_addr and bounced_addr.lower() not in bounced:
                            bounced.add(bounced_addr.lower())
                            new_bounces.append(bounced_addr)
                            print(f"  [{i+1}/{len(ids)}] BOUNCE: {bounced_addr}")
                        
                        # Delete
                        M.store(mid, '+FLAGS', '\\Deleted')
                        total_deleted += 1
                        continue
                    
                    # Check decline
                    is_dec, phrase = is_decline(body)
                    if is_dec:
                        print(f"  [{i+1}/{len(ids)}] DECLINE: {subject[:50]} (phrase: {phrase[:40]})")
                        new_declines.append((subject[:50], phrase, sender))
                        M.store(mid, '+FLAGS', '\\Deleted')
                        total_deleted += 1
                        continue
                    
                    # Print other for review
                    print(f"  [{i+1}/{len(ids)}] OTHER: {subject[:50]:50s} from {sender[:30]}")
                    
                except Exception as e:
                    print(f"  Error on msg {i}: {e}")
            
            # Expunge deleted
            M.expunge()
            
        except Exception as e:
            print(f"  Folder error: {e}")
    
    M.logout()
    
    # Save new bounces
    if new_bounces:
        with open(BOUNCED_FILE, 'a') as f:
            for addr in new_bounces:
                f.write(f"{addr}\n")
        print(f"\n✅ {len(new_bounces)} new bounces saved")
    
    print(f"\n{'='*60}")
    print(f"CLEANUP COMPLETE")
    print(f"{'='*60}")
    print(f"Deleted: {total_deleted} messages")
    print(f"New bounces: {len(new_bounces)}")
    print(f"New declines: {len(new_declines)}")
    print(f"Total bounced: {len(bounced)}")

if __name__ == '__main__':
    main()

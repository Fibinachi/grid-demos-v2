"""
Foundation Reply Tracker
========================
Checks the inbox for replies to sent foundation emails.
Filters out everything except real responses from foundations.

Usage:
  python track_replies.py          # One-time check
  python track_replies.py --watch  # Keep watching (checks every 60s)
"""

import imaplib
import email
import os
import re
import json
import time
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SENT_LOG = os.path.join(SCRIPT_DIR, "ses_logs", "ses_sent.txt")
REPLY_LOG = os.path.join(SCRIPT_DIR, "foundation_replies.json")
IMAP_USER = "charles@columbiataxlawyer.com"
IMAP_HOST = "imap.hostinger.com"
IMAP_PASS = os.environ.get("EMAIL_PASSWORD", "FlorenceFlamingo1!")

# Emails/senders to ignore
IGNORE_DOMAINS = [
    'google.com', 'googlemail.com', 'accounts.google.com',
    'amazonaws.com', 'amazon.com', 'paypal.com', 'stripe.com',
    'hostinger.com', 'user.hostinger.com', 'info.hostinger.com',
    'linkedin.com', 'facebook.com', 'twitter.com', 'x.com',
    'zoom.us', 'discord.com', 'github.com', 'paypal.com',
    'noreply@', 'no-reply@', 'donotreply@', 'do_not_reply@',
    'alerts@', 'newsletter@', 'notifications@',
    'td.com', 'hulanetworks.com',
]


def is_foundation_reply(frm, subj, body):
    """Check if an email looks like a real reply from a foundation."""
    frm_lower = frm.lower()
    subj_lower = subj.lower()
    
    # Skip automated/ignore domains
    for domain in IGNORE_DOMAINS:
        if domain in frm_lower:
            return False
    
    # Must have a real person's name in From
    has_name = '<' in frm and '>' in frm
    if not has_name and 'prescott' not in frm_lower:
        return False
    
    # Check for reply indicators
    is_reply = subj_lower.startswith('re:') or subj_lower.startswith('re-')
    
    # Check for foundation-related keywords in body
    foundation_kw = ['grant', 'foundation', 'funding', 'scholarship', 'theological',
                     'theology', 'trinity college', 'application', 'eligibility',
                     'program', 'support', 'inquiry', 'interested']
    has_kw = any(k in body.lower() for k in foundation_kw)
    
    return is_reply or has_kw


def check_replies():
    """Scan inbox for foundation replies."""
    replies = []
    
    # Load existing reply log
    prev_replies = {}
    if os.path.exists(REPLY_LOG):
        with open(REPLY_LOG, 'r') as f:
            try:
                prev_replies = {r['msg_id']: r for r in json.load(f)}
            except:
                pass
    
    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=15)
        M.login(IMAP_USER, IMAP_PASS)
        M.select('INBOX')
        
        st, ids = M.search(None, 'ALL')
        all_ids = ids[0].split() if ids[0] else []
        
        for num in all_ids:
            st2, data = M.fetch(num, '(RFC822)')
            if st2 != 'OK': continue
            msg = email.message_from_bytes(data[0][1])
            
            msg_id = msg.get('Message-ID', str(num))
            if msg_id in prev_replies:
                continue  # Already logged
            
            frm = msg.get('From', '')
            subj = msg.get('Subject', '')
            
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True)
                        if body:
                            body = body.decode('utf-8', errors='ignore')
                        break
            else:
                body = msg.get_payload(decode=True)
                if body:
                    body = body.decode('utf-8', errors='ignore')
            
            if is_foundation_reply(frm, subj, body):
                # Extract sender email
                match = re.search(r'[\w.+-]+@[\w.-]+\.\w{2,4}', frm)
                sender_email = match.group(1).lower() if match else ''
                
                entry = {
                    'msg_id': msg_id,
                    'from': frm,
                    'email': sender_email,
                    'subject': subj,
                    'snippet': body[:200] if body else '',
                    'date': msg.get('Date', ''),
                    'detected_at': datetime.now().isoformat(),
                }
                replies.append(entry)
        
        M.logout()
    except Exception as e:
        print(f"  IMAP error: {str(e)[:80]}")
    
    # Merge with previous replies
    all_replies = list(prev_replies.values()) + replies
    
    # Save
    with open(REPLY_LOG, 'w') as f:
        json.dump(all_replies, f, indent=2)
    
    return replies


def main():
    watch = '--watch' in sys.argv
    
    if watch:
        print(f"📡 Watching for foundation replies (checking every 60s)...")
        print(f"   Log: {REPLY_LOG}")
        print()
        try:
            while True:
                new = check_replies()
                now = datetime.now().strftime('%H:%M:%S')
                if new:
                    print(f"[{now}] 🎯 {len(new)} NEW FOUNDATION REPLY/REPLIES!")
                    for r in new:
                        print(f"  From: {r['from'][:60]}")
                        print(f"  Subj: {r['subject'][:80]}")
                        print(f"  ---")
                else:
                    with open(REPLY_LOG) as f:
                        total = len(json.load(f))
                    print(f"[{now}] Checked — {total} total replies logged")
                sys.stdout.flush()
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        new = check_replies()
        with open(REPLY_LOG) as f:
            total = len(json.load(f))
        print(f"\nFoundation replies logged: {total}")
        if new:
            print(f"New this check: {len(new)}")
            for r in new:
                print(f"  📩 {r['from'][:50]} | {r['subject'][:70]}")
        else:
            print("No new replies found.")
        print(f"Log: {REPLY_LOG}")


if __name__ == '__main__':
    main()

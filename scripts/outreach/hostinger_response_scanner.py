"""
Hostinger Response Scanner
==========================
Connect to charles@columbiataxlawyer.com via IMAP,
scan inbox for replies to sent foundation emails,
classify as YES/MAYBE/NO, move to folders.

Usage: python hostinger_response_scanner.py
"""
import imaplib
import email
import os
import re
import json
import time
from email.header import decode_header
from datetime import datetime

IMAP_HOST = "imap.hostinger.com"
IMAP_USER = "charles@columbiataxlawyer.com"
IMAP_PASS = os.environ.get("EMAIL_PASSWORD", "FlorenceFlamingo1!")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Classification keywords
YES_KEYWORDS = ['interested', 'would like to', 'happy to', 'pleased to', 'yes',
    'definitely', 'sounds good', 'love to', 'looking forward', 'let\'s discuss',
    'happy to help', 'support your', 'funding', 'grant', 'scholarship',
    'contribute', 'donation', 'sponsor', 'consider', 'apply', 'application',
    'proposal', 'tell me more', 'more information', 'send me',
    'meeting', 'call', 'zoom', 'discuss further']

MAYBE_KEYWORDS = ['not sure', 'maybe', 'possibly', 'might be', 'could be',
    'will think', 'let me think', 'need to discuss', 'check with',
    'talk to my', 'board', 'committee', 'review', 'forwarded', 'passing along',
    'not the right person', 'directed to', 'cc\'ing', 'copying',
    'out of office', 'vacation', 'away', 'busy', 'swamped', 'will get back']

NO_KEYWORDS = ['not interested', 'unfortunately', 'cannot support', 'not able to',
    'do not fund', 'don\'t fund', 'not funding', 'no longer',
    'does not align', 'not aligned', 'not a fit', 'decline', 'declined',
    'regret', 'unable to', 'not within', 'outside our', 'limited resources',
    'not accepting', 'not currently', 'do not accept', 'only fund organizations',
    'only support organizations', 'not in a position', 'not the right fit',
    'remove from', 'unsubscribe', 'stop emailing']

def decode_str(s):
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

def classify_response(subject, sender, body):
    text = f"{subject} {sender} {body}".lower()
    
    # Bounce check
    if any(x in text for x in ['mailer-daemon', 'delivery failure', 'undelivered',
                                'delivery status', '550 ', 'mail delivery failed',
                                'returned mail', 'bounce']):
        return 'BOUNCE', 'Bounced'
    
    no_score = sum(1 for kw in NO_KEYWORDS if kw.lower() in text)
    yes_score = sum(1 for kw in YES_KEYWORDS if kw.lower() in text)
    maybe_score = sum(1 for kw in MAYBE_KEYWORDS if kw.lower() in text)
    
    if no_score >= 2 or (no_score >= 1 and yes_score == 0):
        return 'NO', f'Declined (score: no={no_score})'
    elif yes_score >= 2 and no_score == 0:
        return 'YES', f'Interested (score: yes={yes_score})'
    elif maybe_score >= 1:
        return 'MAYBE', f'Maybe (score: maybe={maybe_score})'
    elif 'auto-reply' in text or 'automatic reply' in text or 'auto reply' in text:
        return 'AUTO', 'Auto-reply'
    else:
        return 'UNREAD', 'Needs review'

def main():
    print("=" * 60)
    print("  HOSTINGER RESPONSE SCANNER")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Connect
    print(f"\n📡 Connecting to {IMAP_HOST}...")
    M = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=30)
    M.login(IMAP_USER, IMAP_PASS)
    print("✅ Connected!")
    
    all_responses = []
    
    for folder in ['INBOX', 'INBOX.Trash']:
        print(f"\n📁 --- {folder} ---")
        try:
            status, count = M.select(folder, readonly=False)
            if status != 'OK':
                print(f"  Cannot select: {count}")
                continue
            print(f"  Messages: {count[0].decode()}")
            
            status, msg_ids = M.search(None, 'ALL')
            if status != 'OK':
                continue
            
            ids = msg_ids[0].split()
            print(f"  Scanning {len(ids)} messages...")
            
            for mid in ids:
                try:
                    status, data = M.fetch(mid, '(RFC822)')
                    if status != 'OK': continue
                    
                    raw = data[0][1]
                    msg = email.message_from_bytes(raw)
                    
                    subject = decode_str(msg.get('Subject', ''))
                    sender = decode_str(msg.get('From', ''))
                    date = decode_str(msg.get('Date', ''))
                    body = get_body(msg)[:1000]
                    
                    # Skip messages FROM us (we sent them)
                    sender_lower = sender.lower()
                    if 'charles' in sender_lower or 'columbiataxlawyer' in sender_lower:
                        continue
                    
                    # Skip completely automated/noreply
                    if any(x in sender_lower for x in ['noreply', 'no-reply', 'mailer-daemon@',
                                                         'bounce@', 'donotreply']):
                        # Still check for bounce
                        if 'mailer-daemon' in sender_lower or 'mail delivery' in subject.lower():
                            cls, reason = 'BOUNCE', 'Bounce notification'
                            all_responses.append({
                                'folder': folder,
                                'msg_id': mid.decode(),
                                'sender': sender[:60],
                                'subject': subject[:80],
                                'date': date,
                                'classification': cls,
                                'reason': reason,
                                'body_preview': body[:200],
                            })
                            print(f"  📬 BOUNCE: {sender[:40]:40s} {subject[:40]}")
                            # Delete bounces
                            M.store(mid, '+FLAGS', '\\Deleted')
                        continue
                    
                    # This looks like a real reply - classify it
                    cls, reason = classify_response(subject, sender, body)
                    
                    all_responses.append({
                        'folder': folder,
                        'msg_id': mid.decode(),
                        'sender': sender[:60],
                        'subject': subject[:80],
                        'date': date,
                        'classification': cls,
                        'reason': reason,
                        'body_preview': body[:200],
                    })
                    
                    emoji = {'YES': '✅', 'MAYBE': '🤔', 'NO': '❌', 'BOUNCE': '📬', 'AUTO': '🤖', 'UNREAD': '📋'}.get(cls, '📧')
                    print(f"  {emoji} {cls:6s} | {sender[:40]:40s} | {subject[:50]}")
                    
                except Exception as e:
                    print(f"  ⚠️ Error on msg: {e}")
            
            M.expunge()
            
        except Exception as e:
            print(f"  ❌ Folder error: {e}")
    
    M.logout()
    
    # Summary
    if all_responses:
        import csv
        
        # Save JSON
        with open(os.path.join(SCRIPT_DIR, 'hostinger_responses.json'), 'w', encoding='utf-8') as f:
            json.dump(all_responses, f, indent=2, default=str)
        
        # Save CSV
        with open(os.path.join(SCRIPT_DIR, 'hostinger_responses.csv'), 'w', newline='', encoding='utf-8') as f:
            fn = ['classification', 'sender', 'subject', 'date', 'reason', 'body_preview']
            w = csv.DictWriter(f, fieldnames=fn)
            w.writeheader()
            for r in all_responses:
                w.writerow({k: r.get(k, '') for k in fn})
        
        yes = sum(1 for r in all_responses if r['classification'] == 'YES')
        maybe = sum(1 for r in all_responses if r['classification'] == 'MAYBE')
        no = sum(1 for r in all_responses if r['classification'] == 'NO')
        bounce = sum(1 for r in all_responses if r['classification'] == 'BOUNCE')
        auto = sum(1 for r in all_responses if r['classification'] == 'AUTO')
        unread = sum(1 for r in all_responses if r['classification'] == 'UNREAD')
        
        print(f"\n{'='*60}")
        print(f"  RESULTS")
        print(f"{'='*60}")
        print(f"  Total replies: {len(all_responses)}")
        print(f"  ✅ YES: {yes}")
        print(f"  🤔 MAYBE: {maybe}")
        print(f"  ❌ NO: {no}")
        print(f"  📬 BOUNCE: {bounce}")
        print(f"  🤖 AUTO: {auto}")
        print(f"  📋 UNREAD: {unread}")
        
        # Show YES/MAYBE highlights
        for r in all_responses:
            if r['classification'] in ('YES', 'MAYBE', 'UNREAD'):
                print(f"\n  {'='*40}")
                print(f"  {r['classification']}: {r['sender']}")
                print(f"  Subj: {r['subject']}")
                print(f"  Body: {r['body_preview'][:200]}")
    else:
        print(f"\n📭 No human replies found in Hostinger inbox")

if __name__ == '__main__':
    main()

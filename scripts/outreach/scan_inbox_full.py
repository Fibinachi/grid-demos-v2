#!/usr/bin/env python3
"""
Full Inbox & Trash Scanner
==========================
Uses Gmail API to scan INBOX and Trash for:
1. Bounce notifications
2. Decline replies from foundations
3. Auto-updates declined_foundations.txt and bounced_emails.txt
4. Trashes irrelevant emails to keep inbox clean
"""
import os, sys, json, base64, re, time
from datetime import datetime
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "gmail_token.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "gmail_credentials.json")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
DECLINED_FILE = os.path.join(SCRIPT_DIR, "declined_foundations.txt")
BOUNCED_FILE = os.path.join(SCRIPT_DIR, "bounced_emails.txt")

# Keywords that indicate decline in email body
DECLINE_PHRASES = [
    "does not support", "do not support", "cannot support",
    "unable to support", "not able to", "regret to inform",
    "unfortunately", "not a fit", "not a good fit",
    "not currently funding", "no longer funding",
    "does not align", "not aligned", "not within our",
    "outside our scope", "outside our mission",
    "not currently accepting", "limited resources",
    "not in a position to", "unable to accommodate",
    "decline", "declined", "not interested",
    "funding priorities have changed",
    "focus our resources", "carefully considered",
    "many worthy requests", "limited budget",
    "not this cycle", "not this year",
    "does not provide funding for",
    "do not fund individuals",
    "only fund organizations",
    "only support organizations",
]

def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)

def list_messages(service, query='', label_ids=['INBOX']):
    """List messages matching query."""
    msgs = []
    page_token = None
    while True:
        result = service.users().messages().list(
            userId='me', q=query, labelIds=label_ids,
            pageToken=page_token, maxResults=500).execute()
        msgs.extend(result.get('messages', []))
        page_token = result.get('nextPageToken')
        if not page_token:
            break
    return msgs

def get_message(service, msg_id):
    """Get full message content."""
    return service.users().messages().get(
        userId='me', id=msg_id, format='full').execute()

def get_body(msg):
    """Extract plain text body from message."""
    parts = msg.get('payload', {}).get('parts', [])
    body = ''
    for part in parts:
        if part.get('mimeType') == 'text/plain':
            data = part.get('body', {}).get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                break
    if not body:
        # Try full message body
        data = msg.get('payload', {}).get('body', {}).get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    return body

def get_headers(msg):
    """Get headers dict."""
    headers = {}
    for h in msg.get('payload', {}).get('headers', []):
        headers[h['name'].lower()] = h['value']
    return headers

def is_bounce(headers, body):
    """Check if message is a bounce notification."""
    subject = headers.get('subject', '')
    sender = headers.get('from', '')
    to = headers.get('to', '')
    
    if 'mailer-daemon' in sender.lower():
        return True
    if 'mail delivery failed' in subject.lower():
        return True
    if 'undelivered' in subject.lower():
        return True
    if 'returned mail' in subject.lower():
        return True
    if 'bounce' in subject.lower():
        return True
    if 'failure notice' in subject.lower():
        return True
    if 'delivery status notification' in subject.lower():
        return True
    if body and ('permanent error' in body.lower() or '550' in body):
        return True
    
    return False

def extract_bounced_address(msg):
    """Extract the original bounced email address from a bounce message."""
    body = get_body(msg)
    headers = get_headers(msg)
    
    # Check body for the original email
    if body:
        emails = re.findall(r'[\w.+-]+@[\w-]+\.\w+', body)
        # Skip mailer-daemon addresses
        real = [e for e in emails if 'mailer-daemon' not in e.lower() and 'amazonses' not in e.lower()]
        if real:
            return real[0]
    
    # Check headers
    for h in ['x-failed-recipients', 'original-recipient', 'final-recipient']:
        val = headers.get(h, '')
        if val:
            e = re.search(r'[\w.+-]+@[\w-]+\.\w+', val)
            if e:
                return e.group()
    
    return ''

def is_decline(body, headers):
    """Check if message body contains decline language."""
    if not body:
        return False, ''
    
    body_lower = body.lower()
    for phrase in DECLINE_PHRASES:
        if phrase in body_lower:
            return True, phrase
    return False, ''

def extract_foundation_info(body, headers):
    """Try to extract foundation name/EIN from the email body or subject."""
    subject = headers.get('subject', '')
    sender = headers.get('from', '')
    
    # Try to get foundation name from subject (e.g., "RE: Inquiry to XYZ Foundation")
    name_match = re.search(r'(?:inquiry|regarding|re:)\s*(.+?)(?:foundation|fund|trust)', subject, re.IGNORECASE)
    if name_match:
        return name_match.group(0).strip()
    
    # Return sender name
    sender_match = re.match(r'([^<]+)', sender)
    if sender_match:
        return sender_match.group(0).strip()
    
    return sender

def trash_message(service, msg_id):
    """Move message to trash."""
    try:
        service.users().messages().trash(userId='me', id=msg_id).execute()
        return True
    except:
        return False

def main():
    print("=" * 60)
    print("  FULL INBOX & TRASH SCANNER")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)
    
    service = get_service()
    
    # Load existing bounced/declined
    bounced = set()
    if os.path.exists(BOUNCED_FILE):
        with open(BOUNCED_FILE) as f:
            bounced = {line.strip() for line in f if line.strip() and '@' in line}
    
    declined = set()
    if os.path.exists(DECLINED_FILE):
        with open(DECLINED_FILE) as f:
            declined = {line.strip().split('|')[0] for line in f if line.strip()}
    
    print(f"Current bounced: {len(bounced)}")
    print(f"Current declined: {len(declined)}")
    
    # Scan INBOX
    print(f"\n--- Scanning INBOX ---")
    inbox_msgs = list_messages(service, label_ids=['INBOX'])
    print(f"Messages in INBOX: {len(inbox_msgs)}")
    
    new_bounces = []
    new_declines = []
    trashed = 0
    
    for i, msg_summary in enumerate(inbox_msgs):
        msg = get_message(service, msg_summary['id'])
        headers = get_headers(msg)
        body = get_body(msg)
        subject = headers.get('subject', 'N/A')
        sender = headers.get('from', 'N/A')
        
        # Check bounce
        if is_bounce(headers, body):
            bounced_addr = extract_bounced_address(msg)
            if bounced_addr and bounced_addr not in bounced:
                bounced.add(bounced_addr)
                new_bounces.append(bounced_addr)
                print(f"  [{i+1}] BOUNCE: {bounced_addr} (from {sender[:40]})")
            
            # Trash it
            if trash_message(service, msg_summary['id']):
                trashed += 1
            continue
        
        # Check decline
        is_dec, phrase = is_decline(body, headers)
        if is_dec:
            foundation = extract_foundation_info(body, headers)
            print(f"  [{i+1}] DECLINE from {foundation[:50]} (phrase: {phrase[:40]})")
            new_declines.append((foundation, phrase, sender))
            
            # Trash it
            if trash_message(service, msg_summary['id']):
                trashed += 1
            continue
        
        # Print non-bounce/non-decline emails for review
        print(f"  [{i+1}] OTHER: {subject[:60]} from {sender[:40]}")
    
    # Save new bounces
    if new_bounces:
        with open(BOUNCED_FILE, 'a') as f:
            for addr in new_bounces:
                f.write(f"{addr}\n")
        print(f"\n✅ {len(new_bounces)} new bounces saved to bounced_emails.txt")
    
    # Save new declines
    if new_declines:
        with open(DECLINED_FILE, 'a') as f:
            for foundation, phrase, sender in new_declines:
                f.write(f"UNKNOWN|{foundation}|{phrase}|{datetime.now().isoformat()}|inbox_scan\n")
        print(f"✅ {len(new_declines)} new declines saved to declined_foundations.txt")
    
    print(f"Trashed: {trashed} messages")
    
    # Now scan TRASH
    print(f"\n--- Scanning TRASH ---")
    trash_msgs = list_messages(service, label_ids=['TRASH'])
    print(f"Messages in TRASH: {len(trash_msgs)}")
    
    trash_bounces = 0
    trash_declines = 0
    trash_kept = []
    
    for msg_summary in trash_msgs:
        msg = get_message(service, msg_summary['id'])
        headers = get_headers(msg)
        body = get_body(msg)
        subject = headers.get('subject', 'N/A')
        sender = headers.get('from', 'N/A')
        
        if is_bounce(headers, body):
            bounced_addr = extract_bounced_address(msg)
            if bounced_addr and bounced_addr not in bounced:
                bounced.add(bounced_addr)
                new_bounces.append(bounced_addr)
                print(f"  Trash BOUNCE: {bounced_addr}")
                trash_bounces += 1
            continue
        
        is_dec, phrase = is_decline(body, headers)
        if is_dec:
            print(f"  Trash DECLINE: {subject[:50]}")
            trash_declines += 1
            continue
        
        trash_kept.append((subject, sender))
    
    if trash_kept:
        print(f"\n  Trash items kept (review manually):")
        for sub, snd in trash_kept[:10]:
            print(f"    {sub[:50]} from {snd[:40]}")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total inbox scanned: {len(inbox_msgs)}")
    print(f"New bounces found: {len(new_bounces)}")
    print(f"New declines found: {len(new_declines)}")
    print(f"Trashed: {trashed}")
    print(f"Total bounced addresses: {len(bounced)}")
    print(f"Declined foundations file: {len([l for l in open(DECLINED_FILE) if l.strip()]) if os.path.exists(DECLINED_FILE) else 0} entries")

if __name__ == '__main__':
    main()

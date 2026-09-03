"""
Gmail Response Classifier
=========================
Scans Gmail inbox for replies to sent foundation emails,
classifies them as YES/MAYBE/NO, and moves to labeled folders.

Usage: python gmail_response_classifier.py
"""
import os
import sys
import json
import re
import base64
from email.message import EmailMessage
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from gmail_api_sender import (
    GMAIL_USER, SENDER_EMAIL, SENDER_NAME,
    CREDENTIALS_FILE, TOKEN_FILE, SCOPES, SCRIPT_DIR as _
)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Labels ──
LABEL_YES = "FoundationResponses/Yes"
LABEL_MAYBE = "FoundationResponses/Maybe"  
LABEL_NO = "FoundationResponses/No"
LABEL_UNREAD = "FoundationResponses/Unread"

# Classify response text
YES_KEYWORDS = [
    'interested', 'would like to', 'happy to', 'pleased to', 'yes',
    'definitely', 'sounds good', 'love to', 'looking forward',
    'let\'s discuss', 'happy to help', 'support your', 'funding',
    'grant', 'scholarship', 'contribute', 'donation', 'sponsor',
    'consider', 'apply', 'application', 'proposal',
    'tell me more', 'more information', 'send me',
    'meeting', 'call', 'zoom', 'discuss further',
]

MAYBE_KEYWORDS = [
    'not sure', 'maybe', 'possibly', 'might be', 'could be',
    'will think', 'let me think', 'need to discuss', 'check with',
    'talk to my', 'board', 'committee', 'review',
    'forwarded', 'passing along', 'not the right person',
    'directed to', 'cc\'ing', 'copying',
    'out of office', 'vacation', 'away',
    'busy', 'swamped', 'will get back',
]

NO_KEYWORDS = [
    'not interested', 'unfortunately', 'cannot support', 'not able to',
    'do not fund', 'don\'t fund', 'not funding', 'no longer',
    'does not align', 'not aligned', 'not a fit',
    'decline', 'declined', 'regret', 'unable to',
    'not within', 'outside our', 'limited resources',
    'not accepting', 'not currently', 'do not accept',
    'only fund organizations', 'only support organizations',
    'not in a position', 'not the right fit',
    'remove from', 'unsubscribe', 'stop emailing',
]

# The emails we sent (for matching replies)
SENT_EMAILS = [
    ("730771408", "TULSA CHRISTIAN FOUNDATION INC", "info@christianfoundation.org"),
    ("821501463", "CHRISTIAN LEGACY FOUNDATION", "info@legacyfoundation.org"),
    ("263631275", "FAITHFUL SERVANTS FOUNDATION", "joy@faithfulservantsfoundation.org"),
    ("716050288", "TRINITY FOUNDATION", "tjtrinityfound@aol.com"),
    ("431551131", "OZARKS HEALTH ADVOCACY FOUNDATION", "mwitthar@itifinancialmgt.com"),
    ("453240491", "SORENSON LEGACY FOUNDATION", "lisa@sdihq.com"),
]

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def ensure_label(service, label_name):
    """Create a Gmail label if it doesn't exist."""
    results = service.users().labels().list(userId=GMAIL_USER).execute()
    for label in results.get('labels', []):
        if label['name'] == label_name:
            return label['id']
    
    label_body = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show',
    }
    created = service.users().labels().create(userId=GMAIL_USER, body=label_body).execute()
    print(f"  📁 Created label: {label_name}")
    return created['id']

def get_message_body(msg):
    """Extract plain text from a Gmail message."""
    parts = []
    if 'parts' in msg['payload']:
        for part in msg['payload']['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    parts.append(base64.urlsafe_b64decode(data).decode('utf-8', errors='replace'))
    elif msg['payload']['mimeType'] == 'text/plain':
        data = msg['payload']['body'].get('data', '')
        if data:
            parts.append(base64.urlsafe_b64decode(data).decode('utf-8', errors='replace'))
    return '\n'.join(parts)

def decode_header_value(value):
    """Decode email header value."""
    if not value:
        return ''
    # Remove any encoded-word encoding
    value = re.sub(r'=\?[^?]+\?[Bb]\?([^?]*)\?=', lambda m: base64.b64decode(m.group(1)).decode('utf-8', errors='replace'), value)
    value = re.sub(r'=\?[^?]+\?[Qq]\?([^?]*)\?=', lambda m: '', value)
    return value

def get_header(msg, name):
    """Get a header value from a message."""
    for header in msg['payload']['headers']:
        if header['name'].lower() == name.lower():
            return decode_header_value(header['value'])
    return ''

def classify_response(subject, sender, body):
    """Classify a response email as YES, MAYBE, or NO."""
    text = f"{subject} {sender} {body}".lower()
    
    # Check NO first (strongest signal)
    no_score = sum(1 for kw in NO_KEYWORDS if kw.lower() in text)
    # Check YES
    yes_score = sum(1 for kw in YES_KEYWORDS if kw.lower() in text)
    # Check MAYBE
    maybe_score = sum(1 for kw in MAYBE_KEYWORDS if kw.lower() in text)
    
    # Auto-bounce detection
    if 'mailer-daemon' in text or 'delivery failure' in text or 'undelivered' in text:
        return 'BOUNCE'
    
    if no_score >= 2 or (no_score >= 1 and yes_score == 0):
        return 'NO'
    elif yes_score >= 2 and no_score == 0:
        return 'YES'
    elif maybe_score >= 1 or (yes_score >= 1 and no_score >= 1):
        return 'MAYBE'
    elif 'auto-reply' in text or 'automatic reply' in text:
        return 'AUTO'
    else:
        return 'UNREAD'

def main():
    print("=" * 60)
    print("  GMAIL RESPONSE CLASSIFIER")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)
    
    service = get_gmail_service()
    print("✅ Gmail API connected")
    
    # Ensure labels exist
    print("\n📁 Ensuring labels...")
    label_ids = {}
    for label_name in [LABEL_YES, LABEL_MAYBE, LABEL_NO, LABEL_UNREAD]:
        label_ids[label_name] = ensure_label(service, label_name)
    
    # Search for replies to sent emails
    print("\n🔍 Searching for replies...")
    all_replies = []
    
    for ein, name, email_addr in SENT_EMAILS:
        # Search for replies from this email address
        query = f"from:{email_addr}"
        try:
            results = service.users().messages().list(
                userId=GMAIL_USER, q=query, maxResults=20
            ).execute()
            messages = results.get('messages', [])
            
            for msg_info in messages:
                msg = service.users().messages().get(
                    userId=GMAIL_USER, id=msg_info['id'], format='full'
                ).execute()
                
                subject = get_header(msg, 'Subject')
                sender = get_header(msg, 'From')
                date = get_header(msg, 'Date')
                body = get_message_body(msg)
                
                classification = classify_response(subject, sender, body)
                
                all_replies.append({
                    'id': msg_info['id'],
                    'ein': ein,
                    'foundation': name,
                    'email': email_addr,
                    'subject': subject[:80],
                    'sender': sender[:60],
                    'date': date,
                    'classification': classification,
                    'body_preview': body[:200] if body else '',
                })
                
                print(f"\n  📧 {name[:35]:35s}")
                print(f"     From: {sender[:50]}")
                print(f"     Subj: {subject[:60]}")
                print(f"     Class: {classification}")
                
        except Exception as e:
            print(f"  ❌ Error searching {email_addr}: {e}")
    
    # Apply labels and move messages
    print(f"\n\n📁 Classifying and moving {len(all_replies)} messages...")
    
    for reply in all_replies:
        msg_id = reply['id']
        classification = reply['classification']
        
        if classification == 'YES':
            target_label = LABEL_YES
        elif classification == 'NO':
            target_label = LABEL_NO
        elif classification == 'MAYBE':
            target_label = LABEL_MAYBE
        else:
            target_label = LABEL_UNREAD
        
        label_id = label_ids[target_label]
        
        try:
            # Apply label
            service.users().messages().modify(
                userId=GMAIL_USER,
                id=msg_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            print(f"  📂 {reply['foundation'][:35]:35s} → {target_label}")
        except Exception as e:
            print(f"  ❌ Error labeling {msg_id}: {e}")
    
    # Summary
    yes_count = sum(1 for r in all_replies if r['classification'] == 'YES')
    maybe_count = sum(1 for r in all_replies if r['classification'] == 'MAYBE')
    no_count = sum(1 for r in all_replies if r['classification'] == 'NO')
    bounce_count = sum(1 for r in all_replies if r['classification'] == 'BOUNCE')
    auto_count = sum(1 for r in all_replies if r['classification'] == 'AUTO')
    unread_count = sum(1 for r in all_replies if r['classification'] == 'UNREAD')
    
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    print(f"  Total replies found: {len(all_replies)}")
    print(f"  ✅ YES (interested): {yes_count}")
    print(f"  🤔 MAYBE: {maybe_count}")
    print(f"  ❌ NO (declined): {no_count}")
    print(f"  📬 BOUNCE: {bounce_count}")
    print(f"  🤖 AUTO-REPLY: {auto_count}")
    print(f"  📋 UNREAD (needs review): {unread_count}")
    
    if all_replies:
        print(f"\n  Detailed results saved to: gmail_responses.json")
        import json as j
        with open(os.path.join(SCRIPT_DIR, 'gmail_responses.json'), 'w') as f:
            j.dump(all_replies, f, indent=2, default=str)

if __name__ == '__main__':
    main()

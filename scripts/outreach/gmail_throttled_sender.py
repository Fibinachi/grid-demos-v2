#!/usr/bin/env python3
"""
Throttled Gmail API Sender for EC2
Sends ~2 emails every 5 minutes using the Gmail API.
Runs through theology_final_send.csv one foundation at a time.
"""
import sys
import os
import time
import json
import csv
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Import the sender's personalization
from gmail_api_sender import (
    personalize_intro, SENDER_NAME, SENDER_EMAIL, GMAIL_USER,
    CREDENTIALS_FILE, TOKEN_FILE, SCOPES, LOG_DIR, BRIDGE,
    load_declined_eins
)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.message import EmailMessage
import base64

# ── Config ──
INPUT_CSV = os.path.join(SCRIPT_DIR, "theology_gmail_send.csv")
SENT_LOG = os.path.join(SCRIPT_DIR, "gmail_sent_log.txt")
SLEEP_BETWEEN = 150  # seconds (~2 per 5 min)

os.makedirs(LOG_DIR, exist_ok=True)

def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)

def load_sent_eins():
    """Load previously sent EINs from log."""
    if not os.path.exists(SENT_LOG):
        return set()
    with open(SENT_LOG) as f:
        return {line.strip().split(',')[0] for line in f if line.strip()}

def log_sent(ein, name, email):
    """Log a sent email."""
    with open(SENT_LOG, 'a') as f:
        f.write(f"{ein},{name},{email},{datetime.now().isoformat()}\n")

def load_declined_eins_set():
    """Load declined/bounced EINs from multiple sources."""
    declined = set()
    
    # From declined_foundations module
    try:
        from declined_foundations import load_declined_eins as lde
        declined.update(lde())
    except:
        pass
    
    # From declined_foundations.txt
    for path in ['declined_foundations.txt', 'bounced_emails.txt']:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    parts = line.strip().split('|')
                    if parts and parts[0].strip():
                        declined.add(parts[0].strip())
    
    return declined

BAD_EMAIL_PATTERNS = [
    'info@', 'contact@', 'hello@', 'admin@', 'webmaster@',
    'support@', 'mail@', 'office@', 'email@', 'inquiries@',
    'ask@', 'hello@', 'hello@', 'media@', 'press@',
    'example.com', 'domain.com', 'yourname',
]

def is_bad_email(email):
    """Check if email looks like a generic/throwaway address."""
    email_lower = email.lower()
    for pat in BAD_EMAIL_PATTERNS:
        if email_lower.startswith(pat):
            return True
    return False

def send_email(service, row):
    """Send a single email via Gmail API."""
    name = row.get('NAME', '')
    email_addr = row.get('EMAIL', '').strip() or row.get('HAS_EMAIL', '')
    ein = row.get('EIN', '')
    
    if not email_addr or email_addr == 'YES':
        print(f"  SKIP {name} — no email address")
        return False
    
    if is_bad_email(email_addr):
        print(f"  SKIP {name} — generic email <{email_addr}>")
        return False
    
    # Personalize
    intro = personalize_intro(row)
    body = f"""Dear {name} Foundation Team,

{intro}

{BRIDGE}

I would be happy to share my CV and discuss how my background and goals align with your foundation's mission. Thank you for your consideration.

Warmly,
{chr(10)}{SENDER_NAME}"""

    msg = EmailMessage()
    msg.set_content(body)
    msg['To'] = email_addr
    msg['From'] = SENDER_EMAIL
    msg['Subject'] = f"Inquiry: Theological Studies at Trinity College, University of Toronto"
    
    try:
        encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId=GMAIL_USER, body={'raw': encoded}).execute()
        log_sent(ein, name, email_addr)
        print(f"  ✅ Sent to {name} <{email_addr}>")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {name} — {e}")
        return False

def main():
    print("=" * 60)
    print("  THROTTLED GMAIL SENDER (~2 emails per 5 min)")
    print(f"  Started: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Load foundations
    with open(INPUT_CSV, 'r') as f:
        rows = list(csv.DictReader(f))
    print(f"\nLoaded {len(rows)} foundations")
    
    # Load sent log
    sent_eins = load_sent_eins()
    print(f"Already sent: {len(sent_eins)}")
    
    # Filter unsent
    unsent = [r for r in rows if r['EIN'] not in sent_eins]
    
    # Filter declined/bounced
    declined = load_declined_eins_set()
    if declined:
        before = len(unsent)
        unsent = [r for r in unsent if r['EIN'] not in declined]
        print(f"Declined/bounced: {len(declined)} (skipped {before - len(unsent)})")
    
    print(f"Remaining to send: {len(unsent)}")
    
    if not unsent:
        print("All done!")
        return
    
    # Auth
    print("\nAuthenticating Gmail API...")
    service = get_gmail_service()
    print("Authenticated!\n")
    
    # Send loop
    for i, row in enumerate(unsent):
        name = row.get('NAME', '')
        ein = row.get('EIN', '')
        print(f"\n[{i+1}/{len(unsent)}] {name} ({ein})")
        
        sent = send_email(service, row)
        
        if sent and i < len(unsent) - 1:
            print(f"  Sleeping {SLEEP_BETWEEN}s... ({datetime.now().isoformat()})")
            time.sleep(SLEEP_BETWEEN)
    
    print(f"\n{'='*60}")
    print(f"Batch complete! Sent: {len(unsent)}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()

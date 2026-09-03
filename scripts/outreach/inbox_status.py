#!/usr/bin/env python3
"""Quick inbox status check."""
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

creds = Credentials.from_authorized_user_file('gmail_token.json', ['https://www.googleapis.com/auth/gmail.modify'])
if creds.expired: creds.refresh(Request())
svc = build('gmail', 'v1', credentials=creds)

msgs = svc.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=50).execute()
print(f"INBOX: {len(msgs.get('messages', []))} remaining")
for m in msgs.get('messages', []):
    msg = svc.users().messages().get(userId='me', id=m['id'], format='metadata', metadataHeaders=['Subject','From']).execute()
    h = {x['name']: x['value'] for x in msg['payload']['headers']}
    print(f"  {h.get('Subject','')[:50]:50s} | {h.get('From','')[:40]}")

trash = svc.users().messages().list(userId='me', labelIds=['TRASH'], maxResults=500).execute()
print(f"\nTRASH: {len(trash.get('messages', []))} messages")

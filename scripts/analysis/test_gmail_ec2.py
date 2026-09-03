#!/usr/bin/env python3
"""Test script to verify Gmail API token works on EC2."""
import sys, os, json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
from email.message import EmailMessage

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gmail_token.json")
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gmail_credentials.json")

print("Step 1: Checking token file...", flush=True)
if os.path.exists(TOKEN_FILE):
    print(f"  Token file exists: {os.path.getsize(TOKEN_FILE)} bytes", flush=True)
else:
    print("  TOKEN FILE MISSING", flush=True)
    sys.exit(1)

print("Step 2: Loading credentials...", flush=True)
creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
print(f"  Valid: {creds.valid}", flush=True)
print(f"  Has refresh: {bool(creds.refresh_token)}", flush=True)
print(f"  Expired: {creds.expired}", flush=True)

if creds.expired and creds.refresh_token:
    print("Step 3: Refreshing token...", flush=True)
    creds.refresh(Request())
    print(f"  Token refreshed. Valid: {creds.valid}", flush=True)

print("Step 4: Building Gmail service...", flush=True)
service = build('gmail', 'v1', credentials=creds)

print("Step 5: Getting profile...", flush=True)
profile = service.users().getProfile(userId='me').execute()
print(f"  Authenticated as: {profile.get('emailAddress', 'UNKNOWN')}", flush=True)

print("\n✅ Gmail API authentication successful!", flush=True)

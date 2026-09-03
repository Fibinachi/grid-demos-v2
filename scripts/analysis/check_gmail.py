"""Check Gmail for Census API key and recent responses"""
import os, json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "gmail_token.json")

if not os.path.exists(token_path):
    print("No Gmail token found")
    exit()

with open(token_path) as f:
    creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)

if not creds or not creds.valid:
    print("Gmail auth invalid or expired")
    exit()

service = build("gmail", "v1", credentials=creds)

# Search for census emails
results = service.users().messages().list(userId="me", q="census api key OR from:census").execute()
msgs = results.get("messages", [])
print(f"Census-related emails: {len(msgs)}")
for msg in msgs[:3]:
    m = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From","Subject","Date"]).execute()
    headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
    print(f"  [{headers.get('Date','?')[:25]}] {headers.get('From','?')[:40]}: {headers.get('Subject','?')[:60]}")

# Check unread
results2 = service.users().messages().list(userId="me", q="is:unread").execute()
unread = results2.get("messages", [])
print(f"\nUnread emails: {len(unread)}")

# Show last 10 recent
results3 = service.users().messages().list(userId="me", maxResults=10).execute()
recent = results3.get("messages", [])
print(f"\nLast 10 emails:")
for msg in recent:
    m = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From","Subject","Date"]).execute()
    headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
    print(f"  [{headers.get('Date','?')[:25]}] {headers.get('From','?')[:40]}: {headers.get('Subject','?')[:60]}")

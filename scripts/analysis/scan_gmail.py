"""Quick Gmail inbox scan - check new/unread messages."""
import json, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = "data/gmail_token.json"
creds = Credentials.from_authorized_user_info(json.load(open(TOKEN)))
service = build("gmail", "v1", credentials=creds)

# Get inbox stats
profile = service.users().getProfile(userId="me").execute()
print(f"Email: {profile['emailAddress']}")
print(f"Threads: {profile.get('threadsTotal',0)} total, {profile.get('threadsUnread',0)} unread")

# List recent messages
results = service.users().messages().list(userId="me", maxResults=20, q="in:inbox").execute()
msgs = results.get("messages", [])
print(f"\n=== RECENT INBOX ({len(msgs)} shown) ===")

for m in msgs:
    msg = service.users().messages().get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From","Subject","Date"]).execute()
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    label_ids = msg.get("labelIds", [])
    unread = "📬" if "UNREAD" in label_ids else "  "
    cat = "📥" if "INBOX" in label_ids else "📤"
    print(f"  {unread}{cat} {headers.get('Date','')[:16]:16s} {headers.get('From','')[:35]:35s} {headers.get('Subject','')[:50]}")

# Count by category
cats = ["INBOX", "SENT", "SPAM", "TRASH", "UNREAD"]
print(f"\n=== LABEL COUNTS ===")
for c in cats:
    r = service.users().messages().list(userId="me", maxResults=1, q=f"label:{c}").execute()
    print(f"  {c:10s}: {r.get('resultSizeEstimate',0)}")

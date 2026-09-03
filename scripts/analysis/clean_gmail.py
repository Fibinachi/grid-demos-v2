"""Clean Gmail inbox - archive bounces, flag important messages."""
import json, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = "data/gmail_token.json"
creds = Credentials.from_authorized_user_info(json.load(open(TOKEN)))
service = build("gmail", "v1", credentials=creds)

# Get all inbox messages
results = service.users().messages().list(userId="me", maxResults=500, q="in:inbox").execute()
msgs = results.get("messages", [])
print(f"Total inbox messages: {len(msgs)}")

bounce_count = 0
keep_count = 0
trash_ids = []
keep_msgs = []

for m in msgs:
    msg = service.users().messages().get(userId="me", id=m["id"], format="metadata", 
                                         metadataHeaders=["From","Subject","Date"]).execute()
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    subj = headers.get("Subject","")
    frm = headers.get("From","")
    
    # Bounce notification
    if "Delivery Status Notification" in subj or "Undeliverable" in subj or "Mail Delivery Subsystem" in frm:
        bounce_count += 1
        trash_ids.append(m["id"])
    # Security alerts - keep
    elif "Security alert" in subj:
        keep_count += 1
        keep_msgs.append(("SECURITY", frm, subj))
    # Mapbox etc
    elif "Mapbox" in frm:
        keep_count += 1
        keep_msgs.append(("ONBOARDING", frm, subj))
    # Everything else
    else:
        keep_count += 1
        keep_msgs.append(("OTHER", frm, subj))

print(f"\nBounce notifications: {bounce_count}")
print(f"Keep messages: {keep_count}")

if keep_msgs:
    print(f"\n=== KEPT MESSAGES ===")
    for cat, frm, subj in keep_msgs:
        print(f"  [{cat}] {frm[:35]:35s} {subj[:60]}")

# Trash the bounces
if trash_ids:
    # Gmail API batch trash - do it in batches of 100
    batch_size = 100
    for i in range(0, len(trash_ids), batch_size):
        batch = trash_ids[i:i+batch_size]
        service.users().messages().batchModify(
            userId="me", body={"ids": batch, "removeLabelIds": ["INBOX"], "addLabelIds": ["TRASH"]}
        ).execute()
    print(f"\n✅ Trashed {len(trash_ids)} bounce notifications")

# Also check SPAM folder
spam = service.users().messages().list(userId="me", maxResults=50, q="in:spam").execute()
spam_msgs = spam.get("messages", [])
print(f"\nSPAM folder: {spam.get('resultSizeEstimate', len(spam_msgs))} messages")
if spam_msgs:
    for m in spam_msgs[:5]:
        msg = service.users().messages().get(userId="me", id=m["id"], format="metadata",
                                             metadataHeaders=["From","Subject"]).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        print(f"  {headers.get('From','')[:35]:35s} {headers.get('Subject','')[:60]}")

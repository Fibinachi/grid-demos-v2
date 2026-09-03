"""Check Gmail using gcloud application default credentials"""
import os, json, base64
from google.auth import default
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Use gcloud ADC (Application Default Credentials)
creds, project = default()
print(f"Using project: {project}")
print(f"Creds type: {type(creds).__name__}")

# Scopes might need to be requested
if hasattr(creds, 'with_scopes'):
    creds = creds.with_scopes(SCOPES)

try:
    service = build("gmail", "v1", credentials=creds)
    
    # Check recent emails
    results = service.users().messages().list(userId="me", maxResults=5).execute()
    msgs = results.get("messages", [])
    print(f"\nRecent emails: {len(msgs)}")
    
    for msg in msgs[:5]:
        m = service.users().messages().get(userId="me", id=msg["id"], format="metadata", 
            metadataHeaders=["From","Subject","Date"]).execute()
        headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
        date = headers.get("Date","?")[:25]
        sender = headers.get("From","?")[:40]
        subject = headers.get("Subject","?")[:60]
        print(f"  [{date}] {sender}: {subject}")
    
    # Search for census API key
    print("\n--- Searching for census emails ---")
    census = service.users().messages().list(userId="me", q="census").execute()
    for msg in census.get("messages", [])[:3]:
        m = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
        print(f"\nSubject: {headers.get('Subject','?')}")
        print(f"From: {headers.get('From','?')}")
        # Get body
        if "parts" in m["payload"]:
            for part in m["payload"]["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    text = base64.urlsafe_b64decode(data).decode()
                    print(f"Body: {text[:1000]}")
    
    # Count unread
    unread = service.users().messages().list(userId="me", q="is:unread").execute()
    print(f"\nUnread: {len(unread.get('messages',[]))}")
    
except Exception as e:
    print(f"Error: {e}")

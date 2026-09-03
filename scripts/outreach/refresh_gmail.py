"""Refresh Gmail token and check for Census key + responses"""
import os, json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

root = os.path.dirname(os.path.abspath(__file__))
token_path = os.path.join(root, "data", "gmail_token.json")
creds_path = os.path.join(root, "data", "gmail_credentials.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Try to refresh the token
if os.path.exists(token_path):
    with open(token_path) as f:
        creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
    
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save refreshed token
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            print("Token refreshed successfully")
        except Exception as e:
            print(f"Token refresh failed: {e}")
    
    if creds and creds.valid:
        service = build("gmail", "v1", credentials=creds)
        
        # Search for census emails
        results = service.users().messages().list(userId="me", q="census").execute()
        msgs = results.get("messages", [])
        print(f"\nCensus emails: {len(msgs)}")
        for msg in msgs[:3]:
            m = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From","Subject","Date"]).execute()
            headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
            print(f"  [{headers.get('Date','?')[:25]}] {headers.get('From','?')}: {headers.get('Subject','?')}")
            # Get full body to extract key
            full = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
            if "parts" in full["payload"]:
                for part in full["payload"]["parts"]:
                    if part["mimeType"] == "text/plain":
                        body = part["body"].get("data", "")
                        import base64
                        text = base64.urlsafe_b64decode(body).decode()
                        print(f"  Body: {text[:500]}")
        
        # Check unread
        results2 = service.users().messages().list(userId="me", q="is:unread").execute()
        unread = results2.get("messages", [])
        print(f"\nUnread: {len(unread)}")
        
        # Show last 10
        results3 = service.users().messages().list(userId="me", maxResults=10).execute()
        print(f"\nLast 10 emails:")
        for msg in results3.get("messages", []):
            m = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From","Subject","Date"]).execute()
            headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
            print(f"  [{headers.get('Date','?')[:25]}] {headers.get('From','?')[:40]}: {headers.get('Subject','?')[:60]}")
    else:
        print("Token invalid and cannot be refreshed")
        print("Need to re-authenticate via browser")
else:
    print("No token file found")

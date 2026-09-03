"""Read the rescued foundation replies from Gmail inbox."""
import json, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = "data/gmail_token.json"
creds = Credentials.from_authorized_user_info(json.load(open(TOKEN)))
service = build("gmail", "v1", credentials=creds)

# Search for the two rescued replies
queries = [
    "shelley@newhope.rocks",
    "Central Woodward Christian"
]

for q in queries:
    results = service.users().messages().list(userId="me", maxResults=5, q=q).execute()
    for m in results.get("messages", []):
        msg = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        
        print(f"{'='*70}")
        print(f"FROM: {headers.get('From','')}")
        print(f"SUBJECT: {headers.get('Subject','')}")
        print(f"DATE: {headers.get('Date','')}")
        print(f"{'='*70}")
        
        # Extract body
        body = ""
        if "parts" in msg["payload"]:
            for part in msg["payload"]["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part["body"].get("data", "")
                    import base64
                    body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                    break
        elif "body" in msg["payload"]:
            data = msg["payload"]["body"].get("data", "")
            if data:
                import base64
                body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        
        # Print body (trimmed if too long)
        if body:
            lines = body.strip().split("\n")
            # Show last 15 lines (the core message, not the quoted history)
            relevant = [l for l in lines if l.strip() and not l.startswith(">") and not l.startswith("On ")]
            if len(relevant) > 20:
                relevant = relevant[-20:]
            print("\n".join(relevant[:30]))
        else:
            print("(no plain text body)")
        print()

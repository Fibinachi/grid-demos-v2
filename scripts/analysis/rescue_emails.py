"""Rescue replies from spam, then check Hostinger."""
import json, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = "data/gmail_token.json"
creds = Credentials.from_authorized_user_info(json.load(open(TOKEN)))
service = build("gmail", "v1", credentials=creds)

# 1. Move real replies out of spam
print("=== RESCUING FROM SPAM ===")
spam = service.users().messages().list(userId="me", maxResults=50, q="in:spam").execute()
for m in spam.get("messages", []):
    msg = service.users().messages().get(userId="me", id=m["id"], format="metadata",
                                         metadataHeaders=["From","Subject"]).execute()
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    subj = headers.get("Subject","")
    frm = headers.get("From","")
    
    # Real replies (not bounces)
    if "Undelivered" not in subj and "Undeliverable" not in subj:
        print(f"  RESCUED: {frm[:40]:40s} | {subj[:60]}")
        service.users().messages().modify(
            userId="me", id=m["id"],
            body={"removeLabelIds": ["SPAM"], "addLabelIds": ["INBOX"]}
        ).execute()
    else:
        print(f"  BOUNCE (keep in spam): {frm[:40]:40s} | {subj[:60]}")

# 2. Check Hostinger inbox  
print(f"\n=== HOSTINGER ===")
hr_path = "scripts/outreach/hostinger_responses.json"
if os.path.exists(hr_path):
    d = json.load(open(hr_path))
    if isinstance(d, list):
        # Categorize
        bounces = [r for r in d if "bounce" in str(r.get("type","")).lower() or "Undelivered" in str(r.get("subject",""))]
        declines = [r for r in d if "decline" in str(r.get("type","")).lower() or "not interested" in str(r.get("subject","")).lower()]
        auto_replies = [r for r in d if "automatic reply" in str(r.get("subject","")).lower() or "out of office" in str(r.get("subject","")).lower()]
        real = [r for r in d if r not in bounces and r not in declines and r not in auto_replies]
        
        print(f"  Total responses: {len(d)}")
        print(f"  Bounces: {len(bounces)}")
        print(f"  Declines: {len(declines)}")
        print(f"  Auto-replies/OOO: {len(auto_replies)}")
        print(f"  Real replies: {len(real)}")
        
        if real:
            print(f"\n  === REAL REPLIES ===")
            for r in real[-10:]:
                subj = str(r.get("subject",""))[:60]
                frm = str(r.get("from",""))[:35]
                print(f"    {frm:35s} | {subj}")
        
        if auto_replies:
            print(f"\n  === AUTO REPLIES (sample) ===")
            for r in auto_replies[:5]:
                print(f"    {str(r.get('from',''))[:35]:35s} | {str(r.get('subject',''))[:60]}")

# 3. Clean Hostinger - mark bounces/declines as cleaned
print(f"\n=== HOSTINGER CLEANUP ===")
print("  Bounces: delete/mark processed")
print("  Auto-replies: can be archived")
print("  Real replies: review for follow-up")

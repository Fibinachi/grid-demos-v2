"""Fix TRINITY misclassification - move to NO folder."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import auth from classifier
from gmail_api_sender import GMAIL_USER, CREDENTIALS_FILE, TOKEN_FILE, SCOPES
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

creds = None
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE) as f:
        creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())

service = build('gmail', 'v1', credentials=creds)

# Find labels
labels = service.users().labels().list(userId='me').execute()
yes_id = next(l['id'] for l in labels['labels'] if l['name'] == 'FoundationResponses/Yes')
no_id = next(l['id'] for l in labels['labels'] if l['name'] == 'FoundationResponses/No')

# Load responses
r = json.load(open('gmail_responses.json'))
msg_id = r[0]['id']

# Move from YES to NO
service.users().messages().modify(
    userId='me', id=msg_id,
    body={'removeLabelIds': [yes_id], 'addLabelIds': [no_id]}
).execute()

# Update JSON
r[0]['classification'] = 'NO'
json.dump(r, open('gmail_responses.json', 'w'), indent=2, default=str)
print("✅ Moved TRINITY to NO folder")
print(f"Response: {r[0]['body_preview'][:200]}")

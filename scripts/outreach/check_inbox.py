"""Check Gmail inbox and classify/clean up."""
import os, json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
token_path = 'data/gmail_token.json'

if not os.path.exists(token_path):
    print('No Gmail token found')
    exit()

with open(token_path) as f:
    creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)

if creds and creds.expired and creds.refresh_token:
    print('Token expired, refreshing...')
    creds.refresh(Request())
    with open(token_path, 'w') as f:
        f.write(creds.to_json())
    print('Refreshed!')

if not creds or not creds.valid:
    print('Gmail auth invalid or expired')
    exit()

service = build('gmail', 'v1', credentials=creds)

profile = service.users().getProfile(userId='me').execute()
print(f'Email: {profile["emailAddress"]}')
print()

# --- STATS ---
results = service.users().messages().list(userId='me', q='is:unread').execute()
unread = len(results.get('messages', []))
print(f'Unread: {unread}')

inbox = service.users().messages().list(userId='me', maxResults=500).execute()
total = len(inbox.get('messages', []))
print(f'Recent 500: {total}')
if inbox.get('resultSizeEstimate'):
    print(f'Est. total: {inbox["resultSizeEstimate"]}')

# --- LAST 30 EMAILS ---
results2 = service.users().messages().list(userId='me', maxResults=30).execute()
recent = results2.get('messages', [])
print(f'\n{"="*90}')
print(f'{"LAST 30 EMAILS":^90}')
print(f'{"="*90}')

emails = []
for msg in recent:
    m = service.users().messages().get(userId='me', id=msg['id'],
        format='metadata',
        metadataHeaders=['From','Subject','Date','LabelIds']).execute()
    headers = {h['name']: h['value'] for h in m['payload']['headers']}
    labels = m.get('labelIds', [])
    is_unread = 'UNREAD' in labels
    is_inbox = 'INBOX' in labels
    fr = headers.get('From', '?')
    subj = headers.get('Subject', '?')
    date = headers.get('Date', '?')
    emails.append({'id': msg['id'], 'from': fr, 'subject': subj, 'date': date, 'unread': is_unread, 'inbox': is_inbox})

for e in emails:
    u = '📬' if e['unread'] else '  '
    print(f'  {u} [{e["date"][:25]}] {e["from"][:45]:45s} {e["subject"][:65]}')

# --- CLASSIFICATION ---
print(f'\n{"="*90}')
print(f'{"CATEGORIES":^90}')
print(f'{"="*90}')

# Categorize by sender domain
categories = {}
for e in emails:
    fr = e['from'].lower()
    if 'noreply' in fr or 'no-reply' in fr:
        cat = '🔔 Notifications (no-reply)'
    elif 'google' in fr or 'gmail' in fr or 'youtube' in fr:
        cat = '📧 Google/Alerts'
    elif 'linkedin' in fr:
        cat = '💼 LinkedIn'
    elif 'github' in fr:
        cat = '🐙 GitHub'
    elif 'amazon' in fr or 'aws' in fr:
        cat = '📦 Amazon/AWS'
    elif 'census' in fr or '.gov' in fr:
        cat = '🏛️ Gov/Census'
    elif 'grant' in fr or 'foundation' in fr or 'nonprofit' in fr or '.org' in fr:
        cat = '🏢 Grants/Nonprofits'
    elif 'paypal' in fr or 'stripe' in fr or 'bank' in fr:
        cat = '💰 Finance'
    elif 'newsletter' in fr or 'mailchimp' in fr or 'sendgrid' in fr or 'substack' in fr:
        cat = '📰 Newsletters'
    else:
        cat = '📨 Person/Other'
    
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(e)

for cat, items in sorted(categories.items()):
    print(f'\n  {cat} ({len(items)}):')
    for e in items[:3]:
        u = '📬' if e['unread'] else '  '
        print(f'    {u} {e["subject"][:60]}')

# --- CLEANUP SUGGESTIONS ---
print(f'\n{"="*90}')
print(f'{"CLEANUP SUGGESTIONS":^90}')
print(f'{"="*90}')

# Find read emails that could be archived
read_inbox = [e for e in emails if not e['unread'] and e['inbox']]
if read_inbox:
    print(f'\n  📖 Read but still in inbox ({len(read_inbox)}):')
    for e in read_inbox[:5]:
        print(f'    - {e["subject"][:65]}')

# Find auto-replies/newsletters that could be cleaned
auto = [e for e in emails if 'noreply' in e['from'].lower() or 'mailchimp' in e['from'].lower()]
if auto:
    print(f'\n  🤖 Auto/no-reply emails ({len(auto)}):')
    for e in auto[:5]:
        print(f'    - {e["from"][:40]:40s} {e["subject"][:50]}')

print()
print(f'📬 = Unread')
print(f'To clean up: use Gmail web interface or I can help with specific actions.')

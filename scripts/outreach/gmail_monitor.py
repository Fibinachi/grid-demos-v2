"""
Gmail Inbox Monitor
===================
Polls the Gmail inbox for replies to sent foundation emails.
Logs new responses and can trigger follow-up actions.

Usage:
  python gmail_monitor.py              # One-time check
  python gmail_monitor.py --watch      # Watch mode (polls every 5 min)
  python gmail_monitor.py --watch --interval 60  # Custom interval in seconds
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "gmail_token.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "gmail_responses.json")
SEEN_FILE = os.path.join(SCRIPT_DIR, "gmail_seen_ids.txt")

# Foundation email domains we sent to (for matching replies)
# These are the auto-generated domains from foundation names
FOUNDATION_KEYWORDS = [
    'foundation', 'foundtn', 'fund', 'grant', 'philanthropy',
    'give', 'giving', 'charitable', 'endowment',
]


def get_service():
    with open(TOKEN_FILE, 'r') as f:
        creds = Credentials.from_authorized_user_info(json.load(f))
    return build('gmail', 'v1', credentials=creds)


def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_seen_ids(ids):
    with open(SEEN_FILE, 'a') as f:
        for i in ids:
            f.write(i + '\n')


def load_response_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    return {'responses': [], 'total': 0, 'last_check': None}


def save_response_log(log):
    with open(LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)


def check_inbox(service, seen_ids):
    """Check for new messages that look like replies."""
    response_log = load_response_log()
    new_responses = []

    # Search for recent messages that might be replies
    # Check inbox and also check for any message from the last 7 days
    query = 'in:inbox after:' + (datetime.now() - timedelta(days=7)).strftime('%Y/%m/%d')
    
    try:
        results = service.users().messages().list(
            userId='me', maxResults=50, q=query
        ).execute()
    except HttpError as e:
        print(f"API Error: {str(e)[:100]}")
        return []

    msgs = results.get('messages', [])
    if not msgs:
        return []

    new_ids = []
    for m in msgs:
        msg_id = m['id']
        if msg_id in seen_ids:
            continue
        new_ids.append(msg_id)

        # Get full message details
        try:
            msg = service.users().messages().get(
                userId='me', id=msg_id, format='metadata',
                metadataHeaders=['From', 'Subject', 'Date', 'To', 'References', 'In-Reply-To']
            ).execute()
        except HttpError:
            continue

        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        frm = headers.get('From', '')
        subj = headers.get('Subject', '')
        to = headers.get('To', '')
        references = headers.get('References', '') or headers.get('In-Reply-To', '')
        date_str = headers.get('Date', '')

        # Skip messages FROM us
        if 'charlesaprescottjr@gmail.com' in frm:
            continue

        # Skip Google/automated messages
        skip_domains = ['google.com', 'googlemail.com', 'accounts.google.com']
        if any(d in frm.lower() for d in skip_domains):
            continue

        # Extract from-name and from-email
        from_name = frm.split('<')[0].strip().strip('"')
        from_email = ''
        if '<' in frm and '>' in frm:
            from_email = frm.split('<')[1].split('>')[0].strip()

        # Check if this is a reply (has References/In-Reply-To, or Re: in subject)
        is_reply = bool(references) or subj.lower().startswith('re:')

        # If it's from a foundation domain, flag it
        is_foundation = any(k in frm.lower() for k in FOUNDATION_KEYWORDS) or \
                        any(k in subj.lower() for k in FOUNDATION_KEYWORDS)

        # Determine category
        if is_reply and is_foundation:
            category = 'foundation_reply'
        elif is_reply:
            category = 'reply'
        elif is_foundation:
            category = 'foundation_inquiry'
        else:
            category = 'other'

        entry = {
            'id': msg_id,
            'from': frm,
            'from_name': from_name,
            'from_email': from_email,
            'subject': subj,
            'to': to,
            'date': date_str,
            'category': category,
            'is_reply': is_reply,
            'detected_at': datetime.now().isoformat(),
            'snippet': msg.get('snippet', '')[:150],
        }

        new_responses.append(entry)
        response_log['responses'].append(entry)
        response_log['total'] += 1

    # Save updated log and seen IDs
    if new_ids:
        response_log['last_check'] = datetime.now().isoformat()
        save_response_log(response_log)
        save_seen_ids(new_ids)

    # Also save seen IDs from this check
    return new_responses


def print_responses(responses):
    """Pretty-print new responses."""
    if not responses:
        print("  No new messages found.")
        return

    for r in responses:
        emoji = '🔵' if r['category'] == 'foundation_reply' else \
                '🟢' if r['category'] == 'reply' else \
                '🟡' if r['category'] == 'foundation_inquiry' else '⚪'
        print(f"  {emoji} [{r['category']}]")
        print(f"     From:    {r['from'][:60]}")
        print(f"     Subject: {r['subject'][:70]}")
        print(f"     Snippet: {r['snippet'][:120]}")
        print(f"     Time:    {r['date'][:30]}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Gmail Inbox Monitor")
    parser.add_argument('--watch', action='store_true', help='Watch mode')
    parser.add_argument('--interval', type=int, default=300, help='Poll interval (seconds, default 300)')
    args = parser.parse_args()

    if not os.path.exists(TOKEN_FILE):
        print("ERROR: No gmail_token.json found. Run gmail_api_sender.py first to authenticate.")
        return

    service = get_service()

    if args.watch:
        print(f"📡 Watching inbox every {args.interval}s...")
        print(f"   Log: {LOG_FILE}")
        print()

        seen_ids = load_seen_ids()
        while True:
            responses = check_inbox(service, seen_ids)
            if responses:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {len(responses)} new message(s):")
                print_responses(responses)
            else:
                total_log = load_response_log()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Checked — {total_log['total']} total responses logged")
            sys.stdout.flush()
            time.sleep(args.interval)
    else:
        print("🔍 One-time inbox check...")
        seen_ids = load_seen_ids()
        responses = check_inbox(service, seen_ids)
        print(f"\nFound {len(responses)} new message(s):")
        print_responses(responses)

        total_log = load_response_log()
        print(f"Total responses logged so far: {total_log['total']}")
        print(f"Log file: {LOG_FILE}")


if __name__ == '__main__':
    main()

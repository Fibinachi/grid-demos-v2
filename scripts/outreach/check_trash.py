#!/usr/bin/env python3
"""Check trash for remaining bounces."""
import imaplib, ssl, os

PASS = 'FlorenceFlamingo1!'
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=30)
M.login('charles@columbiataxlawyer.com', PASS)

# Check INBOX.Trash
st, _ = M.select('INBOX.Trash')
if st == 'OK':
    st2, ids = M.search(None, 'ALL')
    all_ids = ids[0].split() if ids[0] else []
    print('Trash messages:', len(all_ids))
    bounces = 0
    for num in all_ids[:200]:
        st3, d = M.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM)])')
        if st3 == 'OK':
            h = d[0][1].decode('utf-8','ignore') if isinstance(d[0][1], bytes) else ''
            if 'mailer-daemon' in h.lower():
                bounces += 1
    print('Bounces in trash (sample):', bounces)
    if len(all_ids) > 200:
        print('(first 200 of', len(all_ids), ')')
else:
    print('Could not select INBOX.Trash')
M.logout()

print()
print('=== BOUNCE LOG ===')
bounce_path = '/home/ubuntu/grantwizard/bounced_emails.txt'
if os.path.exists(bounce_path):
    with open(bounce_path) as f:
        lines = [l.strip() for l in f if l.strip()]
    print('  Total bounced emails logged:', len(lines))
    print('  First 3:', lines[:3])
    print('  Last 3:', lines[-3:])
else:
    print('  No bounce log found')

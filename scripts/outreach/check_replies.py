#!/usr/bin/env python3
"""Check all foundation replies in inbox."""
import imaplib, ssl

ctx = ssl.create_default_context()
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=30)
M.login('charles@columbiataxlawyer.com', 'FlorenceFlamingo1!')
M.select('INBOX')

searches = [
    ('Frick', 'frick.org'),
    ("America's Charities", 'charities.org'),
    ('Robinwood', 'robinwoodfoundation'),
    ('WAM', 'wamfoundation'),
    ('TSAO', 'tsaofoundation'),
    ('Pines', 'pinesfoundation'),
]

for org, search_term in searches:
    status, ids = M.search(None, 'FROM', search_term)
    if ids[0]:
        nums = ids[0].split()
        print('=== %s (%d emails) ===' % (org, len(nums)))
        for num in nums:
            st, d = M.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            h = d[0][1].decode('utf-8','ignore') if isinstance(d[0][1], bytes) else ''
            for line in h.split('\n'):
                l = line.strip()
                if l.lower().startswith('subject:'):
                    print('  Subject:', l[8:].strip()[:100])
                if l.lower().startswith('date:'):
                    print('  Date:', l[5:].strip()[:30])
            print()
    else:
        print('=== %s: No emails found ===' % org)

M.logout()

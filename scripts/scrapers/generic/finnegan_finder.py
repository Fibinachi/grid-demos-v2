#!/usr/bin/env python3
"""Find Finnegan Foundation in inbox."""
import imaplib, ssl

PASS = 'FlorenceFlamingo1!'
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=30)
M.login('charles@columbiataxlawyer.com', PASS)
M.select('INBOX')

st, ids = M.search(None, 'ALL')
all_ids = ids[0].split() if ids[0] else []

print('Searching', len(all_ids), 'messages...')
for num in all_ids:
    st2, d = M.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])')
    if st2 != 'OK':
        continue
    h = d[0][1].decode('utf-8','ignore') if isinstance(d[0][1], bytes) else ''
    hl = h.lower()
    if 'finneg' in hl or 'finnag' in hl or 'finigan' in hl or 'finagin' in hl:
        print('FOUND:')
        for line in h.split('\n'):
            l = line.strip()
            if l.lower().startswith('from:') or l.lower().startswith('subject:'):
                print(' ', l)
        print()

print('Done searching')

M.logout()

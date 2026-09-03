#!/usr/bin/env python3
"""Read Mary Black Foundation reply."""
import imaplib, ssl

PASS = 'FlorenceFlamingo1!'
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=30)
M.login('charles@columbiataxlawyer.com', PASS)
M.select('INBOX')

st, ids = M.search(None, 'FROM', 'maryblackfoundation.org')
if ids[0]:
    num = ids[0].split()[-1]
    st2, d = M.fetch(num, '(BODY[])')
    if st2 == 'OK':
        raw = b''
        for part in d:
            if isinstance(part, tuple):
                raw += part[1] if isinstance(part[1], bytes) else b''
        body = raw.decode('utf-8', 'ignore')
        in_text = False
        for line in body.split('\n'):
            clean = line.strip()
            if 'Content-Type: text/plain' in clean:
                in_text = True
                continue
            if in_text:
                if clean.startswith('--') and 'Boundary' in clean:
                    break
                if clean.startswith('Content-'):
                    continue
                if clean:
                    print(clean)
else:
    print('Not found')

M.logout()

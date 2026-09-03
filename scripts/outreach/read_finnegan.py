#!/usr/bin/env python3
"""Read Finnegan Foundation reply."""
import imaplib, ssl, email
from email import policy

PASS = 'FlorenceFlamingo1!'
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=30)
M.login('charles@columbiataxlawyer.com', PASS)
M.select('INBOX')

st, ids = M.search(None, 'TEXT', 'Finnegan')
if ids[0]:
    for num in ids[0].split():
        st2, d = M.fetch(num, '(BODY[])')
        if st2 == 'OK':
            raw = b''
            for part in d:
                if isinstance(part, tuple):
                    raw += part[1] if isinstance(part[1], bytes) else b''
            msg = email.message_from_bytes(raw, policy=policy.default)
            print('From:', msg['From'])
            print('Subject:', msg['Subject'])
            print('Date:', msg['Date'])
            print()
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        payload = part.get_content()
                        if isinstance(payload, str):
                            print(payload[:2000])
                        break
            else:
                print(msg.get_content()[:2000])
else:
    print('Not found by TEXT search, trying FROM search...')
    st, ids = M.search(None, 'FROM', 'mette.com')
    if ids[0]:
        for num in ids[0].split():
            st2, d = M.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            if st2 == 'OK':
                h = d[0][1].decode('utf-8','ignore') if isinstance(d[0][1], bytes) else ''
                for line in h.split('\n'):
                    l = line.strip()
                    if l.lower().startswith('from:') or l.lower().startswith('subject:'):
                        print(l)

M.logout()

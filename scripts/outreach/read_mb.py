#!/usr/bin/env python3
"""Read Mary Black Foundation reply with MIME decoding."""
import imaplib, ssl, email
from email import policy

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
    print('Not found')
M.logout()

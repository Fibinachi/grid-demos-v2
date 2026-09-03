#!/usr/bin/env python3
"""Read the Garrigan Foundation reply from inbox."""
import imaplib, ssl

ctx = ssl.create_default_context()
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=30)
M.login('charles@columbiataxlawyer.com', 'FlorenceFlamingo1!')
M.select('INBOX')

# Search for Garrigan Foundation
status, ids = M.search(None, 'FROM', 'garrigan.org')
print('Garrigan IDs:', ids)

if ids[0]:
    nums = ids[0].split()
    for num in nums:
        st, d = M.fetch(num, '(BODY[])')
        raw = d[0][1]
        if isinstance(raw, bytes):
            body = raw.decode('utf-8', 'ignore')
        else:
            body = str(raw)
        
        print(f'\n=== GARRIGAN EMAIL (UID {num}) ===')
        # Extract Subject
        for line in body.split('\n'):
            if line.lower().startswith('subject:'):
                print('SUBJECT:', line[8:].strip())
            if line.lower().startswith('from:'):
                print('FROM:', line[5:].strip())
            if line.lower().startswith('date:'):
                print('DATE:', line[5:].strip())
        
        # Extract plain text content
        print('\n--- BODY ---')
        lines = body.split('\n')
        in_plain = False
        for line in lines:
            clean = line.strip()
            if 'Content-Type: text/plain' in clean:
                in_plain = True
                continue
            if in_plain:
                if clean.startswith('--') and 'Boundary' in clean:
                    break
                if clean.startswith('Content-'):
                    continue
                if clean:
                    print(clean)
else:
    print('No Garrigan emails found')

M.logout()

#!/usr/bin/env python3
"""Quick scan of last 150 messages for any human replies."""
import imaplib, ssl

PASS = 'FlorenceFlamingo1!'
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=60)
M.login('charles@columbiataxlawyer.com', PASS)
M.select('INBOX')

st, ids = M.search(None, 'ALL')
all_ids = ids[0].split() if ids[0] else []
total = len(all_ids)

print('Total inbox:', total)
print('Scanning last 150...')
print()

for num in all_ids[-150:]:
    st2, d = M.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
    if st2 != 'OK':
        continue
    h = d[0][1].decode('utf-8','ignore') if isinstance(d[0][1], bytes) else ''
    from_v = subj_v = date_v = ''
    for line in h.split('\n'):
        l = line.strip()
        if l.lower().startswith('from:'): from_v = l[5:].strip()
        if l.lower().startswith('subject:'): subj_v = l[8:].strip()
        if l.lower().startswith('date:'): date_v = l[5:].strip()[:25]

    hl = (from_v + ' ' + subj_v).lower()
    
    # Skip bounces and my own emails
    if any(x in hl for x in ['mailer-daemon', 'amazonses', 'columbiataxlawyer']):
        continue
    
    # Show anything relevant
    is_reply = subj_v.lower().startswith('re:')
    is_foundation = any(kw in from_v.lower() for kw in 
        ['foundation', 'charities', 'grant', 'philanthropy', 'frick', 
         'robinwood', 'pines', 'tsao', 'wam', 'garrigan'])
    
    if is_reply or is_foundation:
        if 'automatic reply' in subj_v.lower():
            rtype = 'AUTO'
        elif 'case#' in subj_v.lower():
            rtype = 'TICKET'
        elif is_reply:
            rtype = 'HUMAN'
        else:
            rtype = 'OTHER'
        
        print(date_v)
        print('  [%s] %s' % (rtype, from_v[:55]))
        print('  %s' % subj_v[:80])
        print()

M.logout()

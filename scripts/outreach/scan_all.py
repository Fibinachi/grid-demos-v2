#!/usr/bin/env python3
"""Scan both inbox AND trash for foundation replies."""
import imaplib, ssl

PASS = 'FlorenceFlamingo1!'
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=60)

def scan_folder(folder):
    """Scan a folder for foundation replies."""
    try:
        st, _ = M.select(folder)
        if st != 'OK':
            return []
    except:
        return []
    
    st, ids = M.search(None, 'ALL')
    if st != 'OK' or not ids[0]:
        return []
    
    results = []
    for num in ids[0].split():
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
        if any(x in hl for x in ['mailer-daemon', 'amazonses', 'columbiataxlawyer']):
            continue
        
        # Show anything foundation-related or with Re:
        is_reply = subj_v.lower().startswith('re:')
        is_foundation = any(kw in from_v.lower() for kw in 
            ['foundation', 'charities', 'grant', 'philanthropy', 'frick',
             'robinwood', 'pines', 'tsao', 'wam', 'garrigan', 'finnegan',
             'finagin', 'alison', 'mette', 'maryblack'])
        
        if is_reply or is_foundation:
            if 'automatic reply' in subj_v.lower():
                rtype = 'AUTO'
            elif 'case#' in subj_v.lower():
                rtype = 'TICKET'
            elif is_reply:
                rtype = 'HUMAN'
            else:
                rtype = 'OTHER'
            results.append((date_v, rtype, from_v[:55], subj_v[:80]))
    
    return results

M.login('charles@columbiataxlawyer.com', PASS)

print('=== INBOX ===')
inbox = scan_folder('INBOX')
for r in sorted(inbox):
    print(f'  {r[0]} [{r[1]}] {r[2]}')
    print(f'  {r[3]}')
    print()

print('\n=== TRASH (INBOX.Trash) ===')
trash = scan_folder('INBOX.Trash')
for r in sorted(trash):
    print(f'  {r[0]} [{r[1]}] {r[2]}')
    print(f'  {r[3]}')
    print()

if not trash:
    print('  (no foundation replies in trash)')

print(f'\nSummary: {len(inbox)} in inbox, {len(trash)} in trash')

M.logout()

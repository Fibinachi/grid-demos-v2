#!/usr/bin/env python3
"""Scan inbox for ALL foundation replies - auto and human."""
import imaplib, ssl, re

PASS = 'FlorenceFlamingo1!'
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=30)
M.login('charles@columbiataxlawyer.com', PASS)
M.select('INBOX')

status, ids = M.search(None, 'ALL')
all_ids = ids[0].split() if ids[0] else []

print('Total inbox messages: %d' % len(all_ids))
print()

replies = []
for num in all_ids:
    st, d = M.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
    if st != 'OK':
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
    
    # Check if this looks like a foundation reply
    is_foundation = any(kw in from_v.lower() for kw in 
        ['foundation', 'charities', 'philanthropy', 'grant', 'frick', 
         'robinwood', 'pines', 'tsao', 'wam', 'garrigan'])
    
    if is_foundation:
        # Classify
        auto = '(AUTO)' if ('automatic reply' in subj_v.lower() or 'out of office' in subj_v.lower()) else ''
        ticket = '(TICKET)' if 'case#' in subj_v.lower() else ''
        human = '(HUMAN)' if subj_v.lower().startswith('re:') and not auto else ''
        
        if not auto and not ticket:
            human = '(HUMAN)'
        
        replies.append((date_v, from_v[:60], subj_v[:80], auto or ticket or human))

# Sort by date
replies.sort(key=lambda x: x[0])

print('=== FOUNDATION REPLIES (%d found) ===' % len(replies))
print()
for date, from_addr, subject, rtype in replies:
    print('  %s' % date)
    print('  %s %s' % (rtype, from_addr))
    print('  %s' % subject)
    print()

# Also scan for any OTHER human replies we might have missed
print('=== OTHER NON-AUTO REPLIES (not bounces, not me) ===')
other_human = []
for num in all_ids:
    st, d = M.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
    if st != 'OK':
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
    if any(x in hl for x in ['foundation', 'charities', 'frick', 'robinwood', 'pines', 'tsao', 'wam', 'garrigan']):
        continue  # already counted above
    
    # Check if it's a human reply (Re: subject)
    if subj_v.lower().startswith('re:'):
        other_human.append((date_v, from_v[:60], subj_v[:80]))

for date, from_addr, subject in sorted(other_human):
    print('  %s' % date)
    print('  %s' % from_addr)
    print('  %s' % subject)
    print()

if not other_human:
    print('  (none)')

M.logout()

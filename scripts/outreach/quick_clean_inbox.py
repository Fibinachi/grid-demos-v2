#!/usr/bin/env python3
"""Quick inbox cleanup - delete bounces and sent copies by FROM search.
Uses batch IMAP operations for speed."""
import imaplib, ssl

PASS = 'FlorenceFlamingo1!'
ctx = ssl.create_default_context()
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=120)
M.login('charles@columbiataxlawyer.com', PASS)
M.select('INBOX')

def delete_by_from(search_term, label):
    """Search for messages FROM a sender and delete them in one batch."""
    status, ids = M.search(None, 'FROM', search_term)
    if status != 'OK' or not ids[0]:
        print('%s: 0 found' % label)
        return 0
    all_ids = ids[0].split()
    print('%s: %d found, deleting...' % (label, len(all_ids)))
    # IMAP STORE takes comma-separated IDs
    msg_set = ','.join(b.decode() if isinstance(b, bytes) else str(b) for b in all_ids)
    M.store(msg_set, '+FLAGS', '\\Deleted')
    print('  Deleted %d' % len(all_ids))
    return len(all_ids)

total = 0
total += delete_by_from('mailer-daemon', 'Mailer-daemon bounces')
total += delete_by_from('postmaster', 'Postmaster bounces')
total += delete_by_from('amazonses.com', 'SES notifications')

# Sent copies - from my own domain address
status, ids = M.search(None, 'FROM', 'charles@columbiataxlawyer.com')
if status == 'OK' and ids[0]:
    sent_ids = ids[0].split()
    print('Sent copies: %d found, deleting...' % len(sent_ids))
    msg_set = ','.join(b.decode() if isinstance(b, bytes) else str(b) for b in sent_ids)
    M.store(msg_set, '+FLAGS', '\\Deleted')
    total += len(sent_ids)
    print('  Deleted %d' % len(sent_ids))
else:
    print('Sent copies: 0 found')

# Expunge
M.expunge()
print('\nTotal deleted: %d' % total)

# Count remaining
status, ids = M.search(None, 'ALL')
remaining = ids[0].split() if ids[0] else []
print('Remaining in inbox: %d messages' % len(remaining))

M.logout()

"""Check SES bounce format - find how bounced addresses appear"""
import imaplib, re

P = 'FlorenceFlamingo1!'
M = imaplib.IMAP4_SSL('imap.hostinger.com', 993, timeout=30)
M.login('charles@columbiataxlawyer.com', P)
M.select('INBOX')
status, ids = M.search(None, 'ALL')
all_ids = ids[0].split() if ids[0] else []

count = 0
for num in reversed(all_ids):
    st, d = M.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])')
    h = d[0][1].decode('utf-8','ignore') if isinstance(d[0][1], bytes) else ''
    if 'amazonses' in h.lower() and 'delivery' in h.lower() and count < 3:
        count += 1
        st2, d2 = M.fetch(num, '(BODY[])')
        body = d2[0][1].decode('utf-8','ignore') if isinstance(d2[0][1], bytes) else ''
        
        print('=== Bounce %d ===' % count)
        # Search for the content-type boundary to find the DSN
        # Look for email addresses that are NOT amazon/columbiataxlawyer
        all_emails = re.findall(r'[\w.+-]+@[\w.-]+\.\w{2,4}', body)
        real_emails = [e for e in all_emails if 'columbiataxlawyer' not in e and 'amazonses' not in e and 'mailer-daemon' not in e]
        print('  Emails found in body: %s' % real_emails)
        
        # Search for lines around "failed" or "status"
        for line in body.split('\n'):
            ll = line.strip().lower()
            if any(x in ll for x in ['action:', 'status:', 'diagnostic', 'original-recipient', 'final-recipient', 'remote-mta']):
                print('  %s' % line.strip()[:150])
        print()

M.logout()

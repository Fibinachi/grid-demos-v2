#!/usr/bin/env python3
"""
Deduplicate foundation contact list by unique email address.
Each email gets at most ONE email sent to it.
"""
import csv
from collections import defaultdict

CSV = '/home/ubuntu/grantwizard/enriched_contacts_verified.csv'
OUT = '/home/ubuntu/grantwizard/enriched_contacts_deduped.csv'

with open(CSV) as f:
    rows = list(csv.DictReader(f))

print('Total rows:', len(rows))

by_email = defaultdict(list)
no_email = []
for r in rows:
    email = r.get('EMAIL', '').strip().lower()
    if email:
        by_email[email].append(r)
    else:
        no_email.append(r)

print('Unique emails:', len(by_email))
print('No email:', len(no_email))

deduped = []
merged = 0
multi = 0

for email, group in sorted(by_email.items()):
    if len(group) == 1:
        deduped.append(group[0])
    else:
        multi += 1
        merged += len(group) - 1
        # Score: prefer verified + enriched + larger assets
        def score(r):
            s = 0
            if r.get('EMAIL_VERIFIED', '') == 'true':
                s += 10
            if r.get('ENRICHED_EMAIL', ''):
                s += 5
            try:
                s += min(float(r.get('ASSET_AMT', 0) or 0) / 1000000, 10)
            except:
                pass
            return s
        group.sort(key=score, reverse=True)
        deduped.append(group[0])

print()
print('=== RESULTS ===')
print(f'Email groups merged: {multi}')
print(f'Rows deduplicated: {merged}')
print(f'For sending: {len(deduped)}')
print()

# Show biggest merges
print('=== BIGGEST MERGES (10+ entities sharing one email) ===')
for email, group in sorted(by_email.items(), key=lambda x: -len(x[1])):
    if len(group) >= 10:
        names = [r['NAME'].strip()[:35] for r in group]
        print(f'  {len(group)}x {email}')
        for n in names[:4]:
            print(f'       {n}')
        if len(names) > 4:
            print(f'       ... and {len(names)-4} more')

with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(deduped)

print(f'\nOutput: {OUT}')
print(f'Before: {len(rows)} -> After: {len(deduped)} ({merged} merged)')

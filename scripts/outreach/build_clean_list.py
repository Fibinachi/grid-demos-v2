#!/usr/bin/env python3
"""Strip placeholder emails and save clean send list."""
import csv, shutil

PLACEHOLDER_KW = ['fam.com','privatefoundation','educationfoundation.com',
                  'foundation.org','foundation.com','familyfoundation','iii.org']

with open('/home/ubuntu/grantwizard/enriched_contacts_deduped.csv') as f:
    rows = list(csv.DictReader(f))

good = []
removed = 0
for r in rows:
    email = r.get('EMAIL','').strip().lower()
    if any(kw in email for kw in PLACEHOLDER_KW):
        removed += 1
    else:
        good.append(r)

print('Deduped total:', len(rows))
print('Removed placeholders:', removed)
print('Clean send list:', len(good))

out = '/home/ubuntu/grantwizard/enriched_contacts_clean.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(good)

shutil.copy(out, '/home/ubuntu/grantwizard/enriched_contacts.csv')
print('Saved. Sender ready with', len(good), 'foundations.')

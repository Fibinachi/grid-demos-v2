#!/usr/bin/env python3
"""Check what the duplicated foundation emails actually are."""
import csv
from collections import Counter

with open('/home/ubuntu/grantwizard/enriched_contacts_verified.csv') as f:
    rows = list(csv.DictReader(f))

emails = [r.get('EMAIL','').strip().lower() for r in rows if r.get('EMAIL','').strip()]
email_counts = Counter(emails)

print('Total with email:', len(emails))
print('Unique emails:', len(set(emails)))
print('Duplicated emails:', sum(1 for e, c in email_counts.items() if c > 1))

print('\n=== TOP 30 MOST COMMON DUPLICATED EMAILS ===')
for email, count in email_counts.most_common(30):
    if count > 1:
        names = [r['NAME'].strip()[:45] for r in rows if r.get('EMAIL','').strip().lower() == email]
        print(f'  {count:3d}x {email}')
        for n in names[:3]:
            print(f'       {n}')
        if len(names) > 3:
            print(f'       ... and {len(names)-3} more')
        print()

# Classify the duplicates
print('=== ANALYSIS ===')
generic_domain_count = 0
same_domain_count = 0
empty_or_placeholder = 0

for email, count in email_counts.most_common():
    if count <= 1:
        continue
    local, domain = email.split('@')
    # Foundations sharing same generic email like info@phillips.com - these are different
    # state-level entities of the same family foundation using the same contact
    names = [r['NAME'].strip() for r in rows if r.get('EMAIL','').strip().lower() == email]
    domains_from_names = set()
    for n in names:
        words = n.lower().split()
        for w in words:
            if w in domain.replace('.com','').replace('.org','').replace('.net',''):
                domains_from_names.add(w)
    
    # Check if the domain matches the foundation name
    name_words = set()
    for n in names:
        for w in n.lower().replace(' foundation','').replace(' inc','').replace(',','').split():
            if len(w) > 3:
                name_words.add(w)
    
    domain_core = domain.split('.')[0]
    if domain_core in name_words or any(w in domain_core for w in name_words):
        same_domain_count += 1
        if count > 2:
            print(f'  SAME DOMAIN: {email} ({count}x) - multiple {domain_core} entities')
    else:
        generic_domain_count += 1
        if count > 2 and count < 20:
            print(f'  GENERIC: {email} ({count}x) - names: {[n[:30] for n in names[:3]]}')

print(f'\nSame-domain dupes (info@foundationname.org): {same_domain_count}')
print(f'Cross-domain dupes (different foundations sharing email): {generic_domain_count}')

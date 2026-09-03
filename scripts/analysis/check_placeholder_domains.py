#!/usr/bin/env python3
"""Check for placeholder/guessed emails in the deduped list."""
import csv
from collections import Counter

with open('/home/ubuntu/grantwizard/enriched_contacts_deduped.csv') as f:
    rows = list(csv.DictReader(f))

emails = [r.get('EMAIL','').strip().lower() for r in rows if r.get('EMAIL','').strip()]
domains = Counter(e.split('@')[1] for e in emails)

print('=== SUSPICIOUS GUESSED DOMAINS ===')
suspicious = ['fam.com', 'privatefoundation.org', 'educationfoundation.com',
              'johnfoundation.org', 'martinfoundation.org', 'thomasfoundation.org',
              'foundation.org', 'familyfoundation.org', 'familyfoundation.com',
              'iii.org']
for d in suspicious:
    count = domains.get(d, 0)
    if count > 0:
        sample = [r['NAME'].strip()[:40] for r in rows 
                  if r.get('EMAIL','').strip().lower().endswith('@' + d)]
        print(f'\n{d}: {count} foundations')
        for s in sample[:3]:
            print(f'  e.g. {s}')

print('\n=== ALL DOMAINS WITH 10+ FOUNDATIONS ===')
for d, c in domains.most_common(50):
    if c >= 10:
        print(f'  {c:4d}x {d}')

total_unique = len(domains)
single_only = sum(1 for c in domains.values() if c == 1)
print(f'\nTotal unique domains: {total_unique}')
print(f'Domains with 1 foundation only: {single_only}')
print(f'Domains with 2+ foundations: {total_unique - single_only}')

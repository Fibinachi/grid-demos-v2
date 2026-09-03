#!/usr/bin/env python3
"""Check which tier1 foundations need email enrichment."""
import csv

tier1 = {}
with open('/home/ubuntu/grantwizard/foundations_tier1_10m_plus.csv') as f:
    for r in csv.DictReader(f):
        tier1[r['EIN'].strip()] = r

enriched = {}
with open('/home/ubuntu/grantwizard/enriched_contacts_clean.csv') as f:
    for r in csv.DictReader(f):
        enriched[r['EIN'].strip()] = r

matched = 0
good = 0
placeholder = 0
no_email = 0
missing = 0

for ein, r in tier1.items():
    if ein in enriched:
        matched += 1
        email = enriched[ein].get('EMAIL','').strip()
        if not email:
            no_email += 1
        elif any(kw in email.lower() for kw in ['fam.com','privatefoundation','educationfoundation.com']):
            placeholder += 1
        else:
            good += 1
    else:
        missing += 1

print('Tier1 foundations:', len(tier1))
print('In enriched list:', matched)
print('  With good email:', good)
print('  With placeholder:', placeholder)
print('  No email:', no_email)
print('Not in enriched list:', missing)
print()
print('Need enrichment:', placeholder + no_email + missing)

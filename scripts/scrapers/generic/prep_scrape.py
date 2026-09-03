#!/usr/bin/env python3
"""Check remaining foundations that need real emails and scrape."""
import csv

PLACEHOLDER_KW = ['fam.com','privatefoundation','educationfoundation.com',
                  'foundation.org','foundation.com','familyfoundation','iii.org']

with open('/home/ubuntu/grantwizard/enriched_contacts_verified_backup.csv') as f:
    rows = list(csv.DictReader(f))

# Load deduped email whitelist
dedup_emails = set()
with open('/home/ubuntu/grantwizard/enriched_contacts_deduped.csv') as f:
    for r in csv.DictReader(f):
        dedup_emails.add(r.get('EMAIL','').strip().lower())

print('=== FOUNDATIONS NEEDING REAL EMAILS ===')
need_scrape = []
for r in rows:
    email = r.get('EMAIL','').strip().lower()
    domain = r.get('DOMAIN','').strip().lower()
    
    needs = False
    if not email:
        needs = True
    elif any(kw in email for kw in PLACEHOLDER_KW):
        needs = True
    elif email not in dedup_emails:
        needs = True
    
    if needs:
        need_scrape.append(r)

print(f'Total needing real emails: {len(need_scrape)}')
has_domain = sum(1 for r in need_scrape if r.get('DOMAIN','').strip())
has_website = sum(1 for r in need_scrape if r.get('WEBSITE','').strip())
no_domain = len(need_scrape) - has_domain
print(f'  With DOMAIN: {has_domain}')
print(f'  With WEBSITE: {has_website}')
print(f'  No domain: {no_domain}')

# Create a CSV of domains to scrape
out = '/home/ubuntu/grantwizard/foundations_to_scrape.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['EIN','NAME','DOMAIN','CURRENT_EMAIL'])
    for r in need_scrape:
        domain = r.get('DOMAIN','').strip()
        if domain:
            w.writerow([r['EIN'], r['NAME'], domain, r.get('EMAIL','').strip()])
        else:
            # Try to extract from email
            email = r.get('EMAIL','').strip()
            if '@' in email:
                domain = email.split('@')[1]
            else:
                domain = ''
            w.writerow([r['EIN'], r['NAME'], domain, email])

print(f'\nSaved {out}')

# Count with domains
with_domain = sum(1 for r in need_scrape if r.get('DOMAIN','').strip())
print(f'With domains to scrape: {with_domain}')

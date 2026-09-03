#!/usr/bin/env python3
"""Build tier1 foundation scrape input."""
import csv

# Gather tier1 domains that need scraping
tier1_domains = {}  # domain -> (ein, name)
with open('/home/ubuntu/grantwizard/foundations_tier1_10m_plus.csv') as f:
    for r in csv.DictReader(f):
        domain = r.get('GUESSED_DOMAIN','').strip().lower()
        if domain:
            tier1_domains[domain] = (r['EIN'].strip(), r['NAME'].strip())

# Already in clean list (don't need scraping)
clean_eins = set()
with open('/home/ubuntu/grantwizard/enriched_contacts_clean.csv') as f:
    for r in csv.DictReader(f):
        clean_eins.add(r['EIN'].strip())

# Already being scraped
scraping_domains = set()
with open('/home/ubuntu/grantwizard/foundations_to_scrape_full.csv') as f:
    for r in csv.DictReader(f):
        d = r.get('DOMAIN','').strip().lower()
        if d:
            scraping_domains.add(d)

# Tier1 domains that need scraping (not in clean list, not already being scraped)
need_scrape = []
already_covered = 0
for domain, (ein, name) in tier1_domains.items():
    if ein in clean_eins:
        already_covered += 1
    elif domain in scraping_domains:
        already_covered += 1
    else:
        need_scrape.append((ein, name, domain))

print('Tier1 total domains:', len(tier1_domains))
print('Already have email/being scraped:', already_covered)
print('Need new scraping:', len(need_scrape))

# Write tier1 scrape input
out = '/home/ubuntu/grantwizard/tier1_to_scrape.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['EIN','NAME','CITY','STATE','ASSET_AMT','NTEE_CD','EMAIL','SOURCE','DOMAIN','SCRAPED_EMAIL','SOURCE_URL'])
    for ein, name, domain in need_scrape:
        w.writerow([ein, name, '', '', '', '', '', 'dns_info', domain, '', ''])

print(f'Saved: {out}')

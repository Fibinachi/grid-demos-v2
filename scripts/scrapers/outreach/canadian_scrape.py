#!/usr/bin/env python3
"""Build a scrape input CSV for Canadian funders and send to EC2 instances."""
import csv, os, re

base = os.path.dirname(os.path.abspath(__file__))

# Load Canadian funders
with open(os.path.join(base, 'canadian_funding_sources.csv')) as f:
    funders = list(csv.DictReader(f))

# Build scrape input - those with websites but no email
scrape_rows = []
for r in funders:
    url = r.get('url', '').strip()
    name = r.get('name', '').strip()
    if not url:
        continue
    
    domain = re.sub(r'^https?://', '', url).split('/')[0]
    
    scrape_rows.append({
        'EIN': '',  # Canadian orgs don't have EINs
        'NAME': name,
        'CITY': '',
        'STATE': '',
        'ASSET_AMT': '0',
        'NTEE_CD': '',
        'EMAIL': '',
        'SOURCE': 'dns_info',
        'DOMAIN': domain,
        'SCRAPED_EMAIL': '',
        'SOURCE_URL': url,
    })

print(f"Canadian funders with websites needing email scraping: {len(scrape_rows)}")

# Split into 2 batches for the smaller EC2 instances
half = len(scrape_rows) // 2
batch1 = scrape_rows[:half]
batch2 = scrape_rows[half:]

for i, batch in enumerate([batch1, batch2], 1):
    path = os.path.join(base, f'canadian_scrape_tier{i}.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['EIN','NAME','CITY','STATE','ASSET_AMT',
                                           'NTEE_CD','EMAIL','SOURCE','DOMAIN',
                                           'SCRAPED_EMAIL','SOURCE_URL'])
        w.writeheader()
        w.writerows(batch)
    print(f"  Batch {i}: {len(batch)} -> {path}")

print(f"\nUpload and launch on tier1 (13.58.64.223) and tier2 (18.219.220.68)")

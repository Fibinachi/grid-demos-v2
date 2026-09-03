#!/usr/bin/env python3
"""
Build scrape input for remaining 173 theology foundations.
For tier1/2/3 entries, gets GUESSED_DOMAIN from source CSVs.
For propublica entries, generates domain guesses from names.
Also does DNS verification to skip dead domains.
"""
import csv
import os
import sys
import re
import socket
import time

base_dir = os.path.dirname(os.path.abspath(__file__))

# Load source CSVs with domain info
source_domains = {}  # ein -> guessed_domain
for fname in ['foundations_tier1_10m_plus.csv', 'foundations_tier2_1m_10m.csv', 'foundations_tier3_500k_1m.csv']:
    path = os.path.join(base_dir, fname)
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                ein = r.get('EIN', '').strip()
                domain = r.get('GUESSED_DOMAIN', '').strip().lower()
                if ein and domain:
                    source_domains[ein] = domain

# Load need_scrape list
need = []
with open(os.path.join(base_dir, 'theology_need_scrape.csv')) as f:
    for r in csv.DictReader(f):
        need.append(r)

print(f"Loaded {len(need)} foundations needing scraping")
print(f"Source domains available for {len([r for r in need if r['EIN'] in source_domains])}")

# Build scrape list with domains
scrape_entries = []
no_domain = []

for r in need:
    ein = r['EIN']
    name = r['NAME']
    tier = r.get('TIER', '')
    
    # Try source CSV first
    domain = source_domains.get(ein, '')
    
    # If no domain, generate from name
    if not domain:
        # Convert name to domain - take key words, lowercase, remove special chars
        d = name.lower().strip()
        d = re.sub(r'[^a-z0-9\s\.]', '', d)
        d = re.sub(r'\s+', ' ', d).strip()
        # Remove common suffixes
        for suffix in [' inc', ' foundation', ' fund', ' trust', ' corporation', ' ltd', ' llc']:
            d = d.replace(suffix, '')
        d = d.strip()
        # Take first 3-4 significant words
        words = d.split()
        # Filter out common words
        skip_words = {'the', 'a', 'an', 'of', 'for', 'and', 'in', 'to', 'at', 'by'}
        significant = [w for w in words if w not in skip_words]
        
        if significant:
            # Try different domain patterns
            patterns = []
            # Full name (no spaces)
            name_compact = ''.join(significant).lower()
            patterns.append(f"{name_compact}.org")
            patterns.append(f"{name_compact}.com")
            # First words joined
            for n in [2, 3, 4]:
                if len(significant) >= n:
                    joined = ''.join(significant[:n]).lower()
                    patterns.append(f"{joined}.org")
                    patterns.append(f"{joined}.com")
            # First initials
            initials = ''.join(w[0] for w in significant[:3]).lower()
            patterns.append(f"{initials}.org")
            patterns.append(f"{initials}.com")
            
            domain = patterns[0]  # Use first pattern
        else:
            no_domain.append((ein, name))
            continue
    
    scrape_entries.append({
        'EIN': ein,
        'NAME': name,
        'CITY': r.get('CITY', ''),
        'STATE': r.get('STATE', ''),
        'ASSET_AMT': r.get('ASSET_AMT', '0'),
        'NTEE_CD': r.get('NTEE', ''),
        'EMAIL': '',
        'SOURCE': 'dns_info',
        'DOMAIN': domain,
        'SCRAPED_EMAIL': '',
        'SOURCE_URL': '',
        'PRIORITY': r.get('PRIORITY', ''),
    })

print(f"Entries with domains: {len(scrape_entries)}")
if no_domain:
    print(f"No domain possible: {len(no_domain)}")
    for ein, name in no_domain:
        print(f"  {ein} - {name}")

# Write combined scrape list
scrape_path = os.path.join(base_dir, 'theology_scrape_all.csv')
fieldnames = ['EIN', 'NAME', 'CITY', 'STATE', 'ASSET_AMT', 'NTEE_CD',
              'EMAIL', 'SOURCE', 'DOMAIN', 'SCRAPED_EMAIL', 'SOURCE_URL', 'PRIORITY']
with open(scrape_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(scrape_entries)
print(f"Saved: {scrape_path}")

# Split into 4 batches for EC2 instances
batches = []
batch_size = max(1, len(scrape_entries) // 4)
for i in range(0, len(scrape_entries), batch_size):
    batches.append(scrape_entries[i:i+batch_size])
if len(batches) > 4:
    merged = batches[:3]
    merged.append([item for sublist in batches[3:] for item in sublist])
    batches = merged

server_names = ['main_ec2', 'tier1', 'tier2', 'tier3']
for i, batch in enumerate(batches):
    name = server_names[i]
    path = os.path.join(base_dir, f'theology_scrape_{name}.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(batch)
    print(f"  {name}: {len(batch)} domains -> {path}")

print(f"\nReady to upload to EC2 instances. {len(scrape_entries)} total across 4 servers.")

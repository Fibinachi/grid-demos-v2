#!/usr/bin/env python3
"""
Foundation Staff Email Scraper
===============================
For each foundation in the final list, visits their website and finds
real staff/contact email addresses (not generic info@).

Looks for:
- /team, /staff, /about, /contact, /board, /people pages
- Extracts all email addresses found
- Prefers named individuals over generic addresses
"""
import csv
import os
import re
import time
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))

# Common staff/contact pages to try
STAFF_PATHS = [
    '/team', '/staff', '/about', '/about-us', '/about/team',
    '/contact', '/contact-us', '/board', '/board-of-directors',
    '/people', '/our-team', '/our-staff', '/leadership',
    '/foundation/team', '/foundation/staff',
    '/about/leadership', '/about/staff',
    '/grantmaking', '/grants', '/programs',
    '/who-we-are', '/our-people',
    '/',  # homepage last
]

# Generic email prefixes to skip
GENERIC_PREFIXES = [
    'info@', 'contact@', 'hello@', 'admin@', 'webmaster@',
    'support@', 'mail@', 'office@', 'email@', 'inquiries@',
    'ask@', 'media@', 'press@', 'donate@', 'jobs@',
    'hr@', 'careers@', 'volunteer@', 'spam@', 'noreply@',
    'feedback@', 'newsletter@', 'subscribe@', 'bounce@',
]

# Load the final list to get EINs
final_path = os.path.join(base_dir, 'theology_final_list.csv')
with open(final_path) as f:
    final_rows = list(csv.DictReader(f))

# Get EINs from the 529 send list
send_path = os.path.join(base_dir, 'theology_gmail_send.csv')
send_eins = set()
with open(send_path) as f:
    for r in csv.DictReader(f):
        send_eins.add(r['EIN'].strip())

# Load original tier data for guessed domains
domain_map = {}  # ein -> guessed_domain
for tier_file in ['foundations_tier1_10m_plus.csv', 'foundations_tier2_1m_10m.csv',
                   'foundations_tier3_500k_1m.csv']:
    path = os.path.join(base_dir, tier_file)
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                ein = r.get('EIN', '').strip()
                domain = r.get('GUESSED_DOMAIN', '').strip().lower()
                if ein and domain and ein in send_eins:
                    domain_map[ein] = domain

# Also add entries from the final list itself (which has NAME for domain guessing)
name_domain_map = {}
for r in final_rows:
    if r['EIN'] in send_eins and r['EIN'] not in domain_map:
        name = r['NAME']
        # Generate domain guess from name
        d = name.lower().strip()
        d = re.sub(r'[^a-z0-9\s]', '', d)
        words = d.split()
        skip = {'the', 'a', 'an', 'of', 'for', 'and', 'in', 'to', 'at', 'by', 'inc'}
        sig = [w for w in words if w not in skip]
        if sig:
            guessed = ''.join(sig) + '.org'
            name_domain_map[r['EIN']] = guessed

print(f"Foundations to scrape: {len(send_eins)}")
print(f"With tier domains: {len(domain_map)}")
print(f"With guessed domains: {len(name_domain_map)}")

# Build scrape list
scrape_list = []
for r in final_rows:
    ein = r['EIN']
    if ein not in send_eins:
        continue
    
    domain = domain_map.get(ein) or name_domain_map.get(ein, '')
    if not domain:
        continue
    
    scrape_list.append({
        'EIN': ein,
        'NAME': r['NAME'],
        'CITY': r.get('CITY', ''),
        'STATE': r.get('STATE', ''),
        'NTEE': r.get('NTEE', ''),
        'DOMAIN': domain,
    })

print(f"Scrape list built: {len(scrape_list)}")

# Write scrape input
scrape_csv = os.path.join(base_dir, 'staff_scrape_input.csv')
with open(scrape_csv, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['EIN','NAME','CITY','STATE','NTEE','DOMAIN'])
    w.writeheader()
    w.writerows(scrape_list)
print(f"Saved: {scrape_csv}")

# Split into 4 batches for EC2 fleet
batches = []
batch_size = max(1, len(scrape_list) // 4)
for i in range(0, len(scrape_list), batch_size):
    batches.append(scrape_list[i:i+batch_size])
if len(batches) > 4:
    merged = batches[:3] + [sum(batches[3:], [])]
    batches = merged

servers = ['main_ec2', 'tier1', 'tier2', 'tier3']
for i, batch in enumerate(batches):
    path = os.path.join(base_dir, f'staff_scrape_{servers[i]}.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['EIN','NAME','CITY','STATE','NTEE','DOMAIN'])
        w.writeheader()
        w.writerows(batch)
    print(f"  {servers[i]}: {len(batch)} domains -> {path}")

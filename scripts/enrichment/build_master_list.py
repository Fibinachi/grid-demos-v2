#!/usr/bin/env python3
"""
Build the final master list incorporating:
1. Classified theology priority foundations (HIGH + MEDIUM)
2. ProPublica theology search results
3. Cross-reference with existing enriched contacts
4. Outputs the master theology-focused foundation list
"""

import csv
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))

def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

print("=" * 70)
print("  BUILDING MASTER THEOLOGY FOUNDATIONS LIST")
print("=" * 70)

# 1. Load classified tier results
tier1 = load_csv(os.path.join(base_dir, 'classified_tier1.csv'))
tier2 = load_csv(os.path.join(base_dir, 'classified_tier2.csv'))
tier3 = load_csv(os.path.join(base_dir, 'classified_tier3.csv'))
propublica = load_csv(os.path.join(base_dir, 'classified_theology.csv'))

print(f"\nLoaded classifications:")
print(f"  Tier1 ($10M+):     {len(tier1)} ({len([r for r in tier1 if r['priority']=='HIGH'])} HIGH, {len([r for r in tier1 if r['priority']=='MEDIUM'])} MEDIUM)")
print(f"  Tier2 ($1M-$10M):  {len(tier2)} ({len([r for r in tier2 if r['priority']=='HIGH'])} HIGH, {len([r for r in tier2 if r['priority']=='MEDIUM'])} MEDIUM)")
print(f"  Tier3 ($500K-$1M): {len(tier3)} ({len([r for r in tier3 if r['priority']=='HIGH'])} HIGH, {len([r for r in tier3 if r['priority']=='MEDIUM'])} MEDIUM)")
print(f"  ProPublica:        {len(propublica)} ({len([r for r in propublica if r['priority']=='HIGH'])} HIGH)")

# 2. Load existing enriched contacts to cross-reference
enriched = load_csv(os.path.join(base_dir, 'enriched_contacts.csv'))
clean = load_csv(os.path.join(base_dir, 'enriched_contacts_clean.csv'))

enriched_eins = {r['EIN'].strip() for r in enriched if r.get('EMAIL','').strip() not in ('', 'dns_info')}
clean_eins = {r['EIN'].strip() for r in clean}

print(f"\nExisting data:")
print(f"  Enriched contacts: {len(enriched)} ({len(enriched_eins)} with real emails)")
print(f"  Clean list: {len(clean)} EINs")

# 3. Build master list from HIGH + MEDIUM across all tiers
master = []
seen_eins = set()

for tier_label, rows in [('tier1', tier1), ('tier2', tier2), ('tier3', tier3)]:
    for r in rows:
        if r['priority'] not in ('HIGH', 'MEDIUM'):
            continue
        ein = r['ein']
        if ein in seen_eins:
            continue
        seen_eins.add(ein)
        
        has_email = ein in enriched_eins or ein in clean_eins
        
        master.append({
            'EIN': ein,
            'NAME': r['name'],
            'CITY': r.get('city', ''),
            'STATE': r.get('state', ''),
            'NTEE': r.get('ntee_code', ''),
            'ASSET_AMT': r.get('asset_amt', '0'),
            'THEOLOGY_SCORE': r.get('theology_score', '0'),
            'PRIORITY': r['priority'],
            'TIER': tier_label,
            'HAS_EMAIL': 'YES' if has_email else 'NEED SCRAPING',
            'SIGNALS': r.get('signals', ''),
        })

# Add ProPublica results (theology-specific orgs)
for r in propublica:
    ein = r['ein']
    if ein in seen_eins:
        continue
    seen_eins.add(ein)
    
    has_email = ein in enriched_eins or ein in clean_eins
    
    master.append({
        'EIN': ein,
        'NAME': r['name'],
        'CITY': r.get('city', ''),
        'STATE': r.get('state', ''),
        'NTEE': r.get('ntee_code', ''),
        'ASSET_AMT': r.get('asset_amt', '0'),
        'THEOLOGY_SCORE': r.get('theology_score', '0'),
        'PRIORITY': r['priority'],
        'TIER': 'propublica',
        'HAS_EMAIL': 'YES' if has_email else 'NEED SCRAPING',
        'SIGNALS': r.get('signals', ''),
    })

# Sort by score descending
master.sort(key=lambda x: -int(x['THEOLOGY_SCORE']))

print(f"\n{'=' * 70}")
print(f"MASTER LIST SUMMARY")
print(f"{'=' * 70}")
print(f"Total unique theology-focused foundations: {len(master)}")
print(f"HIGH priority: {len([r for r in master if r['PRIORITY']=='HIGH'])}")
print(f"MEDIUM priority: {len([r for r in master if r['PRIORITY']=='MEDIUM'])}")
print(f"\nEmail status:")
print(f"  Already have email: {len([r for r in master if r['HAS_EMAIL']=='YES'])}")
print(f"  Need scraping: {len([r for r in master if r['HAS_EMAIL']=='NEED SCRAPING'])}")

# 4. Write master list
master_path = os.path.join(base_dir, 'theology_master_list.csv')
fieldnames = ['EIN', 'NAME', 'CITY', 'STATE', 'NTEE', 'ASSET_AMT',
              'THEOLOGY_SCORE', 'PRIORITY', 'TIER', 'HAS_EMAIL', 'SIGNALS']
with open(master_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(master)

print(f"\nSaved: {master_path}")

# 5. Write HIGH priority send list (ready-to-send subset with emails)
high_with_email = [r for r in master if r['PRIORITY'] == 'HIGH' and r['HAS_EMAIL'] == 'YES']
high_path = os.path.join(base_dir, 'theology_priority_send.csv')
with open(high_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(high_with_email)
print(f"Ready-to-send HIGH priority: {len(high_with_email)} -> {high_path}")

# 6. Write NEED SCRAPING subset
need_scrape = [r for r in master if r['HAS_EMAIL'] == 'NEED SCRAPING']
scrape_path = os.path.join(base_dir, 'theology_need_scrape.csv')
scrape_fields = ['EIN', 'NAME', 'CITY', 'STATE', 'NTEE',
                 'ASSET_AMT', 'THEOLOGY_SCORE', 'PRIORITY',
                 'TIER', 'SIGNALS', 'HAS_EMAIL']
with open(scrape_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=scrape_fields)
    w.writeheader()
    for r in need_scrape:
        w.writerow({k: r.get(k, '') for k in scrape_fields})
print(f"Need email scraping: {len(need_scrape)} -> {scrape_path}")

# 7. Print top 30
print(f"\n{'=' * 70}")
print(f"TOP 30 THEOLOGY FOUNDATIONS (by score)")
print(f"{'=' * 70}")
for r in master[:30]:
    email_status = '✓' if r['HAS_EMAIL'] == 'YES' else '✗'
    print(f"  [{r['PRIORITY']:6s}] [{r['THEOLOGY_SCORE']:>3s}] {email_status} {r['NAME'][:55]:55s} ({r['CITY']}, {r['STATE']}) [{r['NTEE']}]")

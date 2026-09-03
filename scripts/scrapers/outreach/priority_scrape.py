#!/usr/bin/env python3
"""
Build priority scrape lists from classified foundations.
Combines HIGH + MEDIUM from all tiers, cross-references against existing
enriched contacts, splits into batches for each EC2 instance.
"""
import csv
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))

# Load all classified files
tiers = {
    'tier1': {'classified': 'classified_tier1.csv', 'source': 'foundations_tier1_10m_plus.csv'},
    'tier2': {'classified': 'classified_tier2.csv', 'source': 'foundations_tier2_1m_10m.csv'},
    'tier3': {'classified': 'classified_tier3.csv', 'source': 'foundations_tier3_500k_1m.csv'},
}

# Load existing enriched contacts to skip
enriched_eins = set()
enriched_csv = os.path.join(base_dir, 'enriched_contacts.csv')
if os.path.exists(enriched_csv):
    with open(enriched_csv) as f:
        for r in csv.DictReader(f):
            ein = r.get('EIN', '').strip()
            email = r.get('EMAIL', '').strip()
            if ein and email and email not in ('', 'dns_info'):
                enriched_eins.add(ein)

# Also load clean list
clean_eins = set()
clean_csv = os.path.join(base_dir, 'enriched_contacts_clean.csv')
if os.path.exists(clean_csv):
    with open(clean_csv) as f:
        for r in csv.DictReader(f):
            ein = r.get('EIN', '').strip()
            if ein:
                clean_eins.add(ein)

print(f"Already enriched: {len(enriched_eins)} EINs")
print(f"Clean list: {len(clean_eins)} EINs")

all_priority = []

for tier_name, files in tiers.items():
    classified_path = os.path.join(base_dir, files['classified'])
    source_path = os.path.join(base_dir, files['source'])
    
    # Load classified
    classified = {}
    with open(classified_path) as f:
        for r in csv.DictReader(f):
            classified[r['ein']] = r
    
    # Load source (for guessed domains)
    source_data = {}
    with open(source_path) as f:
        for r in csv.DictReader(f):
            source_data[r['EIN'].strip()] = r
    
    # Get HIGH + MEDIUM
    high_med = [r for r in classified.values() if r['priority'] in ('HIGH', 'MEDIUM')]
    
    skipped_enriched = 0
    skipped_clean = 0
    for r in high_med:
        ein = r['ein']
        domain = source_data.get(ein, {}).get('GUESSED_DOMAIN', '').strip().lower()
        
        if not domain:
            continue
        
        # Skip if already enriched
        if ein in enriched_eins:
            skipped_enriched += 1
            continue
        if ein in clean_eins:
            skipped_clean += 1
            continue
        
        name = r['name']
        city = r.get('city', '') or source_data.get(ein, {}).get('CITY', '')
        state = r.get('state', '') or source_data.get(ein, {}).get('STATE', '')
        asset = r.get('asset_amt', '') or source_data.get(ein, {}).get('ASSET_AMT', '')
        ntee = r.get('ntee_code', '') or source_data.get(ein, {}).get('NTEE_CD', '')
        score = r.get('theology_score', '0')
        
        all_priority.append({
            'EIN': ein,
            'NAME': name,
            'CITY': city,
            'STATE': state,
            'ASSET_AMT': asset,
            'NTEE_CD': ntee,
            'EMAIL': '',
            'SOURCE': 'dns_info',
            'DOMAIN': domain,
            'SCRAPED_EMAIL': '',
            'SOURCE_URL': '',
            'THEOLOGY_SCORE': score,
            'PRIORITY': r['priority'],
            'TIER': tier_name,
        })
    
    print(f"\n{tier_name}:")
    print(f"  Classified: {len(classified)}")
    print(f"  HIGH+MEDIUM: {len(high_med)}")
    print(f"  Skipped (enriched): {skipped_enriched}")
    print(f"  Skipped (clean): {skipped_clean}")
    print(f"  Need scraping: {len([r for r in high_med if source_data.get(r['ein'],{}).get('GUESSED_DOMAIN','').strip() and r['ein'] not in enriched_eins and r['ein'] not in clean_eins])}")

# Sort by score descending
all_priority.sort(key=lambda x: -int(x['THEOLOGY_SCORE']))

print(f"\n\nTotal priority domains to scrape: {len(all_priority)}")
print(f"HIGH: {len([r for r in all_priority if r['PRIORITY']=='HIGH'])}")
print(f"MEDIUM: {len([r for r in all_priority if r['PRIORITY']=='MEDIUM'])}")

# Write combined list
combined_path = os.path.join(base_dir, 'priority_all.csv')
fieldnames = ['EIN','NAME','CITY','STATE','ASSET_AMT','NTEE_CD','EMAIL','SOURCE',
              'DOMAIN','SCRAPED_EMAIL','SOURCE_URL','THEOLOGY_SCORE','PRIORITY','TIER']
with open(combined_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(all_priority)
print(f"\nSaved combined: {combined_path}")

# Split into 4 batches for 4 EC2 instances
# Batch 1: Main EC2 (18.220.3.141) - highest priority
# Batch 2: Tier1 (13.58.64.223)
# Batch 3: Tier2 (18.219.220.68)
# Batch 4: Tier3 (13.59.175.171)
batch_size = max(1, len(all_priority) // 4)
batches = [
    all_priority[i:i+batch_size] 
    for i in range(0, len(all_priority), batch_size)
]

# If we have more than 4 batches, merge the last ones
if len(batches) > 4:
    merged = batches[:3]
    merged.append([item for sublist in batches[3:] for item in sublist])
    batches = merged

server_names = ['main_ec2', 'tier1', 'tier2', 'tier3']

for i, batch in enumerate(batches):
    name = server_names[i]
    path = os.path.join(base_dir, f'priority_{name}.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(batch)
    high_count = len([r for r in batch if r['PRIORITY'] == 'HIGH'])
    print(f"  {name}: {len(batch)} domains ({high_count} HIGH) -> {path}")

print(f"\nDone! Ready to upload to EC2 instances.")

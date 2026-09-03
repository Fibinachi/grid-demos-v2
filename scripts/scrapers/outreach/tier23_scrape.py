#!/usr/bin/env python3
"""Build tier2 and tier3 foundation scrape input CSVs.

Cross-references against enriched contacts to skip EINs that already have emails.
"""
import csv
import sys
import os

def build_scrape_list(tier_csv_path, enriched_csv_path, output_path, tier_label):
    """Build a scrape input CSV for a given tier."""
    
    # Load all domains from tier file
    tier_domains = {}  # domain -> (ein, name)
    with open(tier_csv_path, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            domain = r.get('GUESSED_DOMAIN', '').strip().lower()
            if domain:
                tier_domains[domain] = (r['EIN'].strip(), r['NAME'].strip())
    
    print(f'{tier_label}: {len(tier_domains)} total domains')
    
    # Collect EINs that already have emails (from enriched contacts)
    enriched_eins = set()
    if os.path.exists(enriched_csv_path):
        with open(enriched_csv_path, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                ein = r.get('EIN', '').strip()
                email = r.get('EMAIL', '').strip()
                if ein and email and email not in ('', 'dns_info'):
                    enriched_eins.add(ein)
    
    # Also check clean list
    clean_path = os.path.join(os.path.dirname(enriched_csv_path), 'enriched_contacts_clean.csv')
    clean_eins = set()
    if os.path.exists(clean_path):
        with open(clean_path, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                ein = r.get('EIN', '').strip()
                if ein:
                    clean_eins.add(ein)
    
    print(f'{tier_label}: {len(enriched_eins)} EINs in enriched, {len(clean_eins)} in clean list')
    
    # Filter: only domains not already in enriched or clean lists
    need_scrape = []
    skipped_enriched = 0
    skipped_clean = 0
    for domain, (ein, name) in tier_domains.items():
        if ein in enriched_eins:
            skipped_enriched += 1
        elif ein in clean_eins:
            skipped_clean += 1
        else:
            need_scrape.append((ein, name, domain))
    
    print(f'{tier_label}: {skipped_enriched} already in enriched, {skipped_clean} in clean, {len(need_scrape)} need scraping')
    
    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['EIN', 'NAME', 'CITY', 'STATE', 'ASSET_AMT', 'NTEE_CD',
                     'EMAIL', 'SOURCE', 'DOMAIN', 'SCRAPED_EMAIL', 'SOURCE_URL'])
        for ein, name, domain in need_scrape:
            w.writerow([ein, name, '', '', '', '', '', 'dns_info', domain, '', ''])
    
    print(f'{tier_label}: Saved {output_path} ({len(need_scrape)} rows)')
    return need_scrape


if __name__ == '__main__':
    base_dir = r'E:\grid'
    enriched_csv = os.path.join(base_dir, 'enriched_contacts.csv')
    
    # Tier2
    tier2_csv = os.path.join(base_dir, 'foundations_tier2_1m_10m.csv')
    tier2_out = os.path.join(base_dir, 'tier2_to_scrape.csv')
    t2 = build_scrape_list(tier2_csv, enriched_csv, tier2_out, 'Tier2 ($1M-$10M)')
    
    # Tier3
    tier3_csv = os.path.join(base_dir, 'foundations_tier3_500k_1m.csv')
    tier3_out = os.path.join(base_dir, 'tier3_to_scrape.csv')
    t3 = build_scrape_list(tier3_csv, enriched_csv, tier3_out, 'Tier3 ($500K-$1M)')
    
    total = len(t2) + len(t3)
    print(f'\nTotal domains needing scraping across tier2+tier3: {total:,}')
    print('Ready to upload and launch!')

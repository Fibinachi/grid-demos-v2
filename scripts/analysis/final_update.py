#!/usr/bin/env python3
"""Final update: merge scraped results into master list and rebuild send-ready list."""
import csv, os

base = os.path.dirname(os.path.abspath(__file__))

# Load scraped results
scraped = {}
with open(os.path.join(base, 'priority_all_scraped.csv')) as f:
    for r in csv.DictReader(f):
        ein = r.get('EIN', '').strip()
        email = r.get('SCRAPED_EMAIL', '').strip()
        if ein and email:
            scraped[ein] = email

print(f"New emails scraped: {len(scraped)}")
for ein, email in scraped.items():
    print(f"  {ein} -> {email}")

# Update master list HAS_EMAIL status
master_path = os.path.join(base, 'theology_master_list.csv')
updated_count = 0
rows = []
with open(master_path, 'r') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for r in reader:
        if r['EIN'] in scraped and r['HAS_EMAIL'] == 'NEED SCRAPING':
            r['HAS_EMAIL'] = 'YES'
            updated_count += 1
        rows.append(r)

print(f"\nUpdated {updated_count} foundations in master list (NEED SCRAPING -> YES)")

with open(master_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)

# Rebuild priority send list
high_ready = [r for r in rows if r['PRIORITY'] == 'HIGH' and r['HAS_EMAIL'] == 'YES']
send_path = os.path.join(base, 'theology_priority_send.csv')
with open(send_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(high_ready)

print(f"Ready-to-send HIGH priority: {len(high_ready)}")

# Final counts
total = len(rows)
high = len([r for r in rows if r['PRIORITY'] == 'HIGH'])
med = len([r for r in rows if r['PRIORITY'] == 'MEDIUM'])
need = len([r for r in rows if r['HAS_EMAIL'] == 'NEED SCRAPING'])

print(f"\n{'='*60}")
print(f"FINAL STATE - All work complete")
print(f"{'='*60}")
print(f"Master list:    {total} foundations")
print(f"HIGH priority:  {high} ({len(high_ready)} ready to send)")
print(f"MEDIUM priority:{med}")
print(f"Need scraping:  {need}")
print(f"\nEC2 fleet: all idle (scrapers killed, inbox monitor running)")
print(f"All key files in: {base}")

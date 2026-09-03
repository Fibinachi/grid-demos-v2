"""
Quick test of website scraper — runs on first N rows.
"""
import csv, os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrape_websites import scrape_foundation

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10

with open(CSV_PATH, 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

# Deduplicate by domain
seen = set()
to_scrape = []
for r in rows:
    domain = r.get('DOMAIN', '') or (r['EMAIL'].split('@')[1] if '@' in r.get('EMAIL','') else '')
    if domain and domain not in seen:
        seen.add(domain)
        to_scrape.append((r['NAME'], domain))

to_scrape = to_scrape[:limit]
print(f"Testing {len(to_scrape)} domains...")
print()

results = {'found': 0, 'not_found': 0, 'errors': 0}
for i, (name, domain) in enumerate(to_scrape):
    print(f"[{i+1}/{len(to_scrape)}] {name[:45]:45s} {domain}")
    try:
        email, url = scrape_foundation(name, domain)
        if email:
            print(f"  ✅ {email:45s} (from {url})")
            results['found'] += 1
        else:
            print(f"  ❌ No email found")
            results['not_found'] += 1
    except Exception as e:
        print(f"  ⚠️  Error: {str(e)[:80]}")
        results['errors'] += 1
    print()

print(f"Results: {results['found']} found, {results['not_found']} not found, {results['errors']} errors")

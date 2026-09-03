import csv, sys
path = sys.argv[1]
with open(path) as f:
    rows = list(csv.DictReader(f))
doms = sum(1 for r in rows if r.get('DOMAIN','').strip())
emails = sum(1 for r in rows if r.get('EMAIL','').strip())
has_website = sum(1 for r in rows if r.get('website','').strip() or r.get('WEBSITE','').strip())
print(f'{path}: {len(rows)} rows, {doms} with DOMAIN, {emails} with EMAIL, {has_website} with website')
if rows:
    print(f'  Headers: {list(rows[0].keys())}')

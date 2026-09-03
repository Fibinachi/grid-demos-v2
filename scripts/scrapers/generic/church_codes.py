"""Find church NTEE codes in IRS BMF and extract church data."""
import urllib.request, csv, io

# Check all unique classification codes that start with X (religious NTEE)
url = 'https://www.irs.gov/pub/irs-soi/eo1.csv'
req = urllib.request.Request(url)
resp = urllib.request.urlopen(req, timeout=60)
reader = csv.DictReader(io.TextIOWrapper(resp, encoding='utf-8-sig'))

church_codes = {}
count = 0
x_count = 0

for r in reader:
    c = r.get('CLASSIFICATION', '') or ''
    s = r.get('SUBSECTION', '') or ''
    count += 1
    
    if c.startswith('X'):
        x_count += 1
        church_codes[c] = church_codes.get(c, 0) + 1
    
    if count >= 500000:
        break

print(f'Total rows sampled: {count}')
print(f'Rows with X (religious) codes: {x_count}')
print()
print('Religious NTEE codes found:')
for k,v in sorted(church_codes.items(), key=lambda x:-x[1]):
    print(f'  {k}: {v}')

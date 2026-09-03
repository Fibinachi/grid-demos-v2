"""Download all churches (classification 7000) from IRS EO BMF."""
import urllib.request, csv, io, os

d = r'E:\grid'
output = os.path.join(d, 'irs_churches.csv')

# Stream through all 4 EO files and collect churches
headers = None
all_churches = []

for i in range(1, 5):
    url = f'https://www.irs.gov/pub/irs-soi/eo{i}.csv'
    print(f'Scanning eo{i}.csv...')
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=120)
    reader = csv.DictReader(io.TextIOWrapper(resp, encoding='utf-8-sig'))
    
    if headers is None:
        headers = reader.fieldnames
    
    for r in reader:
        if r.get('CLASSIFICATION', '') == '7000':
            all_churches.append(r)
    
    print(f'  Found {len(all_churches)} churches so far')

print(f'\nTotal churches found: {len(all_churches)}')

# Save
with open(output, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=headers)
    w.writeheader()
    w.writerows(all_churches)

print(f'Saved to: {output}')
print(f'File size: {os.path.getsize(output)/1024/1024:.1f} MB')

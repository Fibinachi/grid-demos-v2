"""Quick peek at IRS EO BMF to find church classification codes."""
import urllib.request, csv, io

url = 'https://www.irs.gov/pub/irs-soi/eo1.csv'
req = urllib.request.Request(url)
resp = urllib.request.urlopen(req, timeout=30)
reader = csv.DictReader(io.TextIOWrapper(resp, encoding='utf-8-sig'))

classifications = {}
activities = {}
subsections = {}
count = 0

for r in reader:
    c = r.get('CLASSIFICATION', '') or '(blank)'
    a = r.get('ACTIVITY', '') or '(blank)'
    s = r.get('SUBSECTION', '') or '(blank)'
    classifications[c] = classifications.get(c, 0) + 1
    activities[a] = activities.get(a, 0) + 1
    subsections[s] = subsections.get(s, 0) + 1
    count += 1
    if count >= 200000:
        break

print(f'Sampled {count} rows from eo1.csv')
print()
print('Subsections (top 10):')
for k,v in sorted(subsections.items(), key=lambda x:-x[1])[:10]:
    print(f'  [{k}]: {v}')

print()
print('Classifications (top 15):')
for k,v in sorted(classifications.items(), key=lambda x:-x[1])[:15]:
    print(f'  [{k}]: {v}')

print()
print('Activities (top 20):')
for k,v in sorted(activities.items(), key=lambda x:-x[1])[:20]:
    print(f'  [{k}]: {v}')

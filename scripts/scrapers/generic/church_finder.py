"""Look at real classification codes and find what churches look like."""
import urllib.request, csv, io

url = 'https://www.irs.gov/pub/irs-soi/eo1.csv'
req = urllib.request.Request(url)
resp = urllib.request.urlopen(req, timeout=60)
reader = csv.DictReader(io.TextIOWrapper(resp, encoding='utf-8-sig'))

# Look for churches by NAME containing "church"
church_count = 0
classification_counts = {}
subsection = {}

for i, r in enumerate(reader):
    name = (r.get('NAME', '') or '').upper()
    
    if 'CHURCH' in name or 'CHAPEL' in name or 'MINISTRY' in name or 'GOSPEL' in name or 'PENTECOSTAL' in name or 'BAPTIST' in name or 'METHODIST' in name:
        church_count += 1
        c = r.get('CLASSIFICATION', '') or '(blank)'
        s = r.get('SUBSECTION', '') or '(blank)'
        classification_counts[c] = classification_counts.get(c, 0) + 1
        subsection[s] = subsection.get(s, 0) + 1
        
        if church_count <= 10:
            print(f'  NAME: {r["NAME"][:50]}')
            print(f'  CLASSIFICATION: {c}, SUBSECTION: {s}')
            print(f'  CITY/STATE: {r.get("CITY","")}, {r.get("STATE","")}')
            print()
    
    if church_count >= 2000:
        break
    if i >= 500000:
        break

print(f'\nChurches found: {church_count}')
print(f'\nClassification codes for churches:')
for k,v in sorted(classification_counts.items(), key=lambda x:-x[1])[:10]:
    print(f'  [{k}]: {v}')
print(f'\nSubsections for churches:')
for k,v in sorted(subsection.items(), key=lambda x:-x[1])[:10]:
    print(f'  [{k}]: {v}')

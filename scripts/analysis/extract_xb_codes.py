import csv
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(script_dir, 'private_foundations_clean.csv'), 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

total = len(rows)
x_codes = [r for r in rows if r.get('NTEE_CD','').strip().startswith('X')]
b_codes = [r for r in rows if r.get('NTEE_CD','').strip().startswith('B')]

print('Total IRS records: %d' % total)
print('X (Religion) codes: %d' % len(x_codes))
print('B (Education) codes: %d' % len(b_codes))
print('Combined: %d' % (len(x_codes)+len(b_codes)))

# Write X/B entries to a CSV for build_contacts
outpath = os.path.join(script_dir, 'religious_education_orgs.csv')
with open(outpath, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['EIN','NAME','CITY','STATE','NTEE_CD','ASSET_AMT'])
    w.writeheader()
    for r in x_codes + b_codes:
        w.writerow({
            'EIN': r.get('EIN','').strip(),
            'NAME': r.get('NAME','').strip(),
            'CITY': r.get('CITY','').strip(),
            'STATE': r.get('STATE','').strip(),
            'NTEE_CD': r.get('NTEE_CD','').strip(),
            'ASSET_AMT': r.get('ASSET_AMT','').strip()
        })

print('Written to: %s' % outpath)

# Show samples
print('\nSample X (Religion):')
for r in x_codes[:5]:
    print('  %s | %s, %s | Assets: %s' % (r.get('NAME','')[:60], r.get('CITY',''), r.get('STATE',''), r.get('ASSET_AMT','')))

print('\nSample B (Education):')
for r in b_codes[:5]:
    print('  %s | %s, %s | Assets: %s' % (r.get('NAME','')[:60], r.get('CITY',''), r.get('STATE',''), r.get('ASSET_AMT','')))

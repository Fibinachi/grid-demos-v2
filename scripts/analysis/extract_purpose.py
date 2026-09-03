"""Check what years have our top foundations and extract their purpose"""
import urllib.request, csv, io, zipfile, re

# Our biggest foundations to check
targets = {
    '562618866': 'Gates Foundation',
    '131684331': 'Ford Foundation',
    '941655673': 'Hewlett Foundation',
    '237093598': 'MacArthur Foundation',
    '133441466': 'Walton Family Foundation',
    '621322826': 'Templeton Foundation',
}

# Check both 2025 and 2026 indexes
for year in [2025, 2026]:
    url = f'https://apps.irs.gov/pub/epostcard/990/xml/{year}/index_{year}.csv'
    print(f'\n=== {year} Index ===')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        content = r.read().decode('utf-8')
    reader = csv.DictReader(content.splitlines())
    found = []
    for row in reader:
        ein = row.get('EIN','').strip()
        if ein in targets:
            batch = row.get('XML_BATCH_ID','')
            found.append((ein, targets[ein], batch))
    if found:
        for ein, name, batch in found:
            print(f'  {name} ({ein}) -> {batch}')
    else:
        print('  None of our target EINs found')

# Now try to extract Gates Foundation's purpose from one batch
# They were likely in 2025
print('\n=== Looking for Gates Foundation purpose ===')
for year in [2025, 2026]:
    url = f'https://apps.irs.gov/pub/epostcard/990/xml/{year}/index_{year}.csv'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        content = r.read().decode('utf-8')
    reader = csv.DictReader(content.splitlines())
    for row in reader:
        if row.get('EIN','').strip() == '562618866':
            batch = row.get('XML_BATCH_ID','')
            print(f'Gates in {year}, batch {batch}')
            
            # Download that batch
            bz = f'https://apps.irs.gov/pub/epostcard/990/xml/{year}/{batch}.zip'
            print(f'Downloading {batch}.zip...')
            req2 = urllib.request.Request(bz, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req2, timeout=300) as r2:
                data = r2.read()
            
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
                for n in names:
                    if '562618866' in n:
                        xml = z.read(n).decode('utf-8', errors='ignore')
                        # Extract mission/purpose
                        for pat in [r'<(MissionDesc)[^>]*>\s*([^<]+)\s*</\1>',
                                     r'<(ActivityOrMissionDesc)[^>]*>\s*([^<]+)\s*</\1>',
                                     r'<(ProgramDescription)[^>]*>\s*([^<]{20,})\s*</\1>']:
                            for m in re.finditer(pat, xml, re.IGNORECASE):
                                print(f'  {m.group(1)}: {m.group(2).strip()[:200]}')
                        
                        # Also extract email/website from this real filing
                        for em in re.finditer(r'[\w.+-]+@[\w.-]+\.\w{2,4}', xml):
                            e = em.group(0)
                            if 'irs.gov' not in e.lower():
                                print(f'  Email: {e}')
                        for w in re.finditer(r'(https?://[^\s<\"\']+)', xml):
                            u = w.group(1)
                            if 'irs.gov' not in u.lower():
                                print(f'  Website: {u}')
                        break
            break

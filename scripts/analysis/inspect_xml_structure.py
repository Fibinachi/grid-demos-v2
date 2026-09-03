"""Download one 990-PF XML and show its email/website fields"""
import urllib.request, zipfile, io, re

url = 'https://apps.irs.gov/pub/epostcard/990/xml/2026/2026_TEOS_XML_01A.zip'
print('Downloading 01A...')
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=120) as r:
    data = r.read()

with zipfile.ZipFile(io.BytesIO(data)) as z:
    names = z.namelist()
    print(f'{len(names)} files')
    
    for name in names[:100]:  # Check first 100
        if name.endswith('.xml') and not name.startswith('_'):
            xml = z.read(name).decode('utf-8', errors='ignore')
            
            # Show XML structure (first 2000 chars)
            print(f'\n=== {name} ===')
            print(xml[:3000])
            
            # Search for email/website patterns
            for pat in [r'[Ee]mail', r'[Ww]ebsite', r'[Ww]eb', r'@']:
                for m in re.finditer(r'<[^>]*' + pat + r'[^>]*>', xml):
                    print(f'  TAG: {m.group()}')
            break

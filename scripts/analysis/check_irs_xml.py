"""Check IRS e-file XML download URLs"""
import urllib.request, re

urls = [
    'https://apps.irs.gov/pub/efile/',
    'https://www.irs.gov/pub/irs-efile/',
    'https://www.irs.gov/charities-non-profits/form-990-series-downloads',
]

for url in urls:
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read().decode('utf-8', errors='ignore')
            # Find all year/month download links
            links = re.findall(r'href=[\"\']([^\"\']+\.zip)[\"\']', content)
            xml_links = re.findall(r'href=[\"\']([^\"\']+202[0-9][^\"\']*)[\"\']', content)
            print('=== %s ===' % url)
            print('  Zip links: %d' % len(links))
            for l in links[:10]:
                print('    %s' % l)
            print('  Date/year links: %d' % len(xml_links))
            for l in xml_links[:10]:
                print('    %s' % l)
            # Also check for text content with "xml" or "download"
            if 'xml' in content.lower():
                lines = content.split('\n')
                for line in lines:
                    if 'xml' in line.lower() and ('202' in line or 'download' in line.lower()):
                        print('  XML ref: %s' % line.strip()[:200])
    except Exception as e:
        print('%s -> %s' % (url, str(e)[:100]))

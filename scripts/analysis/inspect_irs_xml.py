"""Download and inspect IRS 990-PF XML for email/website fields"""
import urllib.request, zipfile, io, csv, re
import xml.etree.ElementTree as ET

url = 'https://apps.irs.gov/pub/epostcard/990/xml/2026/2026_TEOS_XML_04A.zip'
print('Downloading 2026_TEOS_XML_04A.zip...')
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=120) as r:
    data = r.read()
print('Size: %.1f MB' % (len(data) / 1024 / 1024))

with zipfile.ZipFile(io.BytesIO(data)) as z:
    names = z.namelist()
    print('Total XML files in zip: %s' % f'{len(names):,}')
    
    for name in names:
        if name.startswith('_') or not name.endswith('.xml'):
            continue
        xml_content = z.read(name).decode('utf-8', errors='ignore')
        if 'ReturnOfPrivateFoundation' in xml_content or '990-PF' in xml_content[:500]:
            print()
            print('Sample 990-PF: %s' % name)
            print('Size: %.1f KB' % (len(xml_content)/1024))
            
            # Regex search for email/website
            emails = set(re.findall(r'[\w.+-]+@[\w.-]+\.\w{2,4}', xml_content))
            # Filter non-foundation emails
            real_emails = [e for e in emails if not any(x in e.lower() for x in ['irs.gov','efile'])]
            print('Real emails: %d' % len(real_emails))
            for e in real_emails[:5]:
                print('  %s' % e)
            
            # URLs
            urls = set(re.findall(r'(https?://[^\s<"\']+)', xml_content))
            real_urls = [u for u in urls if 'irs.gov' not in u.lower() and 'teos' not in u.lower()]
            print('Real URLs: %d' % len(real_urls))
            for u in real_urls[:5]:
                print('  %s' % u)
            
            # Try structured XML parsing (just first 10KB)
            match = re.search(r'<(Email|Website|WebUrl|BusinessOfficerEmail)[^>]*>(.*?)</\1>', xml_content, re.IGNORECASE)
            if match:
                print('Structured field: %s = %s' % (match.group(1), match.group(2)))
            break

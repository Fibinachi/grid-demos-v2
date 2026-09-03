"""Search for email and website in 990-PF XML files"""
import urllib.request, zipfile, io, re

url = 'https://apps.irs.gov/pub/epostcard/990/xml/2026/2026_TEOS_XML_01A.zip'
print('Downloading...')
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=120) as r:
    data = r.read()

with zipfile.ZipFile(io.BytesIO(data)) as z:
    names = z.namelist()
    print(f'{len(names)} files total')
    
    # Find 990-PF files and search for email/website
    found = 0
    for name in names:
        if not name.endswith('.xml') or name.startswith('_'):
            continue
        xml = z.read(name).decode('utf-8', errors='ignore')
        if '990PF' not in xml:
            continue
        
        found += 1
        ein_match = re.search(r'<EIN>(\d+)</EIN>', xml)
        name_match = re.search(r'<BusinessNameLine1Txt>([^<]+)</', xml)
        ein = ein_match.group(1) if ein_match else '?'
        org = name_match.group(1) if name_match else '?'
        
        # Search ALL possible email/website fields
        email_fields = re.findall(r'<(Email|EmailAddress|EmailAddr|BusinessOfficerEmail|EmailContact)[^>]*>\s*([^<]+@[^<]+)\s*</', xml, re.IGNORECASE)
        website_fields = re.findall(r'<(Website|WebsiteAddress|WebSite|WebUrl)[^>]*>\s*([^<]+)\s*</', xml, re.IGNORECASE)
        
        # Also search for @ anywhere in the XML
        all_emails = re.findall(r'[\w.+-]+@[\w.-]+\.\w{2,4}', xml)
        real_emails = [e for e in all_emails if 'irs.gov' not in e.lower() and 'example' not in e.lower()]
        
        if email_fields or website_fields or real_emails:
            print(f'\nEIN: {ein} | {org}')
            if email_fields:
                for tag, val in email_fields:
                    print(f'  XML EMAIL: <{tag}> {val}')
            if website_fields:
                for tag, val in website_fields:
                    print(f'  XML WEBSITE: <{tag}> {val}')
            if real_emails and not email_fields:
                for e in real_emails[:3]:
                    print(f'  RAW EMAIL: {e}')
            
            if found >= 10:
                break
        
        if found >= 500 and not email_fields:
            print(f'\nScanned {found} 990-PF files - NO EMAIL FIELDS FOUND ANYWHERE')
            print('The IRS XML does not contain email/website fields in this format.')
            break

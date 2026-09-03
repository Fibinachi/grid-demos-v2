"""Check IRS 990-PF XML for mission/purpose/description fields"""
import urllib.request, zipfile, io, re

url = 'https://apps.irs.gov/pub/epostcard/990/xml/2026/2026_TEOS_XML_01A.zip'
print('Downloading 01A...')
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=120) as r:
    data = r.read()
print('Downloaded %.1f MB' % (len(data)/1024/1024))

with zipfile.ZipFile(io.BytesIO(data)) as z:
    names = z.namelist()
    print('Files: %d' % len(names))
    
    found_mission = 0
    for name in names:
        if name.endswith('.xml') and not name.startswith('_'):
            xml = z.read(name).decode('utf-8', errors='ignore')
            if '990PF' not in xml:
                continue
            
            # Search for mission/purpose fields
            patterns = [
                (r'<(Mission|Purpose|MissionDesc|PurposeDesc)[^>]*>\s*([^<]{20,})\s*</\1>', 'Mission/Purpose'),
                (r'<(FormationOrMission|ActivityOrMissionDesc)[^>]*>\s*([^<]{20,})\s*</\1>', 'Formation'),
                (r'<(ProgramDescription|ProgramTitle)[^>]*>\s*([^<]{20,})\s*</\1>', 'Program'),
                (r'<(Organization501c3Desc)[^>]*>\s*([^<]{20,})\s*</\1>', '501c3'),
            ]
            
            for pat, label in patterns:
                for m in re.finditer(pat, xml, re.IGNORECASE):
                    tag, val = m.group(1), m.group(2).strip()
                    if len(val) > 15 and 'http' not in val:
                        ein_m = re.search(r'<EIN>(\d+)</EIN>', xml)
                        nm_m = re.search(r'<BusinessNameLine1Txt>([^<]+)</', xml)
                        ein = ein_m.group(1) if ein_m else '?'
                        org = nm_m.group(1) if nm_m else '?'
                        print('\n%s: <%s>' % (label, tag))
                        print('  EIN: %s | %s' % (ein, org[:50]))
                        print('  Text: %s' % val[:300])
                        found_mission += 1
                        if found_mission >= 10:
                            break
                if found_mission >= 10:
                    break
        if found_mission >= 10:
            break
    
    if found_mission == 0:
        print('\nNo mission/purpose description fields found in 10K+ files.')
        print('The 990-PF XML schema stores these in a different format.')

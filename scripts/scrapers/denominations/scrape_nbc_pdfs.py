"""
Extract NBC state convention PDF church lists and import into DB.
Sources: AL, FL, MS, AR, PA, OH state convention sites.
PDFs contain church name, pastor, address, city, state, zip.
"""
import urllib.request, re, os, json, ssl, fitz

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(SCRIPT_DIR, '..', '..', 'data', 'nbc_churches.jsonl')

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
        return resp.read()
    except:
        return None

def fetch_html(url):
    d = fetch(url)
    return d.decode('utf-8', 'replace') if d else ''

def find_pdfs(url, domain):
    """Find PDF links from a webpage."""
    html = fetch_html(url)
    if not html:
        return []
    pdfs = re.findall(r'href="([^"]*\.pdf)"', html, re.IGNORECASE)
    results = []
    for p in pdfs:
        full = p if p.startswith('http') else ('https://' + domain.rstrip('/') + '/' + p.lstrip('/'))
        results.append(full)
    return results

def extract_churches(pdf_data, default_state):
    churches = []
    try:
        doc = fitz.open(stream=pdf_data, filetype='pdf')
        for page in doc:
            blocks = page.get_text('dict')['blocks']
            lines = []
            for block in blocks:
                if 'lines' in block:
                    for line in block['lines']:
                        text = ''.join([s['text'] for s in line['spans']]).strip()
                        if text:
                            lines.append(text)
            # Parse 6-line blocks: Name, Pastor, Address, City, State, Zip
            i = 0
            while i < len(lines) - 5:
                name = lines[i]
                pastor = lines[i+1]
                address = lines[i+2]
                city = lines[i+3]
                state = lines[i+4]
                zip_code = lines[i+5]
                if name in ['Church', 'Pastor', 'Street', 'City', 'State', 'Zip', 'Eligible']:
                    i += 1; continue
                if 'Eligible Churches' in name or 'Sessions' in name or 'Northwest' in name or 'Northeast' in name:
                    i += 1; continue
                if re.match(r'^[A-Z]{2}$', state) and re.match(r'^\d{5}', str(zip_code)) and len(name) > 3:
                    churches.append({
                        'name': name, 'pastor': pastor, 'address': address,
                        'city': city, 'state': state, 'zip': zip_code
                    })
                    i += 6
                else:
                    i += 1
        doc.close()
    except Exception as e:
        print('    PDF error: {}'.format(e))
    return churches

# Known PDF sources
PDFS = [
    ('AL', 'https://alabamastatebaptist.org/wp-content/uploads/2026/02/ASMBC-Election-Voting-Eligibility-List.pdf'),
    ('AL', 'https://alabamastatebaptist.org/wp-content/uploads/2026/02/Northwest-District-Wing-Voting-Eligibility-List.pdf'),
    ('AL', 'https://alabamastatebaptist.org/wp-content/uploads/2026/02/Southeast-District-Wing-Voting-Eligibility-List.pdf'),
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
total = 0
for state, pdf_url in PDFS:
    fname = pdf_url.split('/')[-1][:50]
    print('{}: {}'.format(state, fname))
    data = fetch(pdf_url)
    if data and len(data) > 10000:
        churches = extract_churches(data, state)
        print('  {} churches'.format(len(churches)))
        for c in churches[:2]:
            print('    {} | {}, {} | {}'.format(c['name'][:35], c['city'][:15], c['state'], c['address'][:25]))
        with open(OUTPUT, 'a', encoding='utf-8') as f:
            for c in churches:
                f.write(json.dumps(c) + '\n')
        total += len(churches)
    else:
        print('  Failed ({}b)'.format(len(data) if data else 0))

print('\nTotal: {} churches from AL'.format(total))
print('Output: {}'.format(OUTPUT))

# Now explore more state sites for PDFs
print('\n=== Discovering more PDFs ===')
MORE_SITES = [
    ('FL', 'https://www.fgbci.org/'),
    ('MS', 'http://www.gmbsc.org/'),
    ('AR', 'http://cmbsc29.com/'),
    ('PA', 'http://www.thepbsc.org/'),
    ('OH', 'http://obsc1.org/'),
]
for state, url in MORE_SITES:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=15, context=ssl_ctx)
        html = resp.read().decode('utf-8', 'replace')
        pdfs = re.findall(r'href="([^"]*\.pdf)"', html, re.IGNORECASE)
        dir_links = [l for l in pdfs if 'church' in l.lower() or 'director' in l.lower() or 'roster' in l.lower() or 'election' in l.lower() or 'member' in l.lower()]
        print('  {}: {} total PDFs, {} likely church directories'.format(state, len(pdfs), len(dir_links)))
        for dl in dir_links[:5]:
            full = dl if dl.startswith('http') else url.rstrip('/') + '/' + dl
            print('    {}'.format(full[:80]))
    except Exception as e:
        print('  {}: {}'.format(state, str(e)[:40]))

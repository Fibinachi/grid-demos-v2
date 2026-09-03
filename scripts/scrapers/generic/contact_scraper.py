"""
Foundation Contact Scraper
===========================
Downloads IRS 990-PF XML filings and extracts contact info.
Then DNS-verifies email domains for the rest.

Strategy:
  1. Cross-reference our EINs against IRS 2026 + 2025 index
  2. Download only the batch zips that contain our foundations
  3. Extract emails/websites from each matching XML
  4. For remaining foundations, DNS-verify guessed domains
  5. Output enriched_contacts.csv
"""

import csv
import os
import sys
import re
import json
import time
import socket
import urllib.request
import zipfile
import io

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "theology_priority_foundations.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "enrich_progress.json")
IRS_BASE = "https://apps.irs.gov/pub/epostcard/990/xml"

_dns_cache = {}

def domain_resolves(domain):
    if domain in _dns_cache:
        return _dns_cache[domain]
    try:
        socket.getaddrinfo(domain, 80, timeout=3)
        _dns_cache[domain] = True
        return True
    except:
        _dns_cache[domain] = False
        return False

def extract_emails_from_xml(text):
    """Extract real organizational emails from 990-PF XML."""
    results = set()
    
    # Method 1: Find XML elements that might contain emails
    # Look for patterns like <Email>addr@domain.com</Email>
    for m in re.finditer(r'<([A-Za-z]+)[^>]*>\s*([\w.+-]+@[\w.-]+\.\w{2,4})\s*</\1>', text):
        tag, email = m.group(1), m.group(2).strip().lower()
        if not any(x in email for x in ['irs.gov', 'efile', '.irs.', 'teos']):
            results.add(('xml_tag', email, tag))
    
    # Method 2: Find email in any attribute/body context
    for m in re.finditer(r'[\w.+-]+@[\w.-]+\.\w{2,4}', text):
        email = m.group(0).lower()
        if not any(x in email for x in ['irs.gov', 'efile', '.irs.', 'teos', 'example.com']):
            results.add(('regex', email, ''))
    
    # Method 3: Look specifically for BusinessOfficerEmail, Email, Website fields
    for field in ['BusinessOfficerEmail', 'Email', 'email', 'EmailAddr', 'EmailAddress']:
        for m in re.finditer(r'<' + field + r'[^>]*>\s*([^<]+@[^<]+)\s*</' + field + r'>', text, re.IGNORECASE):
            email = m.group(1).strip().lower()
            if not any(x in email for x in ['irs.gov', 'efile']):
                results.add(('structured', email, field))
    
    return list(results)

def extract_urls_from_xml(text):
    """Extract website URLs from 990-PF XML."""
    urls = set()
    for m in re.finditer(r'(https?://(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9.]*\.[a-zA-Z]{2,}(?:/[^\s<"\'\\]*)?)', text):
        url = m.group(1).rstrip('/')
        if not any(x in url.lower() for x in ['irs.gov', 'teos']):
            urls.add(url)
    # Also look for Website XML elements
    for m in re.finditer(r'<(?:Website|WebSite|WebUrl|website)[^>]*>\s*([^<]+)\s*</', text, re.IGNORECASE):
        url = m.group(1).strip()
        if not any(x in url.lower() for x in ['irs.gov']):
            urls.add(url)
    return list(urls)

def download_file(url, desc="Downloading"):
    """Download with progress."""
    print(f"  {desc}...")
    sys.stdout.flush()
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    print(f"    {len(data)/1024/1024:.1f} MB")
    return data

def load_index(year):
    """Load IRS index for a year, return list of dicts."""
    url = f"{IRS_BASE}/{year}/index_{year}.csv"
    content = download_file(url, f"  Loading {year} index")
    reader = csv.DictReader(content.decode('utf-8').splitlines())
    return list(reader)

def process_batch(batch_id, year, our_eins):
    """Download a batch zip and extract contacts for our EINs."""
    url = f"{IRS_BASE}/{year}/{batch_id}.zip"
    data = download_file(url, f"  Downloading {batch_id}")
    
    contacts = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        # Build EIN lookup from filenames
        ein_files = {}
        for n in names:
            if not n.endswith('.xml') or n.startswith('_'):
                continue
            match = re.search(r'(\d{9})', n)
            if match and match.group(1) in our_eins:
                ein_files[match.group(1)] = n
        
        found = len(ein_files)
        print(f"    Found {found} of our filings in this batch")
        
        for i, (ein, filename) in enumerate(ein_files.items()):
            try:
                xml = z.read(filename).decode('utf-8', errors='ignore')
            except:
                continue
            
            emails = extract_emails_from_xml(xml)
            urls = extract_urls_from_xml(xml)
            
            # Pick best email
            best_email = None
            best_url = None
            email_source = ''
            
            # Prefer structured fields
            for method, val, tag in emails:
                if method == 'structured':
                    best_email = val
                    email_source = f'{year}_{batch_id}_xml'
                    break
            if not best_email and emails:
                best_email = emails[0][1]
                email_source = f'{year}_{batch_id}_xml'
            
            # Pick best URL
            if urls:
                best_url = urls[0]
            
            if best_email or best_url:
                contacts[ein] = {'email': best_email, 'url': best_url, 'source': email_source}
            
            if (i + 1) % 100 == 0:
                print(f"      Processed {i+1}/{found}")
    
    return contacts

def main():
    print("=" * 70)
    print("  FOUNDATION CONTACT SCRAPER")
    print("=" * 70)
    
    # Load foundations
    print(f"\nLoading {INPUT_CSV}...")
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        foundations = list(csv.DictReader(f))
    our_eins = set(f['EIN'].strip() for f in foundations if f['EIN'].strip())
    print(f"  {len(foundations):,} foundations, {len(our_eins):,} unique EINs")
    
    all_contacts = {}
    
    # Step 1: Process 2026 data
    print("\n--- STEP 1: IRS 2026 990-PF XML ---")
    index_2026 = load_index(2026)
    # Find our 990-PF filings
    our_2026 = [(e.get('EIN',''), e.get('XML_BATCH_ID','')) for e in index_2026 
                if e.get('RETURN_TYPE') == '990PF' and e.get('EIN','').strip() in our_eins]
    print(f"  Our 990-PF filings in 2026: {len(our_2026)}")
    
    # Group by batch
    by_batch = {}
    for ein, batch in our_2026:
        by_batch.setdefault(batch, []).append(ein)
    
    for batch_id, eins in sorted(by_batch.items()):
        contacts = process_batch(batch_id, 2026, set(eins))
        all_contacts.update(contacts)
        print(f"    Extracted {len(contacts)} contacts from {batch_id}")
    
    print(f"\n  2026 total: {len(all_contacts)} contacts")
    
    # Step 2: Process 2025 data for what's missing
    remaining = len(our_eins) - len(all_contacts)
    if remaining > 0:
        print(f"\n--- STEP 2: IRS 2025 990-PF XML ({remaining:,} remaining) ---")
        index_2025 = load_index(2025)
        our_2025 = [(e.get('EIN',''), e.get('XML_BATCH_ID','')) for e in index_2025 
                    if e.get('RETURN_TYPE') == '990PF' and e.get('EIN','').strip() in our_eins
                    and e.get('EIN','').strip() not in all_contacts]
        print(f"  Our remaining 990-PF filings in 2025: {len(our_2025)}")
        
        by_batch_2025 = {}
        for ein, batch in our_2025:
            by_batch_2025.setdefault(batch, []).append(ein)
        
        for batch_id, eins in sorted(by_batch_2025.items()):
            contacts = process_batch(batch_id, 2025, set(eins))
            all_contacts.update(contacts)
            print(f"    Extracted {len(contacts)} contacts from {batch_id}")
    
    print(f"\n  Total IRS contacts: {len(all_contacts)}")
    
    # Step 3: DNS verification for all
    print(f"\n--- STEP 3: DNS Domain Verification ---")
    dns_contacts = {}
    for f in foundations:
        ein = f['EIN'].strip()
        if ein in all_contacts and all_contacts[ein].get('email'):
            continue  # Already have real email
        
        name = f['NAME']
        clean = name.strip().replace(',','').lower().replace('the ','')
        for suf in [' foundation',' foundation inc',' foundation corporation',' inc',' corp',' llc']:
            clean = clean.replace(suf, '')
        words = [w for w in clean.split() if w not in {'and','the','of','for','&','de','la','del'} and len(w)>2]
        
        if not words:
            continue
        
        last = words[-1]
        candidates = [last+'foundation.org', last+'.org', words[0]+'foundation.org']
        
        for domain in candidates:
            if len(domain) > 50:
                continue
            if domain_resolves(domain):
                dns_contacts[ein] = {'dns_email': f'info@{domain}', 'dns_domain': domain}
                break
    
    print(f"  DNS-verified domains: {len(dns_contacts)}")
    
    # Step 4: Write output
    print(f"\n--- STEP 4: Writing enriched_contacts.csv ---")
    fieldnames = ['EIN', 'NAME', 'CITY', 'STATE', 'ASSET_AMT', 'NTEE_CD',
                  'EMAIL', 'EMAIL_SOURCE', 'WEBSITE', 'DNS_EMAIL', 'DNS_DOMAIN']
    
    stats = {'irs_email': 0, 'irs_website': 0, 'dns_only': 0, 'no_contact': 0}
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for fb in foundations:
            ein = fb['EIN'].strip()
            row = {k: fb.get(k, '') for k in ['EIN','NAME','CITY','STATE','ASSET_AMT','NTEE_CD']}
            row.update({'EMAIL':'','EMAIL_SOURCE':'','WEBSITE':'','DNS_EMAIL':'','DNS_DOMAIN':''})
            
            if ein in all_contacts:
                c = all_contacts[ein]
                if c.get('email'):
                    row['EMAIL'] = c['email']
                    row['EMAIL_SOURCE'] = c.get('source', 'irs_xml')
                    stats['irs_email'] += 1
                if c.get('url'):
                    row['WEBSITE'] = c['url']
                    stats['irs_website'] += 1
                if not c.get('email') and ein in dns_contacts:
                    row['DNS_EMAIL'] = dns_contacts[ein]['dns_email']
                    row['DNS_DOMAIN'] = dns_contacts[ein]['dns_domain']
                    stats['dns_only'] += 1
            elif ein in dns_contacts:
                row['DNS_EMAIL'] = dns_contacts[ein]['dns_email']
                row['DNS_DOMAIN'] = dns_contacts[ein]['dns_domain']
                stats['dns_only'] += 1
            else:
                stats['no_contact'] += 1
            
            w.writerow(row)
    
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"  IRS 990-PF emails:  {stats['irs_email']:>6,}")
    print(f"  IRS 990-PF websites:{stats['irs_website']:>6,}")
    print(f"  DNS-verified only:  {stats['dns_only']:>6,}")
    print(f"  No contact found:   {stats['no_contact']:>6,}")
    print(f"  Total with contact: {stats['irs_email']+stats['dns_only']:>6,}")
    print(f"  Output: {OUTPUT_CSV}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()

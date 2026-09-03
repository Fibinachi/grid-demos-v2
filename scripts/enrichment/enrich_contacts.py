"""
Foundation Contact Enrichment Pipeline
========================================
Cross-references our foundation list with:
1. IRS 990-PF XML filings (2026 and 2025) for real emails/websites
2. DNS verification for domain guessing

Output: enriched_contacts.csv with best available contact info
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
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "theology_priority_foundations.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")

IRS_BASE = "https://apps.irs.gov/pub/epostcard/990/xml"

# DNS cache
_dns_cache = {}

def domain_exists(domain):
    if domain in _dns_cache:
        return _dns_cache[domain]
    try:
        socket.getaddrinfo(domain, 80, timeout=3)
        _dns_cache[domain] = True
        return True
    except Exception:
        _dns_cache[domain] = False
        return False

def guess_domains(name):
    """Generate candidate domains from foundation name."""
    clean = name.strip().replace(",", "").lower()
    clean = clean.replace("the ", "")
    for suffix in [" foundation", " foundation inc", " foundation corporation",
                   " inc", " corp", " llc", ", inc.", ", llc"]:
        clean = clean.replace(suffix, "")
    words = clean.split()
    if not words:
        return []
    connectors = {"and", "the", "of", "for", "&", "de", "la", "del"}
    meaningful = [w for w in words if w not in connectors and len(w) > 2]
    if not meaningful:
        meaningful = words
    last = meaningful[-1] if meaningful else words[-1]
    first = meaningful[0] if meaningful else words[0]
    candidates = [
        last + "foundation.org",
        first + "foundation.org",
        last + ".org",
        first + ".org",
        "".join(meaningful) + ".org",
    ]
    return [d for d in candidates if len(d) < 50]

def find_email_via_dns(name):
    """Try DNS-based domain guessing."""
    for domain in guess_domains(name):
        if domain_exists(domain):
            return "info@" + domain, domain
    return None, None

def download_index(year):
    """Download IRS index CSV for a given year."""
    url = f"{IRS_BASE}/{year}/index_{year}.csv"
    print(f"  Downloading {year} index...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode('utf-8')
    return None

def parse_index(content):
    """Parse index CSV into list of dicts."""
    lines = content.splitlines()
    reader = csv.DictReader(lines)
    return list(reader)

def build_ein_lookup(entries):
    """Build EIN -> row lookup from index entries."""
    lookup = {}
    for e in entries:
        ein = e.get('EIN', '').strip()
        if ein and e.get('RETURN_TYPE') == '990PF':
            lookup[ein] = e
    return lookup

def download_batch(batch_id, year):
    """Download an XML batch zip and return the data."""
    url = f"{IRS_BASE}/{year}/{batch_id}.zip"
    print(f"  Downloading {batch_id}.zip...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()
    return None

def extract_contact_from_xml(xml_content):
    """Extract email and website from 990-PF XML via regex."""
    emails = set(re.findall(r'[\w.+-]+@[\w.-]+\.\w{2,4}', xml_content))
    emails = [e for e in emails if 'irs.gov' not in e.lower() and 'efile' not in e.lower()]
    
    urls = set(re.findall(r'(https?://[^\s<"\']+)', xml_content))
    urls = [u for u in urls if 'irs.gov' not in u.lower()]
    
    # Look for specific 990-PF email fields
    structured_email = None
    structured_url = None
    
    # Try to find the Email field in the XML
    ematch = re.search(r'<(?:Email|EmailAddress|email)[^>]*>\s*([^<]+@[^<]+)\s*</', xml_content, re.IGNORECASE)
    if ematch:
        structured_email = ematch.group(1).strip()
    
    # Try Website field
    wmatch = re.search(r'<(?:Website|WebSite|WebUrl|WebsiteAddress|website)[^>]*>\s*([^<]+)\s*</', xml_content, re.IGNORECASE)
    if wmatch:
        structured_url = wmatch.group(1).strip()
    
    # Filter real-looking emails
    real_emails = [e for e in emails if '@' in e and len(e) > 6 and '.' in e.split('@')[1]]
    
    best_email = structured_email or (real_emails[0] if real_emails else None)
    best_url = structured_url or (urls[0] if urls else None)
    
    return best_email, best_url

def process_year(lookup, year, batch_data_cache):
    """Process all batches for a year to find our foundations."""
    # Group our EINs by batch
    batch_eins = {}
    for ein, entry in lookup.items():
        batch = entry.get('XML_BATCH_ID', '').strip()
        if batch:
            batch_eins.setdefault(batch, []).append(ein)
    
    print(f"\n  Our 990-PF filings found: {len(lookup)}")
    print(f"  Across batches: {list(batch_eins.keys())}")
    
    results = {}
    
    for batch_id, eins in batch_eins.items():
        data = download_batch(batch_id, year)
        if not data:
            continue
        
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
            print(f"    Scanning {len(names)} XML files in {batch_id}...")
            
            found = 0
            for name in names:
                if name.startswith('_') or not name.endswith('.xml'):
                    continue
                
                # Check if this XML's EIN is in our list by checking filename
                # IRS XML filenames typically contain the EIN
                ein_match = re.search(r'(\d{9})', name)
                if not ein_match:
                    continue
                
                xml_ein = ein_match.group(1)
                if xml_ein not in eins:
                    continue
                
                # Extract contacts
                try:
                    xml_content = z.read(name).decode('utf-8', errors='ignore')
                except:
                    continue
                
                email, url = extract_contact_from_xml(xml_content)
                if email or url:
                    results[xml_ein] = {'email': email, 'url': url, 'source': f'{year}_{batch_id}'}
                    found += 1
                
                if found % 50 == 0 and found > 0:
                    print(f"      Found {found} contacts so far...")
        
        # Cache the batch data for potential reuse
        batch_data_cache[batch_id] = data
    
    return results

def main():
    print("=" * 70)
    print("  FOUNDATION CONTACT ENRICHMENT PIPELINE")
    print("=" * 70)
    
    # Load our foundation list
    print(f"\nLoading {INPUT_CSV}...")
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        our_foundations = list(csv.DictReader(f))
    print(f"  {len(our_foundations):,} foundations loaded")
    
    # Build EIN set
    our_eins = set(f['EIN'].strip() for f in our_foundations if f['EIN'].strip())
    print(f"  {len(our_eins):,} unique EINs")
    
    # Results storage
    enriched = {}
    batch_data_cache = {}
    
    # Step 1: Try IRS 2026 XML data
    print("\n--- STEP 1: IRS 2026 990-PF XML ---")
    index_2026 = download_index(2026)
    if index_2026:
        entries_2026 = parse_index(index_2026)
        lookup_2026 = build_ein_lookup(entries_2026)
        # Filter to only our EINs
        our_lookup = {k: v for k, v in lookup_2026.items() if k in our_eins}
        results_2026 = process_year(our_lookup, 2026, batch_data_cache)
        enriched.update(results_2026)
        print(f"  Found {len(results_2026)} contacts from 2026")
    
    # Step 2: Try IRS 2025 XML for remaining
    remaining = our_eins - set(enriched.keys())
    print(f"\n--- STEP 2: IRS 2025 990-PF XML ({len(remaining):,} remaining) ---")
    if remaining:
        index_2025 = download_index(2025)
        if index_2025:
            entries_2025 = parse_index(index_2025)
            lookup_2025 = build_ein_lookup(entries_2025)
            our_lookup_2025 = {k: v for k, v in lookup_2025.items() if k in remaining}
            results_2025 = process_year(our_lookup_2025, 2025, batch_data_cache)
            enriched.update(results_2025)
            print(f"  Found {len(results_2025)} contacts from 2025")
    
    # Step 3: DNS-based guessing for all
    print(f"\n--- STEP 3: DNS Domain Guessing (all foundations) ---")
    dns_found = 0
    for f in our_foundations:
        ein = f['EIN'].strip()
        if ein in enriched and enriched[ein].get('email'):
            continue  # Already have real email
        name = f['NAME']
        email, domain = find_email_via_dns(name)
        if email:
            if ein not in enriched:
                enriched[ein] = {}
            enriched[ein]['dns_email'] = email
            enriched[ein]['dns_domain'] = domain
            dns_found += 1
    
    print(f"  DNS-verified domains: {dns_found}")
    
    # Step 4: Write output
    print(f"\n--- STEP 4: Writing {OUTPUT_CSV} ---")
    fieldnames = ['EIN', 'NAME', 'CITY', 'STATE', 'ASSET_AMT', 'NTEE_CD',
                  'EMAIL', 'EMAIL_SOURCE', 'WEBSITE', 'WEBSITE_SOURCE',
                  'DNS_EMAIL', 'DNS_DOMAIN']
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        stats = {'irs_email': 0, 'dns_email': 0, 'no_contact': 0}
        
        for fb in our_foundations:
            ein = fb['EIN'].strip()
            row = {
                'EIN': ein,
                'NAME': fb.get('NAME', ''),
                'CITY': fb.get('CITY', ''),
                'STATE': fb.get('STATE', ''),
                'ASSET_AMT': fb.get('ASSET_AMT', ''),
                'NTEE_CD': fb.get('NTEE_CD', ''),
                'EMAIL': '',
                'EMAIL_SOURCE': '',
                'WEBSITE': '',
                'WEBSITE_SOURCE': '',
                'DNS_EMAIL': '',
                'DNS_DOMAIN': '',
            }
            
            if ein in enriched:
                e = enriched[ein]
                if e.get('email'):
                    row['EMAIL'] = e['email']
                    row['EMAIL_SOURCE'] = e.get('source', 'irs_xml')
                    row['WEBSITE'] = e.get('url', '')
                    row['WEBSITE_SOURCE'] = e.get('source', 'irs_xml') if e.get('url') else ''
                    stats['irs_email'] += 1
                elif e.get('dns_email'):
                    row['DNS_EMAIL'] = e['dns_email']
                    row['DNS_DOMAIN'] = e['dns_domain']
                    stats['dns_email'] += 1
                else:
                    stats['no_contact'] += 1
            else:
                stats['no_contact'] += 1
            
            writer.writerow(row)
    
    print(f"\n{'=' * 70}")
    print(f"  ENRICHMENT COMPLETE")
    print(f"  IRS 990-PF emails found: {stats['irs_email']:,}")
    print(f"  DNS-verified domains:    {stats['dns_email']:,}")
    print(f"  No contact found:        {stats['no_contact']:,}")
    print(f"  Output: {OUTPUT_CSV}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()

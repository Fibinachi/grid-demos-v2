"""
Web Search Email Finder
=======================
For each foundation, searches the web for email addresses matching
their domain. Uses Bing (free, no API key needed) to find pages
that mention @foundationdomain.org patterns.

This catches emails that appear on:
- Guidestar / Candid profiles
- Foundation directory listings
- News articles about the foundation
- PDF grant reports
- LinkedIn / professional profiles

Usage: python search_emails.py [--input theology_gmail_send.csv] [--output search_found_emails.csv]
"""
import csv
import os
import re
import json
import time
import random
import urllib.request
import urllib.parse
import urllib.error
import socket
import ssl
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "theology_gmail_send.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "search_found_emails.csv")

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
]

# Email regex - broad
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.\w{2,4}', re.IGNORECASE)

# Skip known generic/throwaway domains
SKIP_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
                'icloud.com', 'protonmail.com', 'mail.com', 'msn.com', 'live.com',
                'ymail.com', 'zoho.com', 'yandex.com', 'gmx.com', 'fastmail.com'}

# Bing search URL
BING_URL = "https://www.bing.com/search?q={q}&count=50"

def fetch_search_results(domain):
    """Search Bing for @domain and extract results."""
    query = f"@{domain} foundation"
    url = BING_URL.format(q=urllib.parse.quote_plus(query))
    
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.bing.com/',
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        # Extract emails from search results
        emails = set()
        for m in EMAIL_RE.finditer(html):
            email = m.group(0).lower()
            if '@' not in email: continue
            
            # Skip if it's one of our search terms / Bing boilerplate
            if any(x in email for x in ['example@', 'domain.com', 'yourname', 'user@']):
                continue
            
            # Skip personal email domains
            edomain = email.split('@')[1]
            if edomain in SKIP_DOMAINS:
                continue
            
            email = email.strip('.,;:()[]{}<>"\'')
            
            # Skip if it looks like a CSS/JS injection
            if any(x in email for x in ['.png', '.jpg', '.svg', '.css', '.js', 'sentry.', 'rspack@',
                                         'react@', 'lodash@', 'webpack@', 'bundle@', 'chunk@']):
                continue
            
            email = email.strip('.,;:()[]{}<>"\'')
            
            if '@' in email and len(email) > 5:
                emails.add(email)
        
        return list(emails), query
        
    except Exception as e:
        return [], str(e)[:80]

def extract_result_links(html):
    """Extract result URLs from Bing search results page."""
    links = set()
    # Bing result links
    for m in re.finditer(r'<a[^>]*href="(https?://[^"]+)"[^>]*>', html):
        url = m.group(1)
        # Skip Bing internal links
        if any(x in url for x in ['bing.com', 'microsoft.com', 'msn.com', 'go.microsoft']):
            continue
        links.add(url)
    return list(links)

def search_foundation_emails(name, domain):
    """Search for emails related to a foundation using web search."""
    # Normalize domain
    domain = domain.lower().strip().lstrip('www.')
    
    # Generate domain variants  
    domain_variants = {domain}
    
    # Common subdomains
    for sub in ['www.', 'foundation.', 'www.foundation.']:
        domain_variants.add(sub + domain)
    
    # Try different searches
    all_emails = set()
    
    # Search 1: @domain directly
    emails, _ = fetch_search_results(domain)
    all_emails.update(emails)
    
    time.sleep(random.uniform(1.0, 2.0))
    
    # Search 2: foundation name + email
    query2 = f'"{name[:30]}" foundation email'
    url2 = BING_URL.format(q=urllib.parse.quote_plus(query2))
    
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        req = urllib.request.Request(url2, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            html2 = resp.read().decode('utf-8', errors='replace')
        
        for m in EMAIL_RE.finditer(html2):
            email = m.group(0).lower().strip('.,;:()[]{}<>"\'')
            edomain = email.split('@')[1] if '@' in email else ''
            if edomain in SKIP_DOMAINS: continue
            if len(email) > 5 and '@' in email:
                all_emails.add(email)
    except:
        pass
    
    # Filter to domain-relevant emails
    # We want emails that match the foundation's domain OR contain the foundation name
    name_words = set(name.lower().split())
    
    relevant = []
    for e in all_emails:
        edomain = e.split('@')[1]
        
        # Check if the email domain matches or is a subdomain of the foundation domain
        if edomain == domain or edomain.endswith('.' + domain):
            relevant.append(e)
            continue
        
        # Sometimes the foundation uses a completely different domain
        # Check if the email contains foundation name words
        local = e.split('@')[0].lower()
        for word in name_words:
            if len(word) > 4 and word in local:
                relevant.append(e)
                break
    
    return relevant

def main():
    import sys
    
    input_csv = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == '--input' else INPUT_CSV
    output_csv = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == '--output' else OUTPUT_CSV
    
    if not os.path.exists(input_csv):
        print(f"❌ Input file not found: {input_csv}")
        return
    
    with open(input_csv) as f:
        rows = list(csv.DictReader(f))
    
    print(f"📂 Loaded {len(rows)} foundations")
    print(f"🔍 Searching web for email addresses...")
    print()
    
    results = []
    found_count = 0
    start = datetime.now()
    
    for i, r in enumerate(rows):
        name = r.get('NAME', '')
        email = r.get('EMAIL', '').strip().lower()
        ein = r.get('EIN', '')
        
        # Get domain from existing email or generate from name
        domain = ''
        if email and '@' in email:
            domain = email.split('@')[1]
        elif r.get('DOMAIN'):
            domain = r['DOMAIN'].strip().lower()
        
        if not domain or domain in SKIP_DOMAINS:
            continue
        
        # Skip if it's a known generic domain (info@foundation.org - we already have it)
        # But still search - maybe we find a better one
        
        elapsed = (datetime.now() - start).total_seconds()
        rate = (i+1) / elapsed * 3600 if elapsed > 0 else 0
        pct = (i+1) / len(rows) * 100
        print(f"  [{i+1}/{len(rows)}] {pct:4.0f}%  {rate:.0f}/hr  {name[:40]:40s}", end='')
        
        found = search_foundation_emails(name, domain)
        
        # Filter - only keep emails that differ from the current one
        new_emails = [e for e in found if e != email]
        
        if new_emails:
            found_count += 1
            best = new_emails[0]  # First one found
            print(f"  ✅ {best}")
            results.append({
                'EIN': ein,
                'NAME': name,
                'CITY': r.get('CITY', ''),
                'STATE': r.get('STATE', ''),
                'NTEE_CD': r.get('NTEE_CD', ''),
                'ASSET_AMT': r.get('ASSET_AMT', '0'),
                'ORIGINAL_EMAIL': email,
                'FOUND_EMAILS': '; '.join(new_emails[:5]),
                'BEST_EMAIL': best,
            })
        else:
            print(f"  ❌ none")
        
        # Rate limiting - be gentle with Bing
        time.sleep(random.uniform(1.5, 3.0))
    
    print()
    print(f"{'='*60}")
    print(f"  SEARCH COMPLETE")
    print(f"{'='*60}")
    print(f"  Scanned: {len(rows)}")
    print(f"  Found new emails: {found_count}")
    print(f"  Time: {datetime.now() - start}")
    
    # Save results
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['EIN', 'NAME', 'CITY', 'STATE', 'NTEE_CD', 'ASSET_AMT', 'ORIGINAL_EMAIL', 'FOUND_EMAILS', 'BEST_EMAIL']
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)
    
    print(f"  Saved: {output_csv}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Staff Email Finder
==================
For each foundation domain, visits their website looking for staff/contact pages
and extracts real person email addresses (not generic info@).
"""
import csv
import os
import sys
import re
import time
import json
import urllib.request
import urllib.error
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

GENERIC_PREFIXES = [
    'info@', 'contact@', 'hello@', 'admin@', 'webmaster@',
    'support@', 'mail@', 'office@', 'email@', 'inquiries@',
    'ask@', 'media@', 'press@', 'donate@', 'jobs@',
    'hr@', 'careers@', 'volunteer@', 'spam@', 'noreply@',
    'feedback@', 'newsletter@', 'subscribe@', 'bounce@',
    'noreply@', 'no-reply@', 'do-not-reply@',
]

STAFF_PATHS = [
    '/team', '/staff', '/about', '/about-us', '/about/team',
    '/contact', '/contact-us', '/board', '/board-of-directors',
    '/people', '/our-team', '/our-staff', '/leadership',
    '/foundation/team', '/foundation/staff',
    '/about/leadership', '/about/staff',
    '/grantmaking', '/grants', '/programs',
    '/who-we-are', '/our-people',
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch_page(url, timeout=15):
    """Fetch a URL and return HTML text."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        html = resp.read().decode('utf-8', errors='replace')
        return html
    except Exception as e:
        return None

def extract_emails(html, domain):
    """Extract email addresses from HTML, filtering out generic ones."""
    if not html:
        return []
    
    # Find all emails
    found = set()
    for m in re.finditer(r'[\w.+-]+@[\w-]+\.\w+', html):
        email = m.group().lower().strip()
        
        # Skip generic
        if any(email.startswith(p) for p in GENERIC_PREFIXES):
            continue
        
        # Skip non-org domains (gmail, yahoo, etc)
        local, atdomain = email.split('@')
        if any(x in atdomain for x in ['gmail.com', 'yahoo.com', 'hotmail.com',
                                         'outlook.com', 'aol.com', 'icloud.com',
                                         'mail.com', 'protonmail', 'ymail.com']):
            continue
        
        # Must be reasonable length
        if len(local) < 2 or len(email) < 8:
            continue
        
        # Must look like a real name (has letters)
        if not re.search(r'[a-z]', local):
            continue
        
        # Check if it matches foundation domain
        domain_base = '.'.join(domain.split('.')[-2:]) if '.' in domain else domain
        if domain_base not in atdomain:
            continue
        
        found.add(email)
    
    return sorted(found)

def score_email(email, name=''):
    """Score email quality - prefer named individuals over role addresses."""
    local = email.split('@')[0]
    score = 0
    
    # Named individual (firstname.lastname, firstinitiallastname, etc)
    if '.' in local or '_' in local or '-' in local:
        score += 20
    
    # Role-based (grants, programs, etc)
    if any(r in local.lower() for r in ['grant', 'program', 'director', 'executive',
                                          'president', 'ceo', 'foundation']):
        score += 15
    
    # Looks like a person name (2-3 parts)
    parts = re.split(r'[._-]', local)
    if 2 <= len(parts) <= 3:
        if all(p.isalpha() and len(p) >= 2 for p in parts):
            score += 25
    
    # Bonus if name matches foundation name
    if name:
        name_parts = name.lower().split()
        for np in name_parts[:3]:
            if len(np) > 3 and np in local:
                score += 10
    
    return score

def find_staff_emails(name, domain):
    """Find real staff email addresses for a foundation."""
    all_emails = set()
    
    # Try with and without www
    bases = [f"https://www.{domain}", f"https://{domain}"]
    
    for base in bases:
        for path in STAFF_PATHS:
            url = base + path
            html = fetch_page(url)
            if html:
                emails = extract_emails(html, domain)
                all_emails.update(emails)
    
    # Score and sort
    scored = []
    for email in all_emails:
        s = score_email(email, name)
        scored.append((s, email))
    
    scored.sort(reverse=True)
    return [e for s, e in scored]

def process_foundation(name, ein, domain):
    """Process a single foundation."""
    emails = find_staff_emails(name, domain)
    
    if emails:
        best = emails[0]
        all_found = '; '.join(emails[:5])
        return {
            'EIN': ein,
            'NAME': name,
            'DOMAIN': domain,
            'STAFF_EMAIL': best,
            'ALL_EMAILS': all_found,
            'FOUND': 'YES',
        }
    else:
        return {
            'EIN': ein,
            'NAME': name,
            'DOMAIN': domain,
            'STAFF_EMAIL': '',
            'ALL_EMAILS': '',
            'FOUND': 'NO',
        }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Input CSV with EIN,NAME,DOMAIN')
    parser.add_argument('--workers', type=int, default=10)
    args = parser.parse_args()
    
    input_path = args.input
    output_path = os.path.splitext(input_path)[0] + '_staff.csv'
    
    print(f"Loading {input_path}...")
    with open(input_path) as f:
        rows = list(csv.DictReader(f))
    
    print(f"Processing {len(rows)} foundations with {args.workers} workers...")
    print(f"Time: {datetime.now().isoformat()}")
    
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_foundation, r['NAME'], r['EIN'], r['DOMAIN']): i 
                   for i, r in enumerate(rows)}
        
        done = 0
        found = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            done += 1
            if result['FOUND'] == 'YES':
                found += 1
            if done % 10 == 0:
                print(f"  Progress: {done}/{len(rows)} (found: {found})", flush=True)
    
    # Sort: found first, then by name
    results.sort(key=lambda r: (0 if r['FOUND'] == 'YES' else 1, r['NAME']))
    
    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['EIN','NAME','DOMAIN','STAFF_EMAIL','ALL_EMAILS','FOUND'])
        w.writeheader()
        w.writerows(results)
    
    print(f"\nComplete!")
    print(f"Total: {len(results)}")
    print(f"Found emails: {found}")
    print(f"Not found: {len(results) - found}")
    print(f"Output: {output_path}")

if __name__ == '__main__':
    main()

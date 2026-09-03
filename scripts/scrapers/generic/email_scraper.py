"""
Church Website Email Scraper
=============================
Scrapes church websites for email addresses by visiting contact pages,
extracting mailto: links, plain-text emails, and guessing from staff names.

Phases:
  1. Anglican/Episcopal list (102 websites) — quick test
  2. Full church list (5,582 websites) — overnight run

Usage:
  python church_email_scraper.py church_anglican_episcopal.csv church_anglican_emails.csv
  python church_email_scraper.py church_contacts.csv church_contacts_emails.csv
"""

import csv
import os
import re
import sys
import time
import random
import json
import threading
import urllib.request
import urllib.error
import socket
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Pages to try on each church website (trimmed for speed - most common only)
CONTACT_PATHS = [
    "/",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/about/contact",
    "/staff",
    "/our-staff",
    "/leadership",
    "/our-leadership",
    "/about/staff",
    "/clergy",
    "/pastor",
    "/about/clergy",
    "/connect",
    "/give",
    "/giving",
]

# Email priority for churches (higher = better)
EMAIL_PRIORITY = {
    'pastor': 10,
    'rector': 10,
    'vicar': 10,
    'minister': 9,
    'office': 9,
    'admin': 8,
    'administrator': 8,
    'contact': 7,
    'info': 6,
    'hello': 5,
    'connect': 5,
    'welcome': 5,
    'secretary': 5,
    'treasurer': 5,
    'music': 4,
    'youth': 4,
    'children': 4,
    'communications': 4,
    'webmaster': 3,
}

TIMEOUT = 8  # seconds per request
MAX_WORKERS = 12  # concurrent scrapers (t2.micro can handle ~12 max)

stats_lock = threading.Lock()
stats = {
    'scraped': 0,
    'found_email': 0,
    'no_email': 0,
    'errors': 0,
    'total': 0,
    'start_time': None,
}


def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    print(line)
    sys.stdout.flush()


def get_email_priority(email):
    """Score an email address - higher = better for churches."""
    local = email.split('@')[0].lower()
    for keyword, score in EMAIL_PRIORITY.items():
        if keyword in local:
            return score
    return 3  # default low priority


def extract_emails(html, domain):
    """Extract email addresses from HTML content."""
    emails = set()
    # mailto: links
    for m in re.finditer(r'mailto:([\w.+-]+@[\w.-]+\.\w{2,4})', html, re.IGNORECASE):
        emails.add(m.group(1).lower())
    # Plain text emails matching the domain
    domain_clean = domain.replace('www.', '')
    for m in re.finditer(r'[\w.+-]+@(?:' + re.escape(domain_clean) + ')', html, re.IGNORECASE):
        emails.add(m.group(0).lower())
    # Plain text emails with common church email providers (if domain check fails)
    for m in re.finditer(r'[\w.+-]+@[\w.-]+\.(?:org|com|net|church)', html, re.IGNORECASE):
        e = m.group(0).lower()
        # Only include if the domain contains the church domain or is a common provider
        if domain_clean in e or len(e) < 40:
            emails.add(e)
    return list(emails)


def extract_names(html, domain):
    """Look for named staff/leadership and guess their emails."""
    name_emails = set()
    
    # Pattern: Name with title
    for m in re.finditer(
        r'(pastor|rector|vicar|minister|priest|father|brother|sister|deacon|canon|bishop|'
        r'reverend|rev\.?|fr\.?|fr|dr\.?|mr\.?|mrs\.?|ms\.?)'
        r'[\s:,.]*</?(strong|b|span|div|p|h[1-6])[^>]*>[\s:,.]*'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        html, re.IGNORECASE | re.DOTALL):
        name = m.group(3).strip()
        name_emails.update(guess_emails_from_name(name, domain))
    
    # Pattern: Name, Title (e.g. "John Smith, Pastor")
    for m in re.finditer(
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})[\s,]+(?:pastor|rector|vicar|minister|priest|'
        r'deacon|canon|bishop|executive director|director|administrator|'
        r'office manager|secretary|treasurer|chairman|president)',
        html, re.IGNORECASE):
        name = m.group(1).strip()
        name_emails.update(guess_emails_from_name(name, domain))
    
    # Pattern: Staff/Team section headers
    for m in re.finditer(
        r'(staff|team|clergy|leadership|vestry|board|officers|ministry)'
        r'[\s:,]*</?(h[1-6]|div|span|strong|b)[^>]*>[\s:,]*'
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        html, re.IGNORECASE | re.DOTALL):
        name = m.group(3).strip()
        name_emails.update(guess_emails_from_name(name, domain))
    
    return list(name_emails)


def guess_emails_from_name(name, domain):
    """Generate probable email addresses from a person's name."""
    guesses = set()
    parts = name.strip().lower().split()
    if len(parts) < 2:
        return guesses
    
    first = parts[0]
    last = parts[-1]
    fi = first[0]
    
    patterns = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}",
        f"{fi}{last}@{domain}",
        f"{first}_{last}@{domain}",
        f"{first}-{last}@{domain}",
        f"{fi}.{last}@{domain}",
        f"{last}.{first}@{domain}",
        f"{first}{last[0]}@{domain}",
        f"{last}@{domain}",
        f"{fi}{last[0]}@{domain}",
    ]
    
    for p in patterns:
        username = p.split('@')[0]
        if len(username) >= 2 and not any(x in username for x in ['click', 'mailto', 'http']):
            guesses.add(p)
    
    return guesses


def fetch_page(url):
    """Fetch a URL and return HTML content."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            content = r.read().decode('utf-8', errors='replace')
            return content
    except Exception:
        return None


def scrape_church(name, website_url):
    """Scrape a church's website for email addresses."""
    if not website_url or not website_url.strip():
        return None, None
    
    url = website_url.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    # Extract domain from URL
    domain = url.split('://')[1].split('/')[0].lower()
    domain = domain.replace('www.', '')
    
    all_emails = {}
    
    for path in CONTACT_PATHS:
        page_url = url.rstrip('/') + path
        html = fetch_page(page_url)
        if not html:
            continue
        
        # Extract actual emails
        emails = extract_emails(html, domain)
        for email in emails:
            priority = get_email_priority(email)
            if email not in all_emails or priority > all_emails[email][0]:
                all_emails[email] = (priority, page_url)
        
        # Extract names and guess their emails
        name_emails = extract_names(html, domain)
        for email in name_emails:
            if email not in all_emails:
                all_emails[email] = (5, page_url + " (guess)")
        
        # If we found a high-priority email, stop looking
        if any(get_email_priority(e) >= 9 for e in emails):
            break
        
        time.sleep(random.uniform(0.2, 0.5))
    
    if all_emails:
        best_email = max(all_emails.items(), key=lambda x: x[1][0])
        return best_email[0], best_email[1][1]
    return None, None


def process_church(row, website_col=6):
    """Process one church row."""
    name = row[0]  # church_name
    website = row[website_col] if len(row) > website_col else ''
    
    if not website or not website.strip():
        with stats_lock:
            stats['no_email'] += 1
            stats['scraped'] += 1
        return None
    
    email, source = scrape_church(name, website)
    
    with stats_lock:
        stats['scraped'] += 1
        if email:
            stats['found_email'] += 1
        else:
            stats['no_email'] += 1
    
    return (name, website, email or '', source or '')


def progress_printer():
    """Background thread prints progress."""
    while not progress_done:
        time.sleep(5)
        with stats_lock:
            s = dict(stats)
        elapsed = (datetime.now() - s.get('start_time', datetime.now())).total_seconds()
        rate = s['scraped'] / elapsed * 3600 if elapsed > 0 else 0
        total = s['total']
        pct = s['scraped'] / total * 100 if total > 0 else 0
        
        bar = '█' * int(pct / 4) + '░' * (25 - int(pct / 4))
        log(f"[{pct:5.1f}%] {bar} {s['scraped']}/{total} "
            f"| Found: {s['found_email']} | No: {s['no_email']} | Err: {s['errors']} "
            f"| {rate:.0f}/hr")


def main():
    if len(sys.argv) < 2:
        print("Usage: python church_email_scraper.py <input.csv> [output.csv] [--anglican]")
        print()
        print("Examples:")
        print("  python church_email_scraper.py church_anglican_episcopal.csv --anglican")
        print("  python church_email_scraper.py church_contacts.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    is_anglican = '--anglican' in sys.argv or 'anglican' in input_file
    
    # Default output name
    if len(sys.argv) >= 3 and not sys.argv[2].startswith('--'):
        output_file = sys.argv[2]
    else:
        base = os.path.splitext(input_file)[0]
        output_file = base + "_emails.csv"
    
    input_path = os.path.join(SCRIPT_DIR, input_file) if not os.path.isabs(input_file) else input_file
    output_path = os.path.join(SCRIPT_DIR, output_file) if not os.path.isabs(output_file) else output_file
    
    if not os.path.exists(input_path):
        # Try EC2 path
        input_path2 = os.path.join('/home/ubuntu/grantwizard', input_file)
        if os.path.exists(input_path2):
            input_path = input_path2
            output_path = os.path.join('/home/ubuntu/grantwizard', output_file)
        else:
            print(f"ERROR: {input_path} not found")
            sys.exit(1)
    
    # Load CSV
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    
    # Determine website column
    header_lower = [h.lower().strip() for h in header]
    try:
        website_col = header_lower.index('website')
    except ValueError:
        print(f"ERROR: No 'website' column found in {header}")
        sys.exit(1)
    
    # Filter to rows with websites
    with_websites = [r for r in rows if len(r) > website_col and r[website_col].strip()]
    
    log(f"Loaded {len(rows)} churches from {input_file}")
    log(f"With websites: {len(with_websites)}")
    
    global progress_done
    progress_done = False
    
    stats['start_time'] = datetime.now()
    stats['total'] = len(with_websites)
    
    # Load progress file
    progress_file = output_path + ".progress.json"
    processed_urls = set()
    if os.path.exists(progress_file):
        try:
            with open(progress_file) as f:
                processed_urls = set(json.load(f))
            log(f"Resuming: {len(processed_urls)} already processed")
        except:
            pass
    
    # Filter already processed
    remaining = [r for r in with_websites if r[website_col].strip() not in processed_urls]
    log(f"Remaining to scrape: {len(remaining)}")
    
    # Open output
    out_exists = os.path.exists(output_path)
    out_f = open(output_path, 'a', newline='', encoding='utf-8')
    writer = csv.writer(out_f)
    
    if not out_exists:
        writer.writerow(['church_name', 'website', 'email', 'source_url'])
    
    # Start progress thread
    pt = threading.Thread(target=progress_printer, daemon=True)
    pt.start()
    
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {}
        for r in remaining:
            url = r[website_col].strip()
            if url in processed_urls:
                continue
            fut = ex.submit(process_church, r, website_col)
            futures[fut] = (r, url)
        
        try:
            for i, fut in enumerate(as_completed(futures)):
                result = fut.result()
                if result:
                    writer.writerow(result)
                    out_f.flush()
                
                # Save progress
                _, url = futures[fut]
                processed_urls.add(url)
                if (i + 1) % 25 == 0:
                    with open(progress_file, 'w') as f:
                        json.dump(list(processed_urls), f)
                
                results.append(result)
                
        except KeyboardInterrupt:
            log("\nInterrupted! Saving progress...")
            with open(progress_file, 'w') as f:
                json.dump(list(processed_urls), f)
    
    progress_done = True
    out_f.close()
    
    elapsed = (datetime.now() - stats['start_time']).total_seconds()
    log(f"\n{'='*60}")
    log(f"  DONE! ({str(timedelta(seconds=int(elapsed)))})")
    log(f"  Processed: {stats['scraped']}")
    log(f"  Found emails: {stats['found_email']}")
    log(f"  No email found: {stats['no_email']}")
    log(f"  Errors: {stats['errors']}")
    log(f"  Output: {output_path}")
    log(f"{'='*60}")


if __name__ == '__main__':
    progress_done = False
    main()

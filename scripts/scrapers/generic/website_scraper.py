"""
Foundation Website Scraper
===========================
For each DNS-verified foundation domain, visits the website and scrapes:
1. The homepage for email addresses
2. Common contact/grants pages
3. Returns the best-found email (preferring grants@, apply@ over info@)

Output: scraped_contacts.csv with real scraped emails
"""

import csv
import os
import sys
import re
import time
import random
import threading
import urllib.request
import urllib.error
import socket
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "scraped_contacts.csv")

# Pages to try on each foundation's website
CONTACT_PATHS = [
    "/",
    "/contact",
    "/contact-us",
    "/grants",
    "/grant-seekers",
    "/apply",
    "/apply-for-a-grant",
    "/for-grant-seekers",
    "/about",
    "/about-us",
    "/about/contact",
    "/foundation/contact",
    "/contact/grants",
    "/programs",
    "/how-to-apply",
    "/guidelines",
    # Press releases (often contain contact info)
    "/news",
    "/press",
    "/press-release",
    "/press-releases",
    "/newsroom",
    "/media",
    "/in-the-news",
    "/announcements",
    "/blog",
    "/updates",
]

# Email priority score (higher = better)
EMAIL_PRIORITY = {
    'grants': 10,
    'apply': 9,
    'proposals': 9,
    'program': 8,
    'giving': 7,
    'foundation': 6,
    'contact': 5,
    'info': 4,
    'hello': 3,
    'admin': 3,
    'office': 2,
}

TIMEOUT = 8  # seconds per request
MAX_WORKERS = 20  # concurrent scrapers

# Stats
stats_lock = threading.Lock()
stats = {'scraped': 0, 'found_better': 0, 'errors': 0, 'no_change': 0, 'total': 0}
_contact_email_cache = {}

# Dashboard
class Dashboard:
    def __init__(self):
        self.start = datetime.now()
    
    def render(self):
        with stats_lock:
            elapsed = (datetime.now() - self.start).total_seconds()
            rate = stats['scraped'] / elapsed * 3600 if elapsed > 0 else 0
            total = stats.get('total', 1)
            pct = min(stats['scraped'] / total * 100, 100) if total > 0 else 0
            bar_w = 30
            filled = int(bar_w * pct / 100)
            bar = '█' * filled + '░' * (bar_w - filled)
            
            lines = []
            lines.append(f"\033[2J\033[H")
            lines.append(f"  ╔{'═'*56}╗")
            lines.append(f"  ║    🌐  WEBSITE SCRAPER — Finding Real Emails      ║")
            lines.append(f"  ╚{'═'*56}╝")
            lines.append(f"")
            lines.append(f"  {bar}  {pct:.1f}%")
            lines.append(f"  📨 Scraped: {stats['scraped']:,}/{total:,}  ⚡ {rate:.0f}/hr  ⏱️ {str(timedelta(seconds=int(elapsed)))}")
            lines.append(f"  ✅ Better emails: {stats['found_better']:,}  ❌ No change: {stats['no_change']:,}  ⚠️ Errors: {stats['errors']:,}")
            lines.append(f"")
            sys.stdout.write('\n'.join(lines))
            sys.stdout.flush()
    
    def run(self):
        try:
            while True:
                self.render()
                time.sleep(5)
        except:
            pass

dashboard = Dashboard()

def get_email_priority(email):
    """Score an email address by how likely it is to reach the right person."""
    prefix = email.split('@')[0].lower()
    return EMAIL_PRIORITY.get(prefix, 1)

def extract_emails(html, domain):
    """Extract email addresses from HTML content."""
    emails = set()
    # Find mailto: links
    for m in re.finditer(r'mailto:([\w.+-]+@[\w.-]+\.\w{2,4})', html, re.IGNORECASE):
        emails.add(m.group(1).lower())
    # Find plain text emails
    for m in re.finditer(r'[\w.+-]+@(?:' + re.escape(domain) + r'|' + re.escape(domain.replace('www.','')) + r')', html, re.IGNORECASE):
        emails.add(m.group(0).lower())
    return list(emails)
# ── NEW: Name-based email guessing ────────────────────────────

ROLE_TITLES = [
    "executive director", "director", "president", "ceo", "executive",
    "chairman", "chair", "trustee", "secretary", "treasurer",
    "founder", "manager", "administrator", "coordinator",
    "development", "program officer", "grant", "finance",
    "vp", "vice president", "chief", "officer", "board member",
]

def extract_names(html, domain):
    """
    Look for named people (titles + names) in HTML, then generate
    email guesses from those names.
    """
    name_emails = set()
    
    # Pattern 1: "Title: Name" or "Title</strong> Name"
    for m in re.finditer(r'(executive\s+director|director|president|ceo|chairman|trustee|secretary|treasurer|founder|manager|administrator|vp|vice\s+president|board\s+member|program\s+officer|grant\s+manager)'
                         r'[\s:,]*</?(strong|b|span|div)[^>]*>[\s:,]*'
                         r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                         html, re.IGNORECASE | re.DOTALL):
        name = m.group(3).strip()
        name_emails.update(guess_emails_from_name(name, domain))
    
    # Pattern 2: Name, Title (e.g. "John Smith, Executive Director")
    for m in re.finditer(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)[\s,]+(?:executive\s+director|director|president|ceo|chairman|trustee|secretary|treasurer|founder|manager|administrator|vp|vice\s+president)',
                         html, re.IGNORECASE):
        name = m.group(1).strip()
        name_emails.update(guess_emails_from_name(name, domain))
    
    # Pattern 3: "By: Name" or "Contact: Name" in staff sections
    for m in re.finditer(r'(staff|team|people|board|officers|leadership|contact)[\s:,]*</?(h[1-6]|div|span|strong|b)[^>]*>[\s:,]*'
                         r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                         html, re.IGNORECASE | re.DOTALL):
        name = m.group(3).strip()
        name_emails.update(guess_emails_from_name(name, domain))
    
    return list(name_emails)

def guess_emails_from_name(name, domain):
    """Generate email guesses from a person's name and domain."""
    guesses = set()
    parts = name.strip().lower().split()
    if len(parts) < 2:
        return guesses
    
    first = parts[0]
    last = parts[-1]
    first_initial = first[0]
    
    # Common email patterns
    patterns = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}",
        f"{first_initial}{last}@{domain}",
        f"{first}_{last}@{domain}",
        f"{first}-{last}@{domain}",
        f"{first[0]}.{last}@{domain}",
        f"{last}.{first}@{domain}",
        f"{first}{last[0]}@{domain}",
        f"{last}@{domain}",
        f"{first[0]}{last[0]}@{domain}",
    ]
    
    for p in patterns:
        if len(p.split('@')[0]) >= 2:  # Username at least 2 chars
            guesses.add(p)
    
    return guesses
def fetch_page(url, domain):
    """Fetch a URL and return HTML content."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            content = r.read().decode('utf-8', errors='replace')
            return content
    except Exception:
        return None

def scrape_foundation(name, domain):
    """Scrape a foundation's website for better email addresses."""
    global stats
    
    # Normalize domain
    domain = domain.lower().strip()
    if domain.startswith('http://') or domain.startswith('https://'):
        domain = domain.split('://')[1].split('/')[0]
    
    base_url = 'https://' + domain
    all_emails = {}
    
    # Try pages in order - stop if we find a high-priority email
    for path in CONTACT_PATHS:
        url = base_url + path
        html = fetch_page(url, domain)
        if not html:
            continue
        
        # Extract actual emails
        emails = extract_emails(html, domain)
        for email in emails:
            priority = get_email_priority(email)
            if email not in all_emails or priority > all_emails[email][0]:
                all_emails[email] = (priority, url)
        
        # Extract names and guess their emails
        name_emails = extract_names(html, domain)
        for email in name_emails:
            # Name-guessed emails get medium priority (5)
            if email not in all_emails:
                all_emails[email] = (5, url + " (name-guessed)")
        
        # If we found grants/apply/proposals, stop digging
        found_high = any(get_email_priority(e) >= 7 for e in emails)
        if found_high:
            break
        
        # Polite delay between pages
        time.sleep(random.uniform(0.3, 0.8))
    
    # Return best email
    if all_emails:
        best_email = max(all_emails.items(), key=lambda x: x[1][0])
        return best_email[0], best_email[1][1]  # email, source_url
    return None, None

def process_row(row):
    """Process one foundation row."""
    global stats
    
    name = row['NAME']
    current_email = row['EMAIL']
    domain = row.get('DOMAIN', '')
    
    if not current_email and not domain:
        with stats_lock:
            stats['no_change'] += 1
        return None
    
    # Extract domain from current email if needed
    if not domain and current_email:
        domain = current_email.split('@')[1] if '@' in current_email else ''
    
    if not domain:
        with stats_lock:
            stats['no_change'] += 1
        return None
    
    with stats_lock:
        stats['scraped'] += 1
    
    # Scrape the website
    found_email, source_url = scrape_foundation(name, domain)
    
    result = {
        'EIN': row['EIN'],
        'NAME': name,
        'CITY': row.get('CITY', ''),
        'STATE': row.get('STATE', ''),
        'ASSET_AMT': row.get('ASSET_AMT', ''),
        'NTEE_CD': row.get('NTEE_CD', ''),
        'ORIGINAL_EMAIL': current_email or '',
        'SCRAPED_EMAIL': found_email or '',
        'SOURCE_URL': source_url or '',
        'DOMAIN': domain,
    }
    
    with stats_lock:
        if found_email and get_email_priority(found_email) > get_email_priority(current_email or ''):
            stats['found_better'] += 1
        elif found_email:
            stats['no_change'] += 1
        else:
            stats['errors'] += 1
    
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape foundation websites for real emails")
    parser.add_argument("--quick", type=int, default=0, nargs='?', const=100,
                        help="Only scrape first N foundations")
    parser.add_argument("--input", type=str, default=None,
                        help="Custom input CSV (default: enriched_contacts.csv)")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS,
                        help=f"Concurrent scrapers (default: {MAX_WORKERS})")
    args = parser.parse_args()
    
    # Use custom input file if provided
    input_csv = args.input if args.input else INPUT_CSV
    output_csv = OUTPUT_CSV
    if args.input:
        base = os.path.splitext(args.input)[0]
        output_csv = base + "_scraped.csv"
    
    max_workers = args.workers
    
    print("=" * 70)
    print("  FOUNDATION WEBSITE SCRAPER")
    print("  Visits each foundation's website to find real contact emails")
    print("=" * 70)
    
    # Load
    print(f"\nLoading {input_csv}...")
    with open(input_csv, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    if args.quick:
        rows = rows[:args.quick]
    
    with stats_lock:
        stats['total'] = len(rows)
    
    print(f"  {len(rows):,} foundations loaded")
    print(f"  {sum(1 for r in rows if r['EMAIL']):,} with DNS emails")
    
    # Start dashboard thread
    import threading as t
    dash_thread = t.Thread(target=dashboard.run, daemon=True)
    dash_thread.start()
    dashboard.start = datetime.now()
    
    # Process
    print(f"\nScraping with {max_workers} concurrent workers...")
    print("  Dashboard will update every 5s")
    sys.stdout.flush()
    time.sleep(2)
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_row, r): i for i, r in enumerate(rows)}
        
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
            completed += 1
    
    # Write output
    print(f"\n\nWriting {output_csv}...")
    fieldnames = ['EIN', 'NAME', 'CITY', 'STATE', 'ASSET_AMT', 'NTEE_CD',
                  'EMAIL', 'SOURCE', 'DOMAIN', 'SCRAPED_EMAIL', 'SOURCE_URL']
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        
        # Merge scraped results with original data
        scraped_map = {r['EIN']: r for r in results if r}
        
        for row in rows:
            ein = row['EIN']
            out = {
                'EIN': ein,
                'NAME': row.get('NAME', ''),
                'CITY': row.get('CITY', ''),
                'STATE': row.get('STATE', ''),
                'ASSET_AMT': row.get('ASSET_AMT', ''),
                'NTEE_CD': row.get('NTEE_CD', ''),
                'EMAIL': row.get('EMAIL', ''),
                'SOURCE': 'dns',
                'DOMAIN': row.get('DOMAIN', ''),
                'SCRAPED_EMAIL': '',
                'SOURCE_URL': '',
            }
            
            if ein in scraped_map:
                sr = scraped_map[ein]
                scraped_email = sr.get('SCRAPED_EMAIL', '')
                if scraped_email:
                    out['SCRAPED_EMAIL'] = scraped_email
                    out['SOURCE_URL'] = sr.get('SOURCE_URL', '')
                    # If scraped email is better, upgrade
                    if get_email_priority(scraped_email) > get_email_priority(out['EMAIL']):
                        out['EMAIL'] = scraped_email
                        out['SOURCE'] = 'scraped'
            
            w.writerow(out)
    
    print(f"\n{'=' * 60}")
    with stats_lock:
        print(f"  COMPLETE")
        print(f"  Websites scraped: {stats['scraped']:,}")
        print(f"  Better emails found: {stats['found_better']:,}")
        print(f"  No improvement: {stats['no_change']:,}")
        print(f"  Errors/timeouts: {stats['errors']:,}")
    print(f"  Output: {OUTPUT_CSV}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()

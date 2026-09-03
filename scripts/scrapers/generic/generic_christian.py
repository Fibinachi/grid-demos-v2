"""
Christian Directory Scraper
===========================
Scrapes Christian business directories and religious organization websites
for contact email addresses. Targets:
  1. Christian business directories (christianbusinessdirectory.com, etc.)
  2. IRS X (Religion) and B (Education) codes from existing data

Usage:
  python christian_scraper.py                          # Full run
  python christian_scraper.py --irs-only              # IRS data only
  python christian_scraper.py --dirs-only             # Directories only
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
import urllib.parse
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "christian_contacts.csv")

stats_lock = threading.Lock()
stats = {'scraped': 0, 'found': 0, 'errors': 0}

# -- DASHBOARD --
class Dashboard:
    def __init__(self):
        self.start = datetime.now()
        self.total = 1

    def render(self):
        with stats_lock:
            elapsed = (datetime.now() - self.start).total_seconds()
            rate = stats['scraped'] / elapsed * 3600 if elapsed > 0 else 0
            pct = min(stats['scraped'] / self.total * 100, 100)
            bar_w = 30
            filled = int(bar_w * pct / 100)
            bar = '#' * filled + '.' * (bar_w - filled)

            sys.stdout.write("\033[2J\033[H")
            sys.stdout.write("  +" + "="*56 + "+\n")
            sys.stdout.write("  |   CHRISTIAN OUTREACH SCRAPER                |\n")
            sys.stdout.write("  +" + "="*56 + "+\n\n")
            sys.stdout.write("  [%s]  %.1f%%\n" % (bar, pct))
            sys.stdout.write("  Scraped: %d/%d  Rate: %.0f/hr  Elapsed: %s\n" % (
                stats['scraped'], self.total, rate, str(timedelta(seconds=int(elapsed)))))
            sys.stdout.write("  Found: %d  Errors: %d\n" % (stats['found'], stats['errors']))
            sys.stdout.write("\n")
            sys.stdout.flush()

    def run(self):
        try:
            while True:
                self.render()
                time.sleep(5)
        except:
            pass

dashboard = Dashboard()

# -- FETCH --
def fetch_page(url, timeout=10):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except:
        return None

def extract_emails(html, domain):
    emails = set()
    for m in re.finditer(r'mailto:([\w.+-]+@[\w.-]+\.\w{2,4})', html, re.IGNORECASE):
        emails.add(m.group(1).lower())
    for m in re.finditer(r'[\w.+-]+@[\w.-]+\.\w{2,4}', html, re.IGNORECASE):
        emails.add(m.group(0).lower())
    return list(emails)

# -- DIRECTORY 1: Christian Business Directory --
def scrape_cbd_pages():
    """Scrape christianbusinessdirectory.com listings."""
    found = []
    base = "https://christianbusinessdirectory.com"

    html = fetch_page(base, timeout=15)
    if not html:
        return found

    cats = re.findall(r'href="(/category/[^"]+)"', html)
    cats = list(set(cats))[:10]

    for cat in cats[:5]:
        url = base + cat
        html = fetch_page(url, timeout=10)
        if not html:
            continue

        emails = extract_emails(html, "christianbusinessdirectory.com")
        for e in emails:
            found.append((e, url, "Christian Business Directory"))

        biz_links = re.findall(r'href="(https?://[^"]+)"', html)
        for biz_url in biz_links[:20]:
            if 'christianbusinessdirectory' not in biz_url:
                biz_html = fetch_page(biz_url, timeout=8)
                if biz_html:
                    biz_emails = extract_emails(biz_html, re.findall(r'https?://([^/]+)', biz_url)[0] if re.findall(r'https?://([^/]+)', biz_url) else "")
                    for e in biz_emails:
                        if 'example' not in e and 'test' not in e:
                            found.append((e, biz_url, "Christian Business"))
                time.sleep(random.uniform(0.5, 1.5))

        time.sleep(random.uniform(1, 2))

    return found

# -- DIRECTORY 2: Christian Chamber of Commerce --
def scrape_christian_chamber():
    """Scrape christianchamber.com member directory."""
    found = []
    base = "https://christianchamber.com"

    paths = ["/members", "/directory", "/member-directory", "/businesses"]
    for path in paths:
        html = fetch_page(base + path, timeout=10)
        if html:
            emails = extract_emails(html, "christianchamber.com")
            for e in emails:
                found.append((e, base + path, "Christian Chamber"))

            member_links = re.findall(r'href="([^"]*member[^"]*)"', html, re.IGNORECASE) + \
                           re.findall(r'href="([^"]*business[^"]*)"', html, re.IGNORECASE)
            for m_url in list(set(member_links))[:15]:
                if not m_url.startswith('http'):
                    m_url = base + m_url
                m_html = fetch_page(m_url, timeout=8)
                if m_html:
                    m_emails = extract_emails(m_html, re.findall(r'https?://([^/]+)', m_url)[0] if re.findall(r'https?://([^/]+)', m_url) else "")
                    for e in m_emails:
                        found.append((e, m_url, "Christian Chamber Member"))
                time.sleep(random.uniform(0.5, 1))
        time.sleep(1)

    return found

# -- DIRECTORY 3: Christian Business Network --
def scrape_cbn():
    """Scrape christianbusinessnetwork.com."""
    found = []
    base = "https://christianbusinessnetwork.com"
    paths = ["/members", "/directory", "/business-directory", "/listings"]

    for path in paths:
        html = fetch_page(base + path, timeout=10)
        if html:
            emails = extract_emails(html, "christianbusinessnetwork.com")
            for e in emails:
                found.append((e, base + path, "Christian Business Network"))

            member_links = re.findall(r'href="([^"]+)"', html)
            for link in member_links[:15]:
                if link.startswith('/') and link != path:
                    m_html = fetch_page(base + link, timeout=8)
                    if m_html:
                        m_emails = extract_emails(m_html, "")
                        for e in m_emails:
                            found.append((e, base + link, "CBN Member"))
                    time.sleep(random.uniform(0.3, 0.8))
        time.sleep(1)

    return found

# -- IRS DATA: X and B codes --
def extract_irs_religious():
    """Extract X (Religion) and B (Education) orgs from IRS data."""
    csv_path = os.path.join(SCRIPT_DIR, "private_foundations_clean.csv")
    if not os.path.exists(csv_path):
        print("  private_foundations_clean.csv not found")
        return []

    with open(csv_path, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    targets = []
    for r in rows:
        code = r.get('NTEE_CD', '').strip()
        if code.startswith('X') or code.startswith('B'):
            targets.append({
                'EIN': r.get('EIN', '').strip(),
                'NAME': r.get('NAME', '').strip(),
                'CITY': r.get('CITY', '').strip(),
                'STATE': r.get('STATE', '').strip(),
                'NTEE_CD': code,
                'ASSET_AMT': r.get('ASSET_AMT', '').strip(),
                'SOURCE': 'irs_xb_codes'
            })

    return targets

# -- MAIN --
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Christian outreach contact scraper")
    parser.add_argument("--irs-only", action="store_true",
                        help="Only process IRS X/B codes")
    parser.add_argument("--dirs-only", action="store_true",
                        help="Only scrape directories")
    args = parser.parse_args()

    all_contacts = []

    # Phase 1: IRS Data
    if not args.dirs_only:
        print("\n  Phase 1: Extracting IRS X/B code organizations...")
        irs_contacts = extract_irs_religious()
        total = len(irs_contacts)
        print("  %d religious/education organizations extracted" % len(irs_contacts))

        with stats_lock:
            stats['scraped'] = len(irs_contacts)
            stats['found'] = sum(1 for c in irs_contacts if c.get('NAME'))

        all_contacts.extend(irs_contacts)

    # Phase 2: Directory scraping
    if not args.irs_only:
        print("\n  Phase 2: Scraping Christian business directories...")

        dashboard.total = 3
        dash_thread = threading.Thread(target=dashboard.run, daemon=True)
        dash_thread.start()
        dashboard.start = datetime.now()

        with stats_lock:
            stats['scraped'] = 0

        scrapers = [
            ("Christian Business Directory", scrape_cbd_pages),
            ("Christian Chamber of Commerce", scrape_christian_chamber),
            ("Christian Business Network", scrape_cbn),
        ]

        for name, scraper in scrapers:
            print("  Scraping %s..." % name)
            sys.stdout.flush()
            try:
                results = scraper()
                for email, url, source in results:
                    all_contacts.append({
                        'EIN': '',
                        'NAME': source,
                        'CITY': '',
                        'STATE': '',
                        'NTEE_CD': '',
                        'ASSET_AMT': '',
                        'EMAIL': email,
                        'SOURCE_URL': url,
                        'SOURCE': 'directory_' + name.lower().replace(" ","_")
                    })
                print("    Found %d emails from %s" % (len(results), name))
            except Exception as e:
                print("    Error: %s" % str(e)[:80])

            with stats_lock:
                stats['scraped'] += 1

        with stats_lock:
            stats['found'] = sum(1 for c in all_contacts if c.get('EMAIL'))

    # Write output
    print("\n  Writing %s..." % OUTPUT_CSV)
    fieldnames = ['EIN', 'NAME', 'CITY', 'STATE', 'NTEE_CD', 'ASSET_AMT',
                  'EMAIL', 'SOURCE_URL', 'SOURCE']

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for c in all_contacts:
            w.writerow(c)

    with_emails = sum(1 for c in all_contacts if c.get('EMAIL'))

    print("\n" + "="*60)
    print("  CHRISTIAN OUTREACH COMPLETE")
    print("  Total contacts: %d" % len(all_contacts))
    print("  With emails: %d" % with_emails)
    print("  Output: %s" % OUTPUT_CSV)
    print("="*60)

if __name__ == '__main__':
    main()

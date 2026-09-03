"""
Church Directory Scraper - USA Churches Catalog
================================================
Scrapes usachurches.org to build a comprehensive directory of churches
organized by denomination and faith tradition.

Outputs:
  church_denomination_catalog.csv  - Summary by denomination (sorted)
  church_contacts.csv              - Individual church contact details
  church_anglican_episcopal.csv    - Anglican/Episcopal only (targeted)

For Anglican/Episcopal churches, the email template will explicitly
mention the Certificate in Theology (PhD feeder track) at Trinity College, University of Toronto.

Usage:
  python church_directory_scraper.py                 # Full scrape
  python church_directory_scraper.py --catalog-only  # Just denomination list
  python church_directory_scraper.py --anglican-only # Anglican/Episcopal only
  python church_directory_scraper.py --state CA      # Single state
"""

import csv
import os
import sys
import re
import time
import random
import threading
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_CSV = os.path.join(SCRIPT_DIR, "church_denomination_catalog.csv")
CONTACTS_CSV = os.path.join(SCRIPT_DIR, "church_contacts.csv")
ANGLICAN_CSV = os.path.join(SCRIPT_DIR, "church_anglican_episcopal.csv")

BASE = "https://www.usachurches.org"

stats_lock = threading.Lock()
scrape_stats = {'families': 0, 'denominations': 0, 'churches': 0, 'pages': 0, 'errors': 0, 'contacts': 0}

# ── HELPER ──
def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None

def extract_phone(html):
    phones = re.findall(r'\b\(\d{3}\)\s*\d{3}[-.]\d{4}\b', html)
    return phones[0] if phones else ''

def extract_website(html):
    m = re.search(r'<a[^>]*href="(https?://[^"]+)"[^>]*>\s*(?:Visit|Website|www\.)', html, re.IGNORECASE)
    if m:
        return m.group(1).rstrip('/')
    return ''

def slugify(text):
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    return s

# ── DENOMINATION FAMILIES ──
FAMILIES = {
    'adventist': 'Adventist Churches',
    'baptist': 'Baptist Churches',
    'brethren': 'Brethren Churches',
    'catholic': 'Catholic Churches',
    'christian-restorationist': 'Christian and Restorationist Churches',
    'congregational': 'Congregational Churches',
    'episcopal-anglican': 'Episcopal and Anglican Churches',
    'friends-quaker': 'Friends (Quaker) Churches',
    'fundamentalist-bible': 'Fundamentalist and Bible Churches',
    'holiness': 'Holiness Churches',
    'lutheran': 'Lutheran Churches',
    'mennonite': 'Mennonite Churches',
    'methodist': 'Methodist Churches',
    'pentecostal': 'Pentecostal Churches',
    'presbyterian': 'Presbyterian Churches',
    'reformed': 'Reformed Churches',
    'orthodox': 'Orthodox Churches',
    'other': 'Other Churches'
}

# ── STEP 1: Get denominations for each family ──
def get_denominations(family_slug, family_name):
    """Scrape a denomination family page and return list of (name, info_url, listing_url)."""
    url = BASE + "/" + family_slug + ".htm"
    html = fetch(url)
    if not html:
        print("    Could not fetch %s" % url)
        return []

    denoms = []
    # Find denomination links in the content area
    # Pattern: <li><a href="denomination/{slug}.htm">{name}</a></li>
    for m in re.finditer(r'<li>\s*<a\s+href="(denomination/([^"]+))">([^<]+)</a>', html):
        denom_url = BASE + "/" + m.group(1)
        denom_slug = m.group(2).replace('.htm', '')
        denom_name = m.group(3).strip()

        # Construct listing URL: /christian/{family}/{slug}/
        listing_url = BASE + "/christian/" + family_slug + "/" + denom_slug + "/"

        denoms.append((denom_name, denom_url, listing_url))

    return denoms

# ── STEP 2: Get church count from listing page ──
def get_church_listing_info(listing_url):
    """Get the total count and first page of church listings."""
    html = fetch(listing_url)
    if not html:
        return 0, []

    # Extract count from "Showing 1-20 of X church listings"
    # HTML: Showing&nbsp;1-20 of <b><font color="#990000">105 </font></b>church listings
    count = 0
    m = re.search(r'(\d[\d,]*)\s*(?:&nbsp;)?\s*(?:</\w+>)?\s*(?:</\w+>)?\s*(?:&nbsp;)?\s*church\s*listings', html, re.IGNORECASE)
    if m:
        count = int(m.group(1).replace(',', ''))
    else:
        # Fallback: count church links on the page
        church_links = re.findall(r'href="[^"]*/church/([a-zA-Z0-9_.-]+)"', html)
        count = len(set(church_links))

    # Extract church entries from this page
    churches = []
    
    # Find church links with their surrounding context
    # HTML structure: <a href="church/slug">Church Name</a>Size: ...<br>Address, ST ZIP
    seen_urls = set()
    for m in re.finditer(
        r'<a\s+href="[^"]*/church/([a-zA-Z0-9_.-]+)"[^>]*>\s*([^<]+?)\s*</a>',
        html
    ):
        slug = m.group(1)  # Keep .htm extension
        church_url = BASE + '/church/' + slug
        if church_url in seen_urls:
            continue
        seen_urls.add(church_url)
        church_name = m.group(2).strip()
        
        # Extract size from context after the link
        start = m.end()
        context = html[start:start+500]
        size_match = re.search(r'(Mega|Large|Medium|Small)\s*church', context, re.IGNORECASE)
        size_info = size_match.group(1) if size_match else ''
        
        # Extract address - look for "City, ST" pattern
        addr_match = re.search(r'([A-Z][a-zA-Z .-]+?),\s*([A-Z]{2})(?:\s*(\d{5}))?', context)
        city_state = ''
        if addr_match:
            city_state = (addr_match.group(1).strip() + ', ' + addr_match.group(2)).strip()
        
        churches.append((church_name, church_url, size_info, city_state))

    return count, churches

# ── STEP 3: Scrape individual church page ──
def scrape_church_page(church_url):
    """Scrape individual church page for contact info."""
    html = fetch(church_url, timeout=10)
    if not html:
        return {}

    info = {}

    # Denomination - look for denomination link in the page
    m = re.search(r'<a\s+href="(?:/)?denomination/([^"]+)"[^>]*>([^<]+)</a>', html)
    if m:
        info['denomination'] = m.group(2).strip()

    # Address
    m = re.search(r'(\d+\s+[^<]+),\s*([A-Z]{2})\s*(\d{5})', html)
    if m:
        info['address'] = m.group(0).strip()
        info['city_state'] = m.group(1).strip() + ', ' + m.group(2).strip()
        info['zip'] = m.group(3).strip()

    # Phone
    m = re.search(r'\(\d{3}\)\s*\d{3}[-.]\d{4}', html)
    if m:
        info['phone'] = m.group(0).strip()

    # Website - find last non-social external link
    all_links = re.findall(r'href="(https?://([^"]+))"', html)
    for link_url, domain in reversed(all_links):
        domain = domain.lower()
        if any(s in domain for s in ['usachurches.org', 'google.', 'facebook.com', 'twitter.com', 'instagram.com', 'vimeo.com', 'youtube.com']):
            continue
        info['website'] = link_url.rstrip('/')
        break

    return info

# ── FULL PIPELINE ──
def run_catalog():
    """Step 1: Build denomination catalog."""
    print("\n" + "="*70)
    print("  CHURCH DENOMINATION CATALOG BUILDER")
    print("="*70)

    catalog = []

    for family_slug, family_name in sorted(FAMILIES.items()):
        print("\n  Family: %s..." % family_name)
        sys.stdout.flush()

        denoms = get_denominations(family_slug, family_name)
        print("    Found %d denominations" % len(denoms))

        for denom_name, denom_url, listing_url in denoms:
            count, _ = get_church_listing_info(listing_url)
            print("      %-45s %d churches" % (denom_name[:43], count))

            catalog.append({
                'family': family_name,
                'family_slug': family_slug,
                'denomination': denom_name,
                'denomination_slug': listing_url.rstrip('/').split('/')[-1],
                'church_count': count,
                'listing_url': listing_url,
                'info_url': denom_url
            })

            with stats_lock:
                scrape_stats['denominations'] += 1

            time.sleep(random.uniform(0.5, 1.5))

    # Write catalog
    with open(CATALOG_CSV, 'w', newline='', encoding='utf-8') as f:
        fields = ['family', 'family_slug', 'denomination', 'denomination_slug', 'church_count', 'listing_url', 'info_url']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        catalog.sort(key=lambda r: (r['family'], r['denomination']))
        for row in catalog:
            w.writerow(row)

    total_churches = sum(r['church_count'] for r in catalog)
    print("\n" + "="*60)
    print("  CATALOG COMPLETE")
    print("  Families: %d" % len(FAMILIES))
    print("  Denominations: %d" % len(catalog))
    print("  Total church listings: %d" % total_churches)
    print("  Output: %s" % CATALOG_CSV)
    print("="*60)

    return catalog

def run_church_scrape(catalog, anglican_only=False, state_filter=None):
    """Step 2: Scrape individual church pages for contact info."""
    contacts = []

    anglican_families = ['episcopal-anglican']

    for row in catalog:
        if anglican_only and row['family_slug'] not in anglican_families:
            continue
        if row['church_count'] == 0:
            continue

        listing_url = row['listing_url']
        denom_name = row['denomination']
        family_name = row['family']

        print("\n  %s / %s (%d churches)" % (family_name, denom_name, row['church_count']))
        sys.stdout.flush()

        # Paginate through listing pages
        pages = max(1, (row['church_count'] + 19) // 20)
        for page in range(pages):
            page_url = listing_url
            if page > 0:
                page_url = listing_url.rstrip('/') + '/' + str(page * 20) + '/'

            _, churches = get_church_listing_info(page_url)

            for church_name, church_url, size, loc in churches:
                with stats_lock:
                    scrape_stats['churches'] += 1

                # State filter
                if state_filter and state_filter.upper() not in loc.upper():
                    continue

                # Scrape individual page
                info = scrape_church_page(church_url)

                contact = {
                    'church_name': church_name,
                    'denomination': denom_name,
                    'family': family_name,
                    'address': info.get('address', ''),
                    'city_state': info.get('city_state', ''),
                    'zip': info.get('zip', ''),
                    'phone': info.get('phone', ''),
                    'website': info.get('website', ''),
                    'page_url': church_url
                }
                contacts.append(contact)

                with stats_lock:
                    scrape_stats['contacts'] += 1

                time.sleep(random.uniform(0.3, 0.8))

            with stats_lock:
                scrape_stats['pages'] += 1

            pct = (page + 1) / pages * 100
            print("\r    Page %d/%d (%d%%) | Churches: %d" % (
                page+1, pages, pct, len(churches)), end='')
            sys.stdout.flush()

            time.sleep(random.uniform(0.5, 1))

    output_csv = ANGLICAN_CSV if anglican_only else CONTACTS_CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fields = ['church_name', 'denomination', 'family', 'address',
                  'city_state', 'zip', 'phone', 'website', 'page_url']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in contacts:
            w.writerow(c)

    print("\n\n  Contact scrape complete: %d churches" % len(contacts))
    print("  Output: %s" % output_csv)
    return contacts

def print_summary(catalog):
    """Print a sorted summary by denomination/family."""
    print("\n" + "="*70)
    print("  CHURCH DIRECTORY SUMMARY BY DENOMINATION")
    print("="*70)
    print("")

    by_family = {}
    for row in catalog:
        by_family.setdefault(row['family'], []).append(row)

    total_all = 0
    for family in sorted(by_family.keys()):
        denoms = by_family[family]
        fam_total = sum(d['church_count'] for d in denoms)
        total_all += fam_total
        print("  %s" % family)
        print("  " + "-"*len(family))
        for d in sorted(denoms, key=lambda x: -x['church_count']):
            if d['church_count'] > 0:
                print("    %-50s %5d churches" % (d['denomination'][:48], d['church_count']))
        print("    %-50s %5d total" % ("", fam_total))
        print("")

    print("  " + "="*50)
    print("  TOTAL: %d churches across %d families" % (total_all, len(by_family)))
    print("  " + "="*50)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Church directory scraper")
    parser.add_argument("--catalog-only", action="store_true",
                        help="Only build denomination catalog (no contact scraping)")
    parser.add_argument("--anglican-only", action="store_true",
                        help="Only Anglican/Episcopal churches")
    parser.add_argument("--state", type=str, default=None,
                        help="Filter by state (e.g., CA, NY)")
    parser.add_argument("--summary", action="store_true",
                        help="Print catalog summary from existing file")
    parser.add_argument("--yes", action="store_true",
                        help="Auto-confirm (no prompts)")
    args = parser.parse_args()

    catalog = []

    if args.summary:
        if os.path.exists(CATALOG_CSV):
            with open(CATALOG_CSV, 'r', encoding='utf-8') as f:
                catalog = list(csv.DictReader(f))
            print_summary(catalog)
        else:
            print("No catalog found. Run without --summary first.")
        return

    # Step 1: Catalog
    catalog = run_catalog()

    # Print summary
    print_summary(catalog)

    # Step 2: Scrape churches (if not catalog-only)
    if not args.catalog_only:
        if args.yes:
            run_church_scrape(catalog, args.anglican_only, args.state)
        else:
            answer = input("\n  Scrape individual church pages for contacts? (y/n): ")
            if answer.lower().startswith('y'):
                run_church_scrape(catalog, args.anglican_only, args.state)

if __name__ == '__main__':
    main()

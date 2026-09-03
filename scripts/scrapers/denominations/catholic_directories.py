#!/usr/bin/env python3
"""
Comprehensive Diocese Directory Scraper
========================================
Scrapes ALL directories from the Diocese of Charleston website.
Uses Playwright output files as input for listing links,
then fetches detail pages via HTTP.

Usage:
    1. Use Playwright to collect listings -> data/denom/diocese_listings.csv
    2. python scripts/scrapers/scrape_diocese_directories.py
"""
import csv, json, os, re, sys, time, urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        PROJECT_DIR = os.path.expanduser("~/grantwizard")
        break
    PROJECT_DIR = parent

OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
os.makedirs(OUT_DIR, exist_ok=True)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def fetch(url, timeout=15):
    headers = {
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        r = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode('utf-8', 'replace')
    except Exception as e:
        return None


def scrape_all_listings():
    """Scrape all listing pages via HTTP (works with browser headers)."""
    BASE = 'https://directory.charlestondiocese.org'
    all_listings = []
    
    targets = [
        ('priests', '/directories/priest-directory/'),
        ('deacons', '/directories/deacon-directory/'),
        ('campus-ministry', '/directories/campus-ministry-directory/'),
        ('deanery', '/directories/deanery-listings/'),
        ('diocesan-offices', '/directories/diocesan-offices/'),
        ('diocesan-staff', '/directories/diocesan-staff/'),
        ('hospitals', '/directories/hospitals-and-health-care-directory/'),
        ('monasteries', '/directories/monasteries-convents-residences-directory/'),
        ('organizations', '/directories/organization-directory/'),
        ('retreat-centers', '/directories/retreat-center-directory/'),
        ('schools', '/directories/school-directory/'),
        ('seminarians', '/directories/seminarian-directory/'),
        ('seminary', '/directories/seminary-directory/'),
        ('social-outreach', '/directories/social-outreach-directory/'),
    ]
    
    for dir_name, path in targets:
        url = BASE + path
        html = fetch(url)
        if not html:
            log("  %s: FAILED" % dir_name)
            continue
        
        # Get all content links (not nav)
        links = re.findall(r'href="(https://directory\.charlestondiocese\.org/[^"]+)"[^>]*>([^<]+)</a>', html, re.I)
        content = [(u, n.strip()) for u, n in links if '/directories/' not in u and 'charlestondiocese.org' in u and n.strip() and n.strip().lower() != 'southcarolina']
        seen = set()
        unique = [(u, n) for u, n in content if not (u in seen or seen.add(u))]
        
        for u, n in unique:
            all_listings.append({'name': n, 'url': u, 'directory': dir_name})
        
        log("  %s: %d entries" % (dir_name, len(unique)))
        time.sleep(0.3)
    
    return all_listings


def scrape_detail(url, person_type):
    """Scrape a single detail page."""
    html = fetch(url)
    if not html:
        return None
    
    data = {
        'name': '',
        'url': url,
        'type': person_type,
        'assignments': '',
        'office_phone': '',
        'office_email': '',
        'mailing_address': '',
        'mailing_city': '',
        'mailing_state': '',
        'mailing_zip': '',
        'office_address': '',
    }
    
    name_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I)
    if name_m:
        data['name'] = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()
    
    assign_section = re.search(r'<h3[^>]*>Assignments?[^<]*</h3>(.*?)(?:<h3|<footer|</main)', html, re.DOTALL | re.I)
    if assign_section:
        ah = assign_section.group(1)
        assignments = re.findall(r'<a[^>]*href="(https://directory\.charlestondiocese\.org/[^"]*)"[^>]*>([^<]*)</a>', ah, re.I)
        if assignments:
            data['assignments'] = ' | '.join(['%s (%s)' % (b.strip(), a) for a, b in assignments])
        else:
            simpler = re.findall(r'>([^<]*(?:at|Retired|Outside|Director)[^<]*)<', ah)
            if simpler:
                data['assignments'] = ' | '.join([s.strip() for s in simpler])
    
    phone_m = re.search(r'Office Phone:\s*</[^>]*>\s*(?:<a[^>]*href="tel:([^"]+)">)?\s*([\d\s\-\(\)]{7,})', html, re.I)
    if phone_m:
        data['office_phone'] = (phone_m.group(1) or phone_m.group(2) or '').strip()
    
    email_m = re.search(r'Office Email:\s*</[^>]*>\s*<a[^>]*href="mailto:([^"]*)"', html, re.I)
    if email_m:
        data['office_email'] = email_m.group(1).strip()
    
    mail_section = re.search(r'Mailing Address[^<]*</h3>(.*?)(?:<h3|<footer|</main)', html, re.DOTALL | re.I)
    if mail_section:
        lines = [l.strip() for l in re.findall(r'>([^<]{3,})<', mail_section.group(1)) if l.strip()]
        if lines:
            data['mailing_address'] = ' | '.join(lines)
            for line in reversed(lines):
                czip = re.search(r'([A-Z][A-Za-z\s.]+),\s*(A[LKSZR]|C[AOT]|D[EC]|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV|WY)\s+(\d{5})', line)
                if czip:
                    data['mailing_city'] = czip.group(1).strip()
                    data['mailing_state'] = czip.group(2)
                    data['mailing_zip'] = czip.group(3)
                    break
    
    office_section = re.search(r'Office Address[^<]*</h3>(.*?)(?:<h3|<footer|</main)', html, re.DOTALL | re.I)
    if office_section:
        lines = [l.strip() for l in re.findall(r'>([^<]{3,})<', office_section.group(1)) if l.strip()]
        if lines:
            data['office_address'] = ' | '.join(lines)
    
    return data


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--detail-only', action='store_true', help='Skip listing, just scrape details')
    parser.add_argument('--dry-run', action='store_true', help='Skip saving')
    parser.add_argument('--listings', help='Path to listings CSV file (or "latest" to use newest)')
    args = parser.parse_args()
    
    # Determine listings file
    if args.listings == 'latest':
        # Use the full listing from data/denom/diocese_full_listings.csv
        listings_fp = os.path.join(PROJECT_DIR, 'data', 'denom', 'diocese_full_listings.csv')
        if not os.path.exists(listings_fp):
            listings_fp = os.path.join(OUT_DIR, 'diocese_full_listings.csv')
    elif args.listings:
        listings_fp = args.listings
    else:
        listings_fp = os.path.join(OUT_DIR, 'diocese_listings.csv')
    
    # Step 1: Scrape listings (skip if using custom listings file)
    if not args.detail_only and not args.listings:
        log("=== Step 1: Scraping all directory listings ===")
        listings = scrape_all_listings()
        
        # Save listings
        fp = os.path.join(OUT_DIR, 'diocese_listings.csv')
        with open(fp, 'w', newline='', encoding='utf-8') as f:
            if listings:
                w = csv.DictWriter(f, fieldnames=listings[0].keys())
                w.writeheader()
                w.writerows(listings)
        log("Saved %d listings to %s" % (len(listings), fp))
        
        if args.dry_run:
            log("Dry run - skipping detail scrape")
            return
    
    # Load listings
    if not os.path.exists(listings_fp):
        log("No listings file found at %s!" % listings_fp)
        return
    
    with open(listings_fp, 'r', encoding='utf-8') as f:
        listings = list(csv.DictReader(f))
    log("=== Step 2: Scraping %d detail pages ===" % len(listings))
    
    results = []
    for i, entry in enumerate(listings):
        detail = scrape_detail(entry['url'], entry.get('directory', ''))
        if detail:
            detail['directory'] = entry.get('directory', '')
            results.append(detail)
        
        if (i + 1) % 25 == 0:
            log("  %d/%d detail pages scraped" % (i + 1, len(listings)))
        time.sleep(0.25)
    
    # Save details
    fp = os.path.join(OUT_DIR, 'diocese_all_details.csv')
    with open(fp, 'w', newline='', encoding='utf-8') as f:
        if results:
            w = csv.DictWriter(f, fieldnames=results[0].keys())
            w.writeheader()
            w.writerows(results)
    log("Saved %d detail records to %s" % (len(results), fp))
    log("Done!")


if __name__ == '__main__':
    main()

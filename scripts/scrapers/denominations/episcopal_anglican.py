"""
Anglican/Episcopal Church Scraper
==================================
Direct-scrapes Anglican and Episcopal church listings from USAChurches.org.

Denominations:
  - Episcopal Church (TEC)      ~105 listings
  - Continuing Anglican         ~?
  - Reformed Episcopal Church   ~?
  - Charismatic Episcopal       ~?

Output: church_anglican_episcopal.csv
"""

import csv
import os
import sys
import re
import time
import random
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "church_anglican_episcopal.csv")
BASE = "https://www.usachurches.org"

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
    phones = re.findall(r'\((\d{3})\)\s*(\d{3})[-.](\d{4})', html)
    if phones:
        return '(%s) %s-%s' % phones[0]
    return ''

# Anglican/Episcopal listing URLs
ANGLICAN_DENOMS = [
    ("Episcopal Church (TEC)", "https://www.usachurches.org/christian/episcopal-anglican/episcopal-church/"),
    ("Continuing Anglican", "https://www.usachurches.org/christian/episcopal-anglican/continuing-anglican/"),
    ("Reformed Episcopal Church", "https://www.usachurches.org/christian/episcopal-anglican/reformed-episcopal-church/"),
    ("Charismatic Episcopal Church", "https://www.usachurches.org/christian/episcopal-anglican/international-communion-of-the-charismatic-episcopal-church/"),
]

def get_church_listing_page(url):
    """Fetch a listing page and extract church entries."""
    html = fetch(url)
    if not html:
        return 0, []
    
    # Get count
    count = 0
    m = re.search(r'(\d[\d,]*)\s*(?:&nbsp;)?\s*(?:</\w+>)?\s*(?:</\w+>)?\s*(?:&nbsp;)?\s*church\s*listings', html, re.IGNORECASE)
    if m:
        count = int(m.group(1).replace(',', ''))
    
    # Extract churches
    churches = []
    seen = set()
    for m in re.finditer(r'<a\s+href="[^"]*/church/([a-zA-Z0-9_.-]+\.htm)"[^>]*>\s*([^<]+?)\s*</a>', html):
        slug = m.group(1)  # Keep .htm extension
        name = m.group(2).strip()
        church_url = BASE + '/church/' + slug
        if church_url in seen:
            continue
        seen.add(church_url)
        
        # Get context for address
        start = m.end()
        context = html[start:start+500]
        
        addr_match = re.search(r'([A-Z][a-zA-Z .-]+?),?\s*([A-Z]{2})(?:\s*(\d{5}))?', context)
        city_state = ''
        zipcode = ''
        if addr_match:
            city_state = (addr_match.group(1).strip() + ', ' + addr_match.group(2)).strip()
            zipcode = addr_match.group(3) or ''
        
        churches.append((name, church_url, city_state, zipcode))
    
    return count, churches

def scrape_church_page(church_url):
    """Get phone and website from individual church page."""
    html = fetch(church_url, timeout=10)
    if not html:
        return '', ''
    
    phone = ''
    # Phone: (201) 327-3012 or 201-327-3012
    m = re.search(r'\(\d{3}\)\s*\d{3}[-.]\d{4}', html)
    if m:
        phone = m.group(0).strip()
    
    website = ''
    # Find ALL external links, skip social/usachurches, take the last good one
    # (the church website is typically the last non-social link in the page)
    all_links = re.findall(r'href="(https?://([^"]+))"', html)
    for link_url, domain in reversed(all_links):
        domain = domain.lower()
        if any(s in domain for s in ['usachurches.org', 'google.', 'facebook.com', 'twitter.com', 'instagram.com', 'vimeo.com', 'youtube.com']):
            continue
        website = link_url.rstrip('/')
        break
    
    return phone, website

def main():
    print("=" * 70)
    print("  ANGLICAN/EPISCOPAL CHURCH SCRAPER")
    print("=" * 70)
    
    all_churches = []
    
    for denom_name, listing_url in ANGLICAN_DENOMS:
        print("\n  %s..." % denom_name)
        sys.stdout.flush()
        
        # Get first page
        total_count, churches = get_church_listing_page(listing_url)
        print("    Total: %d churches" % total_count)
        print("    Page 1: %d churches" % len(churches))
        
        # Get paginated pages
        if total_count > 20:
            pages = (total_count + 19) // 20
            for page in range(1, pages):
                page_url = listing_url.rstrip('/') + '/' + str(page * 20) + '/'
                _, page_churches = get_church_listing_page(page_url)
                churches.extend(page_churches)
                print("    Page %d: %d churches" % (page+1, len(page_churches)))
                time.sleep(random.uniform(0.5, 1))
        
        all_churches.extend([(c[0], c[1], c[2], c[3], denom_name) for c in churches])
        time.sleep(random.uniform(0.5, 1.5))
    
    print("\n  Total churches found: %d" % len(all_churches))
    
    # Now scrape individual pages for phone/website
    print("\n  Scraping individual church pages for contact info...")
    results = []
    for i, (name, url, city_state, zipcode, denom) in enumerate(all_churches):
        phone, website = scrape_church_page(url)
        results.append({
            'church_name': name,
            'denomination': denom,
            'city_state': city_state,
            'zip': zipcode,
            'phone': phone,
            'website': website,
            'page_url': url
        })
        if (i + 1) % 20 == 0:
            print("    %d/%d..." % (i+1, len(all_churches)))
            sys.stdout.flush()
        time.sleep(random.uniform(0.3, 0.8))
    
    # Write CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        fields = ['church_name', 'denomination', 'city_state', 'zip', 'phone', 'website', 'page_url']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow(r)
    
    # Summary
    with_website = sum(1 for r in results if r['website'])
    with_phone = sum(1 for r in results if r['phone'])
    
    print("\n" + "=" * 60)
    print("  ANGLICAN/EPISCOPAL SCRAPE COMPLETE")
    print("  Churches: %d" % len(results))
    print("  With website: %d" % with_website)
    print("  With phone: %d" % with_phone)
    print("  Output: %s" % OUTPUT_CSV)
    print("=" * 60)

if __name__ == '__main__':
    main()

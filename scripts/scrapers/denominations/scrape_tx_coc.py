#!/usr/bin/env python3
"""Scrape Texas Churches of Christ directory from theseeker.org.

Structure:
- director.htm (A-B), director1.htm (C-E), director2.htm (F-K),
  director3.htm (L-O), director4.htm (P-S), director5.htm (T-Z)
  → Each lists city names linking to /cgi-bin/texas/city_nfo.pl?city=CityName
- city_nfo.pl page lists individual churches with name, address, phone, email, website
"""
import re, os, sys, urllib.request, urllib.error, json, time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = "https://www.theseeker.org"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

DIR_PAGES = [
    "/texas/director.htm",  "/texas/director1.htm",
    "/texas/director2.htm", "/texas/director3.htm",
    "/texas/director4.htm", "/texas/director5.htm",
]


def fetch(url, timeout=15, referer=""):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(BASE + url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as f:
        return f.read().decode("utf-8", "replace")


def get_cities_from_page(html):
    """Extract city names from a directory page."""
    cities = set()
    # City links are like: city=Abilene>Abilene</a> (no quotes!)
    for m in re.finditer(r'/cgi-bin/texas/city_nfo\.pl\?city=([^>"\'&\t ]+)', html):
        city = urllib.request.unquote(m.group(1)).replace('+', ' ').strip()
        if city:
            cities.add(city)
    return sorted(cities)


def parse_churches(html, city, state="TX"):
    """Parse church data from a city_nfo.pl page."""
    churches = []
    
    # Each church entry: <a href=WEBSITE><font class=churchname>NAME</font></a><br>
    # followed by address, phone, email, membership info
    for m in re.finditer(
        r'<a\s+href=(https?://[^>\s]+)><font\s+class=churchname>([^<]+)</font></a>',
        html
    ):
        website = m.group(1)
        name = m.group(2).strip()
        pos = m.end()
        context = html[pos:pos+600]
        
        # Extract address from Google Maps link text
        addr = ""
        addr_m = re.search(r'<a\s+href=https://maps\.google\.com/[^>]+>([^<]+)</a>', context)
        if addr_m:
            addr = addr_m.group(1).strip()
        
        # Extract ZIP
        zipcode = ""
        zip_m = re.search(r'(?:TX|Texas)\s*(\d{5}(?:-\d{4})?)', context)
        if zip_m:
            zipcode = zip_m.group(1)
        
        # Extract phone
        phone = ""
        phone_m = re.search(r'Phone:</font>\s*<font\s+class=info>([^<]+)', context)
        if phone_m:
            phone = phone_m.group(1).strip()
        
        # Extract email
        email = ""
        email_m = re.search(r'Email:</font>\s*<font\s+class=info><a\s+href=mailto:([^>]+)>', context)
        if email_m:
            email = email_m.group(1).strip()
        
        # Extract membership
        members = 0
        members_m = re.search(r'Total number of members:</font>\s*<font\s+class=info>(\d+)', context)
        if members_m:
            members = int(members_m.group(1))
        
        churches.append({
            'name': name,
            'address': addr,
            'city': city,
            'state': state,
            'zip': zipcode,
            'phone': phone,
            'email': email,
            'website': website,
            'members': members,
        })
    
    return churches


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit-cities', type=int, default=0)
    parser.add_argument('-o', '--output', default='')
    args = parser.parse_args()
    
    print(f'=== Texas Churches of Christ Scraper ===')
    
    # Step 1: Get all cities
    all_cities = set()
    for dp in DIR_PAGES:
        print(f'  Fetching {dp}...', end=' ', flush=True)
        try:
            html = fetch(dp)
            cities = get_cities_from_page(html)
            all_cities.update(cities)
            print(f'{len(cities)} cities')
        except Exception as e:
            print(f'ERR: {e}')
    
    all_cities = sorted(all_cities)
    print(f'\nTotal cities: {len(all_cities):,}')
    
    if args.limit_cities:
        all_cities = all_cities[:args.limit_cities]
    
    # Step 2: Fetch each city
    all_churches = []
    errors = 0
    
    for ci, city in enumerate(all_cities):
        url = f'/cgi-bin/texas/city_nfo.pl?city={city.replace(" ", "+")}'
        label = f'[{ci+1}/{len(all_cities)}] {city:30s}'
        print(f'  {label}', end=' ', flush=True)
        try:
            html = fetch(url, referer='/texas/director.htm')
            churches = parse_churches(html, city)
            all_churches.extend(churches)
            print(f'{len(churches)} churches')
        except Exception as e:
            errors += 1
            print(f'ERR: {e}')
        time.sleep(0.25)
    
    print(f'\n=== RESULTS ===')
    print(f'Total churches: {len(all_churches):,}')
    print(f'Errors: {errors}')
    
    with_web = sum(1 for c in all_churches if c.get('website'))
    with_phone = sum(1 for c in all_churches if c.get('phone'))
    with_email = sum(1 for c in all_churches if c.get('email'))
    print(f'With website: {with_web:,}')
    print(f'With phone: {with_phone:,}')
    print(f'With email: {with_email:,}')
    
    if all_churches:
        print(f'\nSamples:')
        for c in all_churches[:5]:
            print(f'  {c["name"][:50]:50s} | {c.get("address",""):30s} | {c["city"]:20s}')
    
    if args.output and all_churches:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(all_churches, f, indent=2)
        print(f'\nSaved to {args.output}')
    
    print('\nDone!')


if __name__ == '__main__':
    main()

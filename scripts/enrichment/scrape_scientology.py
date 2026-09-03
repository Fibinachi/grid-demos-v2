#!/usr/bin/env python3
"""
Scientology Organization Scraper
=================================
Scrapes scientology.org sitemap for all org locations, then classifies
each by type using URL path patterns.

Taxonomy:
  - Class V Org — standard local church
  - Ideal Org — flagship newly-built org
  - Advanced Org — delivers OT levels
  - Saint Hill Org — delivers Saint Hill Special Briefing Course
  - Flag Service Org — Clearwater FL headquarters
  - Flag Ship Service Org — Freewinds ship
  - Celebrity Centre — celeb-focused orgs
  - Mission — smaller outreach units
  - Continental Liaison Office — regional admin
  - Support Organization — Golden Era, Bridge, etc.
  - Narconon / Criminon / Applied Scholastics / WISE — affiliated nonprofits

Usage:
    python scripts/enrichment/scrape_scientology.py
    python scripts/enrichment/scrape_scientology.py --limit 50
    python scripts/enrichment/scrape_scientology.py --merge
"""
import argparse, json, os, re, sqlite3, time, urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT = os.path.join(PROJECT_DIR, 'data', 'scientology_orgs.json')
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


def classify_by_url(url):
    """Classify org type by URL path."""
    u = url.lower()
    if '/advanced-' in u: return 'Advanced Org'
    if '/flag-land-base' in u: return 'Flag Service Org'
    if '/freewinds' in u: return 'Flag Ship Service Org'
    if '/ideal-orgs/' in u: return 'Ideal Org'
    if '/celebrity' in u: return 'Celebrity Centre'
    if '/mission' in u: return 'Mission'
    if '/saint-hill' in u: return 'Saint Hill Org'
    if any(x in u for x in ['/bringing-scientology', '/golden-era', '/bridge-publications',
                              '/new-era', '/scientology-media', '/dissemination']):
        return 'Support Organization'
    if '/continental-liaison' in u or '/clo' in u:
        return 'Continental Liaison Office'
    return 'Class V Org'


def scrape_page(url):
    """Scrape a single org page. Returns dict or None."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', 'replace')

        title = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        name = title.group(1).strip() if title else ''
        name = name.replace('&amp;', '&').replace('&nbsp;', ' ').replace('\u00a0', ' ')
        
        addr, city, state, zipcode, lat, lon = '', '', '', '', None, None
        ld = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        if ld:
            try:
                data = json.loads(ld.group(1))
                if '@graph' in data:
                    for item in data['@graph']:
                        if item.get('@type') in ('Place', 'Church', 'Organization'):
                            data = item; break
                geo = data.get('geo', {}) or data.get('mainEntity', {}).get('geo', {}) or {}
                lat = geo.get('latitude'); lon = geo.get('longitude')
                addr_obj = data.get('address', {}) or data.get('location', {}).get('address', {})
                if isinstance(addr_obj, dict):
                    addr = addr_obj.get('streetAddress', '')
                    city = addr_obj.get('addressLocality', '')
                    state = addr_obj.get('addressRegion', '')
                    zipcode = addr_obj.get('postalCode', '')
            except: pass
        
        return {'name': name, 'url': url,
                'address': addr, 'city': city, 'state': state, 'zip': zipcode,
                'latitude': lat, 'longitude': lon}
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--merge', action='store_true')
    args = parser.parse_args()

    req = urllib.request.Request('https://www.scientology.org/sitemap.xml', headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        sitemap = resp.read().decode('utf-8', 'replace')

    church_urls = re.findall(r'https://www\.scientology\.org/churches/[^<]+', sitemap)
    print(f'Church/location URLs: {len(church_urls):,}')

    urls_to_scrape = church_urls[:args.limit] if args.limit else church_urls
    print(f'Scraping {len(urls_to_scrape):,} pages...\n')

    orgs = []
    for i, url in enumerate(urls_to_scrape):
        if url.endswith('/') and not url.endswith('.html'):
            continue
        org_type = classify_by_url(url)
        result = scrape_page(url)
        if result:
            result['type'] = org_type
            orgs.append(result)
            name = (result['name'] or '(no title)')[:50]
            print(f'  [{i+1}/{len(urls_to_scrape)}] {name:50s} | {org_type:20s} | {result["city"]:18s} {result["state"]}')
        else:
            print(f'  [{i+1}/{len(urls_to_scrape)}] FAILED: {url.split("/")[-1][:50]}')
        time.sleep(0.3)

    print(f'\nScraped {len(orgs):,} orgs')
    types = {}
    for o in orgs: types[o['type']] = types.get(o['type'], 0) + 1
    print(f'\n{"Type":30s} {"Count":>6s}')
    print('-' * 40)
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f'{t:30s} {c:>6,}')

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w') as f:
        json.dump(orgs, f, indent=2)
    print(f'\nSaved to {OUTPUT}')

    if args.merge and orgs:
        db = sqlite3.connect(DB_PATH, timeout=60)
        matched, new = 0, 0
        for o in orgs:
            if not o['city'] or not o['state']:
                continue
            existing = db.execute("""
                SELECT id FROM churches
                WHERE LOWER(name) = LOWER(?) AND LOWER(city) = LOWER(?) AND state = ?
                LIMIT 1
            """, (o['name'], o['city'], o['state'])).fetchone()
            if existing:
                db.execute("""UPDATE churches SET faith_tradition='other', family='Scientology',
                    denomination=?, website=CASE WHEN website='' OR website IS NULL THEN ? ELSE website END,
                    latitude=CASE WHEN latitude IS NULL OR latitude=0 THEN ? ELSE latitude END,
                    longitude=CASE WHEN longitude IS NULL OR longitude=0 THEN ? ELSE longitude END,
                    last_updated=datetime('now') WHERE id=?""",
                    (o['type'], o['url'], o['latitude'], o['longitude'], existing[0]))
                matched += 1
            else:
                db.execute("""INSERT INTO churches (name,city,state,faith_tradition,family,denomination,
                    website,latitude,longitude,source,last_updated) VALUES (?,?,?,'other','Scientology',?,?,?,?,'scientology_org_scraper',datetime('now'))""",
                    (o['name'], o['city'], o['state'], o['type'], o['url'], o['latitude'], o['longitude']))
                new += 1
        db.commit()
        print(f'Merge: {matched} matched, {new} new records')
        db.close()


if __name__ == '__main__':
    main()

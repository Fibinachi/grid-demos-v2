#!/usr/bin/env python3
"""
Bulk Catholic Sitemap Harvester
===============================
For each remaining diocese, try common sitemap URLs via HTTP.
Much faster than Playwright for initial pass.

Usage:
    python scripts/scrapers/denominations/scrape_catholic_sitemap_bulk.py
"""

import csv, json, re, sys, time, urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from collections import Counter

PROJECT_DIR = Path(r"E:\grid")
DATA_DIR = PROJECT_DIR / "data"
DIOCESE_JSON = DATA_DIR / "catholic_dioceses.json"
OUTPUT_CSV = DATA_DIR / "catholic_bulk_sitemap_results.csv"

SITEMAP_PATHS = ['/sitemap.xml', '/sitemap_index.xml', '/wp-sitemap.xml']
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Skip patterns for non-parish URLs
SKIP_PATTERNS = ['/event', '/blog', '/news', '/contact', '/about', '/staff',
                 '/donate', '/giving', '/job', '/career', '/volunteer',
                 '/wp-', '/feed', '/tag', '/author', '/category',
                 '/search', '/pdf', '.pdf', '/privacy', '/login']

def fetch(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return f.read().decode('utf-8', 'replace')
    except Exception:
        return None

def is_parish_url(url):
    """Check if URL looks like a parish page."""
    url_lower = url.lower()
    if re.search(r'\.(jpg|jpeg|png|gif|svg|pdf|css|js|zip|xml|json|ico)', url_lower):
        return False
    for skip in SKIP_PATTERNS:
        if skip in url_lower:
            return False
    # Positive indicators
    indicators = ['/parish/', '/parishes/', '/location/', '/church/', '/churches/',
                  '-catholic-church', '-parish', 'st-', 'saint-',
                  'our-lady-', 'holy-', 'sacred-heart-', 'immaculate-',
                  'blessed-sacrament-', 'christ-the-king-', 'st.-',
                  '/our-parishes/', '/parish-directory/']
    for ind in indicators:
        if ind in url_lower:
            return True
    return False

def extract_name(url):
    path = urlparse(url).path.strip('/')
    parts = [p for p in path.split('/') if p.lower() not in
             ('parish','parishes','location','churches','our-parishes',
              'parish-directory','church','index','locations')]
    if parts:
        name = parts[-1].replace('-',' ').replace('_',' ').title()
        name = re.sub(r'\bSt\b(?!\.)', 'St.', name)
        return name[:200]
    return ''

def main():
    import sqlite3
    db = sqlite3.connect(str(PROJECT_DIR / 'churches.db'))
    db_dioceses = set(r[0].strip().lower() for r in db.execute(
        "SELECT DISTINCT diocese FROM churches WHERE denomination='Roman Catholic Church' AND diocese IS NOT NULL AND diocese != ''"
    ).fetchall())
    db.close()

    with open(DIOCESE_JSON) as f:
        dioceses = json.load(f)

    # Find unmatched
    to_scrape = []
    for d in dioceses:
        dj = d['name'].lower().strip()
        dj_short = dj.replace('archdiocese of ','').replace('diocese of ','').replace('eparchy of ','').replace('ordinariate of ','').strip()
        matched = False
        for db_name in db_dioceses:
            dj_words = set(w for w in dj_short.split() if len(w) > 3)
            db_words = set(w for w in db_name.split() if len(w) > 3)
            if len(dj_words & db_words) >= 2 or dj_short in db_name or db_name in dj_short:
                matched = True
                break
        if not matched:
            to_scrape.append(d)

    print(f"Dioceses to check: {len(to_scrape)}")

    all_results = []
    found_any = 0
    start = time.time()

    for i, d in enumerate(to_scrape):
        name = d['name']
        url = d['website'].strip()
        state = d.get('state', '')
        cms = d.get('cms', 'unknown')

        if not url.startswith('http'):
            url = 'https://' + url

        base = url.rstrip('/')
        found_urls = []
        parish_urls = []

        # Try each sitemap path
        for sp in SITEMAP_PATHS:
            sitemap_url = base + sp
            xml = fetch(sitemap_url)
            if xml:
                locs = re.findall(r'<loc[^>]*>(.*?)</loc>', xml, re.DOTALL)
                # Also check for sitemap index
                child_locs = []
                for loc in locs:
                    loc = loc.strip()
                    if loc.startswith('<![CDATA[') and loc.endswith(']]>'):
                        loc = loc[9:-3]
                    if '.xml' in loc.lower():
                        child_locs.append(loc)
                    else:
                        found_urls.append(loc)

                # Follow child sitemaps
                for cl in child_locs[:20]:
                    child_xml = fetch(cl)
                    if child_xml:
                        child_urls = re.findall(r'<loc[^>]*>(.*?)</loc>', child_xml, re.DOTALL)
                        for cu in child_urls:
                            cu = cu.strip()
                            if cu.startswith('<![CDATA[') and cu.endswith(']]>'):
                                cu = cu[9:-3]
                            found_urls.append(cu)

                if found_urls:
                    parish_urls = [u for u in found_urls if is_parish_url(u)]
                    print(f"  [{i+1}/{len(to_scrape)}] {name[:45]:45s} sitemap={sp:20s} {len(found_urls)} URLs, {len(parish_urls)} parishes")
                    break

        if parish_urls:
            found_any += 1
            for pu in parish_urls[:200]:
                pname = extract_name(pu)
                all_results.append({
                    'diocese': name, 'state': state, 'cms': cms,
                    'parish_name': pname, 'parish_url': pu,
                })
        elif not found_urls:
            # No sitemap at all
            pass

        if (i+1) % 20 == 0:
            elapsed = time.time() - start
            print(f"  --- {i+1}/{len(to_scrape)} in {elapsed:.0f}s, {found_any} with data ---")

    # Save results
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['diocese','state','cms','parish_name','parish_url'])
        for r in all_results:
            w.writerow([r['diocese'], r['state'], r['cms'], r['parish_name'], r['parish_url']])

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"Done! Checked {len(to_scrape)} dioceses in {elapsed:.0f}s")
    print(f"Found sitemaps for: {found_any} dioceses")
    print(f"Total parish URLs: {len(all_results)}")
    print(f"Saved to: {OUTPUT_CSV}")

    # Summary
    by_diocese = Counter(r['diocese'] for r in all_results)
    print(f"\nTop dioceses by parish count:")
    for d_name, cnt in by_diocese.most_common(10):
        print(f"  {cnt:>5}  {d_name[:55]}")

if __name__ == '__main__':
    main()

"""Extract mosque URLs from sitemaps and scrape data."""
import requests, re, sqlite3
from datetime import datetime, timezone

HEADERS = {'User-Agent': 'Mozilla/5.0'}
NOW = datetime.now(timezone.utc).isoformat()
DB = 'E:/grid/churches.db'

# ── Sitemap sources ──
sources = [
    {
        'name': 'visitamosque_us',
        'base': 'https://visitamosque.us',
        'sitemap': 'https://visitamosque.us/wp-sitemap.xml',
        'url_filter': 'mosque-item',
        'state_filter': True,  # exclude state pages
    },
    {
        'name': 'muslimsinbritain',
        'base': 'https://mosques.muslimsinbritain.org',
        'sitemap': 'https://mosques.muslimsinbritain.org/wp-sitemap.xml',
        'url_filter': '/mosques/',
    },
    {
        'name': 'mosquefinder_in',
        'base': 'https://mosquefinder.in',
        'sitemap': 'https://mosquefinder.in/wp-sitemap.xml',
        'url_filter': None,  # get all
    },
]

all_mosque_urls = {}

for src in sources:
    print(f"\n=== {src['name']} ===")
    try:
        r = requests.get(src['sitemap'], headers=HEADERS, timeout=15)
        sub_sitemaps = re.findall(r'<loc>([^<]+)</loc>', r.text)
        print(f"  Sub-sitemaps: {len(sub_sitemaps)}")
        
        urls = []
        for sm in sub_sitemaps:
            r2 = requests.get(sm, headers=HEADERS, timeout=15)
            page_urls = re.findall(r'<loc>([^<]+)</loc>', r2.text)
            if src['url_filter']:
                page_urls = [u for u in page_urls if src['url_filter'] in u]
            if src.get('state_filter'):
                # Exclude state-level pages (shorter URLs)
                page_urls = [u for u in page_urls if u.count('/') > src['base'].count('/') + 3]
            urls.extend(page_urls)
        
        urls = list(set(urls))
        all_mosque_urls[src['name']] = urls
        print(f"  Mosque URLs: {len(urls)}")
        if urls:
            print(f"  Sample: {urls[0][:100]}")
    except Exception as e:
        print(f"  ERROR: {e}")

# ── Summary ──
print(f"\n=== Summary ===")
total = 0
for name, urls in all_mosque_urls.items():
    print(f"  {name}: {len(urls)}")
    total += len(urls)
print(f"  TOTAL: {total}")

# Save URL lists
for name, urls in all_mosque_urls.items():
    with open(f'E:/grid/data/{name}_urls.txt', 'w') as f:
        f.write('\n'.join(urls))
print("\nSaved URL lists to data/")

"""Extract and scrape mosque URLs from sitemaps."""
import requests, re, sqlite3
from datetime import datetime, timezone

HEADERS = {'User-Agent': 'Mozilla/5.0'}
NOW = datetime.now(timezone.utc).isoformat()
DB = 'E:/grid/churches.db'

# ── UK: muslimsinbritain.org ──
print("=== UK: Muslims in Britain ===")
r = requests.get('https://mosques.muslimsinbritain.org/sitemap.xml', headers=HEADERS)
links = re.findall(r'href="([^"]+)"', r.text)
mosque_links = [l for l in links if '/mosques/' in l]
print(f"  Mosque links: {len(mosque_links)}")
for l in mosque_links[:5]:
    print(f"    {l[:100]}")

# ── India: mosquefinder.in ──
print("\n=== India: mosquefinder.in ===")
r2 = requests.get('https://mosquefinder.in/wp-sitemap.xml', headers=HEADERS)
sitemaps = re.findall(r'<loc>([^<]+)</loc>', r2.text)
print(f"  Sub-sitemaps: {len(sitemaps)}")
for sm in sitemaps:
    name = sm.split('/')[-1]
    r3 = requests.get(sm, headers=HEADERS, timeout=15)
    urls = re.findall(r'<loc>([^<]+)</loc>', r3.text)
    mosque = [u for u in urls if 'mosque' in u.lower() or 'masjid' in u.lower()]
    print(f"    {name}: {len(urls)} total, {len(mosque)} mosque-related")
    if mosque:
        print(f"      Sample: {mosque[0][:100]}")

# ── US: visitamosque.us — check all sitemaps ──
print("\n=== US: visitamosque.us ===")
r4 = requests.get('https://visitamosque.us/wp-sitemap.xml', headers=HEADERS)
v_sitemaps = re.findall(r'<loc>([^<]+)</loc>', r4.text)
for sm in v_sitemaps:
    name = sm.split('/')[-1]
    r5 = requests.get(sm, headers=HEADERS, timeout=15)
    urls = re.findall(r'<loc>([^<]+)</loc>', r5.text)
    mosque = [u for u in urls if 'mosque-item' in u]
    print(f"    {name}: {len(urls)} total, {len(mosque)} mosque-item")
    if mosque:
        print(f"      First: {mosque[0][:100]}")
        print(f"      Last: {mosque[-1][:100]}")

# ── Also check for custom post type sitemaps ──
print("\n=== Custom post type sitemaps ===")
for site, base in [('visitamosque.us', 'https://visitamosque.us'), 
                    ('mosquefinder.in', 'https://mosquefinder.in')]:
    cpts = ['mosque', 'mosques', 'masjid', 'masjids', 'islamic-center', 'mosque-item', 'listing', 'place']
    for cpt in cpts:
        url = f'{base}/wp-sitemap-posts-{cpt}-1.xml'
        try:
            rc = requests.get(url, headers=HEADERS, timeout=8)
            if rc.status_code == 200:
                urls = re.findall(r'<loc>([^<]+)</loc>', rc.text)
                print(f"  {site}/wp-sitemap-posts-{cpt}-1.xml: {len(urls)} URLs")
                if urls:
                    print(f"    Sample: {urls[0][:100]}")
        except:
            pass

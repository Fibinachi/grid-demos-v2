"""
Scrape the national SBC directory (churches.sbc.net) from its 35 church sitemaps.
Each sitemap has ~1,000 church detail pages with name, address, phone, email, coords.
"""
import urllib.request, json, time, re, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET

OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sbc_national.jsonl")

SITEMAP_INDEX = "https://churches.sbc.net/sitemaps.xml"
BASE = "https://churches.sbc.net"

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def get_church_sitemaps():
    """Parse sitemap index and return list of church-sitemap URLs."""
    xml = fetch(SITEMAP_INDEX)
    root = ET.fromstring(xml)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for loc in root.findall("s:sitemap/s:loc", ns):
        u = loc.text.strip()
        if "church-sitemap" in u:
            urls.append(u)
    return sorted(urls)

def parse_church_sitemap(url):
    """Parse a church sitemap XML and return list of church page URLs."""
    xml = fetch(url)
    root = ET.fromstring(xml)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for loc in root.findall("s:url/s:loc", ns):
        u = loc.text.strip()
        if u.startswith(BASE + "/church/"):
            urls.append(u)
    # Skip the first entry which is /churches/ (the search page)
    return urls[1:] if urls and "/churches/" in urls[0] else urls

def scrape_church(url):
    """Scrape a single church detail page for name, address, phone, email."""
    try:
        html = fetch(url, timeout=15).decode("utf-8", errors="replace")
    except Exception as e:
        return {"url": url, "error": str(e)}
    
    church = {"url": url}
    
    # Extract name from <title> or h1
    m = re.search(r'<title>([^<]+)', html)
    if m:
        name = m.group(1).replace(" - SBC Churches Directory", "").strip()
        church["name"] = name
    
    # Extract address - pattern: City, State ZIP  
    m = re.search(r'([^<]+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', html)
    if m:
        church["city"] = m.group(1).strip()
        church["state"] = m.group(2)
        church["zip"] = m.group(3)
    
    # Extract address line before city
    # Find the address block: it's usually in a div/h3 before the city/state/zip
    addr_match = re.search(r'<h3[^>]*>\s*([^<]+?)</h3>\s*<p[^>]*>\s*([^,]+?),\s*([A-Z]{2})', html)
    if addr_match:
        street_raw = addr_match.group(1).strip()
        # Clean up - remove HTML entities if any
        street_raw = re.sub(r'<[^>]+>', '', street_raw).strip()
        if street_raw and len(street_raw) > 5:
            church["address"] = street_raw
    
    # Try alternative: address before city state in the page
    if "address" not in church:
        alt = re.search(r'<p[^>]*>\s*([^<]+?)\s*<br\s*/?>\s*([^,]+?),\s*([A-Z]{2})\s+\d{5}', html)
        if alt:
            church["address"] = alt.group(1).strip()
    
    # Phone
    m = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', html)
    if m:
        church["phone"] = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
    
    # Email from mailto:
    m = re.search(r'mailto:([^"\'<>]+)', html)
    if m:
        church["email"] = m.group(1).strip()
    
    # Coordinates from Google Maps URL
    m = re.search(r'll=([\d.-]+),([\d.-]+)', html)
    if m:
        church["lat"] = float(m.group(1))
        church["lng"] = float(m.group(2))
    
    return church

def main():
    t0 = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] Fetching sitemap index...")
    sitemaps = get_church_sitemaps()
    print(f"  Found {len(sitemaps)} church sitemaps")
    
    all_urls = []
    for sm in sitemaps:
        urls = parse_church_sitemap(sm)
        all_urls.extend(urls)
        print(f"  {sm.split('/')[-1]}: {len(urls)} URLs")
    
    print(f"\n[{time.strftime('%H:%M:%S')}] Total: {len(all_urls):,} church pages to scrape")
    
    # Scrape in parallel
    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=20) as ex:
        fut_map = {ex.submit(scrape_church, url): url for url in all_urls}
        for f in as_completed(fut_map):
            done += 1
            if done % 500 == 0:
                print(f"  {done:,}/{len(all_urls):,} ({done/len(all_urls)*100:.0f}%)")
            results.append(f.result())
    
    # Write JSONL
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for r in results:
            if "error" not in r:
                f.write(json.dumps(r) + "\n")
    
    good = sum(1 for r in results if "error" not in r)
    bad = sum(1 for r in results if "error" in r)
    print(f"\n[{time.strftime('%H:%M:%S')}] Done in {time.time()-t0:.0f}s")
    print(f"  {good:,} good, {bad:,} errors")
    print(f"  Output: {OUTPUT}")
    
    # Stats
    with_phone = sum(1 for r in results if "phone" in r)
    with_email = sum(1 for r in results if "email" in r)
    with_coords = sum(1 for r in results if "lat" in r)
    print(f"  With phone: {with_phone:,}")
    print(f"  With email: {with_email:,}")
    print(f"  With coords: {with_coords:,}")

if __name__ == "__main__":
    main()

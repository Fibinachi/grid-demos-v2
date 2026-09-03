"""
Scraper for Southern Baptist Convention church directory.
https://churches.sbc.net/ — 34,501 churches across 1,438 pages.

Output: sbc_churches.csv
"""
import csv, os, re, time, urllib.request, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(SCRIPT_DIR, "sbc_churches.csv")
PROGRESS = os.path.join(SCRIPT_DIR, "sbc_scrape_progress.json")

MAX_WORKERS = 20  # concurrent scrapers

def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    print(line)
    sys.stdout.flush()

def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except:
        return None

def get_church_links_from_page(page_num):
    """Get all church listing URLs from a single page."""
    url = "https://churches.sbc.net/page/%d/?_paged=%d" % (page_num, page_num)
    html = fetch(url)
    if not html:
        return []
    
    # Extract church links
    links = re.findall(r'href="(https://churches\.sbc\.net/church/[^"]+)"', html)
    return list(dict.fromkeys(links))  # deduplicate

def scrape_church_page(url):
    """Scrape a single church page for contact info."""
    html = fetch(url, timeout=12)
    if not html:
        return None
    
    church = {"source_url": url}
    
    # Church name - from h1
    m = re.search(r'<h1[^>]*>([^<]+)', html)
    if m:
        church["church_name"] = m.group(1).strip()
    
    # City, State, Zip - from heading
    m = re.search(r'<h3[^>]*>([^<]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', html)
    if m:
        church["city"] = m.group(1).strip()
        church["state"] = m.group(2).strip()
        church["zip"] = m.group(3).strip()
    
    # Phone
    m = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html)
    if m:
        church["phone"] = m.group(0).strip()
    
    # Email (mailto: link)
    m = re.search(r'href="mailto:([^"]+)"', html)
    if m:
        church["email"] = m.group(1).strip()
    
    # Website
    m = re.search(r'href="(https?://[^"]+)"[^>]*>.*?</a>\s*$', html, re.IGNORECASE | re.MULTILINE)
    if not m:
        m = re.search(r'<a[^>]+href="(https?://[^"\']+)"[^>]*>\s*(?:https?://)?\1', html)
    if not m:
        # Try more general website extraction
        m = re.search(r'(https?://(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^"<\s]*)?)', html)
    if m:
        url_found = m.group(1)
        # Skip if it's the SBC domain itself
        if "churches.sbc.net" not in url_found:
            church["website"] = url_found
    
    return church

def main():
    log("SBC Church Directory Scraper")
    log("Target: 34,501 churches across ~1,438 pages")
    
    # Phase 1: Collect all church URLs from listing pages
    log("\nPhase 1: Collecting church listing URLs...")
    
    total_pages = 1438
    all_links = []
    
    for page in range(1, total_pages + 1):
        links = get_church_links_from_page(page)
        all_links.extend(links)
        if page % 50 == 0 or page == 1:
            log("  Page %d/%d: %d links found (total: %d)" % (page, total_pages, len(links), len(all_links)))
        time.sleep(0.3)
    
    all_links = list(dict.fromkeys(all_links))  # deduplicate
    log("\n  Total unique church URLs: %d" % len(all_links))
    
    # Phase 2: Scrape each church page for contact info
    log("\nPhase 2: Scraping individual church pages...")
    
    results = []
    processed = 0
    found_email = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scrape_church_page, url): url for url in all_links}
        
        for future in as_completed(futures):
            url = futures[future]
            processed += 1
            try:
                church = future.result()
                if church:
                    results.append(church)
                    if church.get("email"):
                        found_email += 1
            except:
                pass
            
            if processed % 50 == 0:
                log("  Scraped %d/%d | Found emails: %d" % (processed, len(all_links), found_email))
                # Save incrementally
                save_results(results)
    
    save_results(results)
    log("\n✅ Complete!")
    log("  Processed: %d" % processed)
    log("  With email: %d" % found_email)
    log("  Total saved: %d" % len(results))
    log("  Output: %s" % OUTPUT)

def save_results(results):
    if not results:
        return
    keys = ["church_name", "denomination", "address", "city", "state", "zip", "phone", "website", "email", "source_url"]
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in results:
            row = {k: r.get(k, "") for k in keys}
            row["denomination"] = "Southern Baptist Convention"
            w.writerow(row)

if __name__ == "__main__":
    main()

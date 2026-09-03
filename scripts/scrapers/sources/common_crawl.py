#!/usr/bin/env python3
"""
Common Crawl Diocese Scraper
=============================
Uses the Common Crawl index to find church/parish listings on diocese
and denominational admin body websites without making direct HTTP requests.

This queries the Common Crawl CDX index for pages under each target domain,
then analyzes page content from the crawl data.

Usage:
    python scripts/scrapers/common_crawl_diocese.py --list           # List targets
    python scripts/scrapers/common_crawl_diocese.py --run           # Run all
    python scripts/scrapers/common_crawl_diocese.py --run --limit=10 # Test run
    python scripts/scrapers/common_crawl_diocese.py --inspect       # Show results
"""
import csv, json, gzip, io, os, re, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
DENOM_DIR = DATA_DIR / "denom"
OUT_DIR = PROJECT_DIR / "data" / "scraped" / "cc_dioceses"

UA = "Mozilla/5.0 (compatible; GrantWizard/1.0; +https://grantwizard.dev)"

def log(msg):
    print(f"[cc] {msg}")
    sys.stdout.flush()

# ─── Target Sources ────────────────────────────────────────────────

def load_catholic_dioceses():
    """Load 195 US Catholic dioceses from compiled JSON."""
    path = DATA_DIR / "catholic_dioceses.json"
    if not path.exists():
        log(f"File not found: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for d in data:
        results.append({
            "name": d.get("name", ""),
            "url": d.get("website", ""),
            "state": d.get("state", ""),
            "type": "catholic_diocese",
            "tradition": "Roman Catholic",
        })
    log(f"Loaded {len(results)} Catholic dioceses")
    return results

# ─── Common Crawl CDX Query ────────────────────────────────────────

def query_cc_index(domain, max_pages=1000, retries=2):
    """
    Query the Common Crawl CDX index for pages under a domain.
    Uses the official Index API at http://index.commoncrawl.org/
    """
    from urllib.parse import quote
    
    # Normalize domain - strip protocol and trailing slash
    domain = re.sub(r'^https?://', '', domain)
    domain = re.sub(r'/$', '', domain)
    domain = domain.strip()
    
    # Use CC-MAIN-2025 (latest completed crawl) or fallback
    # Try most recent crawls in order
    crawls = [
        "CC-MAIN-2025-18",
        "CC-MAIN-2025-13",
        "CC-MAIN-2025-09",
        "CC-MAIN-2025-05",
        "CC-MAIN-2024-52",
        "CC-MAIN-2024-46",
        "CC-MAIN-2024-42",
        "CC-MAIN-2024-38",
        "CC-MAIN-2024-34",
    ]
    
    # URL pattern: match pages under this domain
    url_pattern = f"*.{domain}/*"
    
    all_results = []
    for crawl in crawls:
        if len(all_results) >= max_pages:
            break
        
        api_url = f"http://index.commoncrawl.org/{crawl}-index"
        params = {
            "url": url_pattern,
            "output": "json",
            "limit": min(10000, max_pages),
            "fl": "url,status,filename,offset,length,mime",
        }
        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        full_url = f"{api_url}?{qs}"
        
        for attempt in range(retries):
            try:
                r = urllib.request.Request(full_url, headers={"User-Agent": UA})
                with urllib.request.urlopen(r, timeout=30) as f:
                    raw = f.read().decode("utf-8", "replace")
                for line in raw.strip().split("\n"):
                    if line:
                        try:
                            entry = json.loads(line)
                            all_results.append(entry)
                        except:
                            pass
                log(f"  {crawl}: {len(raw.splitlines())} results from {domain}")
                time.sleep(0.5)  # Rate limit
                break
            except Exception as e:
                log(f"  {crawl} attempt {attempt+1} failed: {str(e)[:60]}")
                time.sleep(1)
    
    return all_results

# ─── Content Analysis ──────────────────────────────────────────────

def fetch_cc_content(filename, offset, length):
    """Fetch actual page content from Common Crawl WARC data."""
    # Common Crawl WARC files are stored as compressed chunks
    # Access via AWS or HTTP
    base_url = "https://data.commoncrawl.org/"
    warc_path = filename  # e.g., "crawl-data/CC-MAIN-2025-18/..."
    
    try:
        url = base_url + warc_path
        # Request specific byte range
        r = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Range": f"bytes={offset}-{offset + length - 1}"
        })
        with urllib.request.urlopen(r, timeout=30) as f:
            # The response is gzipped WARC content
            raw = f.read()
            # Try to decompress and parse
            try:
                decompressed = gzip.decompress(raw)
                text = decompressed.decode("utf-8", "replace")
                return text
            except:
                return raw.decode("utf-8", "replace")
    except Exception as e:
        return None

def is_church_directory_page(url, mime):
    """Check if a URL looks like a church directory/listing page."""
    if mime and "html" not in mime:
        return False
    
    url_lower = url.lower()
    # Patterns indicating directory/listings
    dir_patterns = [
        "/parish", "/parishes", "/church", "/churches",
        "/directory", "/listing", "/listings", "/find-a-church",
        "/findachurch", "/congregation", "/congregations",
        "/search", "/locations", "/locator", "/finder",
        "/about/parishes", "/our-parishes", "/parish-locator",
        "/worship/parishes", "/mass-times", "/mass",
    ]
    for pat in dir_patterns:
        if pat in url_lower:
            return True
    
    # Homepage
    if url_lower.count("/") <= 3 and not url_lower.endswith((".jpg",".png",".pdf",".css",".js")):
        return True
    
    return False

def extract_parish_links(html_content, base_domain):
    """From HTML content, extract links that look like parish/church pages."""
    if not html_content:
        return []
    
    parishes = []
    
    # Pattern: links containing parish names
    patterns = [
        # <a href="...">St. Mary</a> or <a href="...">St Mary Church</a>
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(St\.?\s*[^<]{5,80}?)\s*</a>',
        # <a href="...">Our Lady of ...</a>
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Our\s+(?:Lady|Mother|Lord)[^<]{5,80}?)\s*</a>',
        # <a href="...">Holy ... Church</a>
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Holy\s+[^<]{5,80}?)\s*</a>',
        # <a href="...">Sacred Heart</a>
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Sacred\s+Heart[^<]{0,50}?)\s*</a>',
        # JSON-LD with @type=Church or @type=CatholicChurch
        r'{"@type"\s*:\s*"(?:Catholic)?Church"[^}]*"name"\s*:\s*"([^"]+)"[^}]*"url"\s*:\s*"([^"]+)"',
        r'{"@type"\s*:\s*"(?:Catholic)?Church"[^}]*"url"\s*:\s*"([^"]+)"[^}]*"name"\s*:\s*"([^"]+)"',
    ]
    
    for pat in patterns:
        matches = re.findall(pat, html_content, re.IGNORECASE | re.DOTALL)
        for m in matches:
            if isinstance(m, tuple):
                href, name = m[0], m[1]
            else:
                href, name = m, ""
            
            href = href.strip() if href else ""
            name = name.strip() if name else ""
            
            if href and not href.startswith("#") and not href.startswith("javascript"):
                if not href.startswith("http"):
                    if href.startswith("/"):
                        href = f"https://{base_domain}{href}"
                    else:
                        href = f"https://{base_domain}/{href}"
                parishes.append({"name": name, "url": href})
    
    return parishes

# ─── Main Pipeline ─────────────────────────────────────────────────

def run(limit=None):
    """Run the full pipeline."""
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # Load targets
    targets = load_catholic_dioceses()
    
    if limit:
        targets = targets[:limit]
    
    log(f"Processing {len(targets)} diocese websites via Common Crawl...")
    
    all_results = []
    
    for i, target in enumerate(targets):
        domain = re.sub(r'^https?://', '', target["url"]).split("/")[0]
        log(f"[{i+1}/{len(targets)}] {target['name']} ({domain})")
        
        if not domain:
            continue
        
        # Query Common Crawl index
        pages = query_cc_index(domain, max_pages=500)
        
        # Filter to directory/relevant pages
        dir_pages = [p for p in pages if is_church_directory_page(p.get("url",""), p.get("mime",""))]
        
        # Extract parish links from crawled content
        found_parishes = set()
        for dp in dir_pages[:20]:  # Limit content fetches
            content = fetch_cc_content(dp.get("filename",""), int(dp.get("offset",0)), int(dp.get("length",0)))
            parishes = extract_parish_links(content, domain)
            for p in parishes:
                key = (p["url"], p["name"])
                if key not in found_parishes:
                    found_parishes.add(key)
                    all_results.append({
                        "diocese": target["name"],
                        "diocese_url": target["url"],
                        "state": target["state"],
                        "parish_name": p["name"],
                        "parish_url": p["url"],
                        "match_type": "common_crawl",
                    })
        
        log(f"  Pages in CC index: {len(pages)}, directory pages: {len(dir_pages)}, parishes found: {len(found_parishes)}")
        
        # Save incremental
        if all_results:
            outf = OUT_DIR / f"results_{domain.replace('.','_')}.json"
            with open(outf, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2)
        
        time.sleep(1)  # Rate limit CDX API
    
    # Save combined results
    combined_path = OUT_DIR / "all_results.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    
    # Also export CSV
    csv_path = DATA_DIR / "cc_diocese_parishes.csv"
    if all_results:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=all_results[0].keys())
            w.writeheader()
            w.writerows(all_results)
    
    log(f"\n{'='*60}")
    log(f"Complete! {len(all_results)} parish links found across {len(targets)} dioceses")
    log(f"Results: {combined_path}")
    log(f"CSV: {csv_path}")

def list_targets():
    """List available targets."""
    targets = load_catholic_dioceses()
    print(f"\n{'='*60}")
    print(f"Total diocese targets: {len(targets)}")
    print(f"{'='*60}")
    for t in targets:
        print(f"  {t['state']:5s} {t['name']:40s} {t['url']}")

def show_results():
    """Show accumulated results."""
    path = DATA_DIR / "cc_diocese_parishes.csv"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            r = csv.DictReader(f)
            rows = list(r)
        print(f"\n{'='*60}")
        print(f"Total church/parish links found: {len(rows)}")
        print(f"{'='*60}")
        for row in rows[:20]:
            print(f"  {row['state']:5s} {row['parish_name'][:40]:40s} {row['parish_url']}")
        if len(rows) > 20:
            print(f"  ... and {len(rows)-20} more")
    else:
        print("No results yet. Run with --run first.")

if __name__ == "__main__":
    if "--list" in sys.argv:
        list_targets()
    elif "--run" in sys.argv:
        limit = None
        for a in sys.argv:
            if a.startswith("--limit="):
                limit = int(a.split("=")[1])
        run(limit=limit)
    elif "--inspect" in sys.argv:
        show_results()
    else:
        print(__doc__)

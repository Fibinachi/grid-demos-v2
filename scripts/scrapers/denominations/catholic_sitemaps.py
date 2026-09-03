#!/usr/bin/env python3
"""
Sitemap Parish Harvester
========================
Fetches diocese sitemaps, extracts all parish/church URLs,
and saves them to CSV for import.

Usage:
    python scripts/scrapers/harvest_parishes_from_sitemaps.py
    python scripts/scrapers/harvest_parishes_from_sitemaps.py --limit=20
    python scripts/scrapers/harvest_parishes_from_sitemaps.py --resume
"""
import csv, json, os, re, sys, time, urllib.request, urllib.error
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

PROJECT_DIR = Path(r"E:\grid")
DATA_DIR = PROJECT_DIR / "data"
DIOCESE_JSON = DATA_DIR / "catholic_dioceses.json"
OUTPUT_CSV = DATA_DIR / "diocese_parishes_from_sitemaps.csv"
STATE_FILE = DATA_DIR / "sitemap_harvest_state.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def fetch_xml(url, timeout=15):
    """Fetch an XML sitemap."""
    for attempt in range(2):
        try:
            r = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/xml,text/xml,*/*;q=0.9",
            })
            with urllib.request.urlopen(r, timeout=timeout) as f:
                return f.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
            else:
                return None
    return None

def parse_sitemap(xml, base_url):
    """
    Parse a sitemap XML. Returns (urls_list, is_index, child_sitemaps).
    """
    if not xml:
        return [], False, []
    
    urls = re.findall(r'<loc[^>]*>(.*?)</loc>', xml, re.DOTALL)
    
    # Check if it's a sitemap index (links to other sitemaps)
    is_index = "<sitemapindex" in xml.lower() or any("sitemap" in u.lower() and u.endswith(".xml") for u in urls[:5])
    
    # For a sitemap index, the URLs point to child sitemaps
    child_sitemaps = []
    actual_urls = []
    
    for u in urls:
        u = u.strip()
        # CDATA
        if u.startswith("<![CDATA[") and u.endswith("]]>"):
            u = u[9:-3]
        
        if is_index or u.endswith(".xml"):
            child_sitemaps.append(u)
        else:
            actual_urls.append(u)
    
    return actual_urls, is_index, child_sitemaps

def extract_parish_name_from_url(url):
    """Try to extract a parish name from a URL path."""
    # Remove domain, split path
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    
    # Common patterns for parish URLs
    # /parish/st-mary-catholic-church
    # /location/st-joseph-church
    # /parishes/st-anne
    # /churches/st-patrick
    
    # Look for parish indicators in path
    indicators = ["parish", "parishes", "location", "church", "churches"]
    name = ""
    
    for i, part in enumerate(parts):
        if part.lower() in indicators and i + 1 < len(parts):
            name = parts[i + 1]
            break
    
    if not name and parts:
        # Try last part
        last = parts[-1]
        # Only if it looks like a church name (has st-, our-, holy-, sacred-)
        if re.search(r'^(st-|our-|holy-|sacred-|immaculate-|blessed-|christ-|saint)', last, re.I):
            name = last
    
    # Clean up name
    if name:
        name = name.replace("-", " ").replace("_", " ").title()
        # Fix "St " -> "St. "
        name = re.sub(r'\bSt\b', 'St.', name)
        name = re.sub(r'\bSt\.\s+', 'St. ', name)
    
    # Fallback: extract from URL
    if not name:
        # Try to find meaningful info
        parts = [p for p in parts if not re.match(r'^\d+$', p) and p not in ('wp-content', 'uploads', 'index')]
        if parts:
            name = parts[-1].replace("-", " ").replace("_", " ").title()
    
    return name[:100]

def is_parish_url(url):
    """Check if a URL looks like a parish/church page."""
    url_lower = url.lower()
    
    # Must be HTML page, not a file
    if re.search(r'\.(jpg|jpeg|png|gif|pdf|css|js|zip|xml|json)$', url_lower):
        return False
    
    # Skip obvious non-parish pages
    skip_patterns = [
        "/events/", "/calendar/", "/blog/", "/news/", "/contact",
        "/about/", "/staff/", "/donate/", "/giving/", "/employment",
        "/jobs/", "/careers/", "/volunteer/", "/privacy", "/login",
        "/wp-", "/feed/", "/tag/", "/author/", "/category/",
        "/comment", "/search", "/page/", "/amp/",
    ]
    for pat in skip_patterns:
        if pat in url_lower:
            return False
    
    # Positive indicators
    parish_indicators = [
        "/parish/", "/parishes/", "/location/", "/church/", "/churches/",
        "-catholic-church", "-parish", "st-", "saint-",
        "our-lady-", "holy-", "sacred-heart-", "immaculate-",
        "blessed-sacrament-", "blessed-virgin-", "christ-the-king-",
        "st.-", "st-",
    ]
    for ind in parish_indicators:
        if ind in url_lower:
            return True
    
    return False

def collect_all_sitemap_urls(sitemap_url, max_child_sitemaps=30, depth=0):
    """
    Recursively fetch sitemap URLs, following sitemap indexes.
    Returns a flat list of all URLs found.
    """
    if depth > 3:
        return []  # Prevent infinite recursion
    
    xml = fetch_xml(sitemap_url)
    if not xml:
        return []
    
    locs = re.findall(r'<loc[^>]*>(.*?)</loc>', xml, re.DOTALL)
    
    urls = []
    child_sitemaps = []
    
    for u in locs:
        u = u.strip()
        # Handle CDATA
        if u.startswith("<![CDATA[") and u.endswith("]]>"):
            u = u[9:-3]
        
        # Check if it links to another sitemap
        if ".xml" in u.lower() and ("sitemap" in u.lower() or depth > 0):
            child_sitemaps.append(u)
        else:
            urls.append(u)
    
    # If we found very few URLs and have child sitemaps, this is likely a sitemap index
    if len(urls) < 5 and child_sitemaps:
        urls = []
        for child_url in child_sitemaps[:max_child_sitemaps]:
            time.sleep(0.2)
            child_urls = collect_all_sitemap_urls(child_url, max_child_sitemaps, depth + 1)
            urls.extend(child_urls)
    
    # If depth == 0, log what we found
    if depth == 0:
        log(f"  Index: {bool(child_sitemaps)}, Direct: {len(urls)}, Child sitemaps: {len(child_sitemaps)}")
    
    return urls

def fetch_all_parish_urls(diocese_entry):
    """
    For a diocese, fetch its sitemap and extract ALL URLs.
    Aggressively follows sitemap indexes to get every page.
    """
    name = diocese_entry.get("name", "")
    state = diocese_entry.get("state", "")
    sitemap_url = diocese_entry.get("sitemap_url", "")
    diocese_url = diocese_entry.get("website", "")
    
    if not sitemap_url:
        return []
    
    domain = urlparse(diocese_url).netloc.lower() if diocese_url else ""
    
    log(f"  Sitemap: {sitemap_url}")
    
    # Collect ALL URLs from sitemap tree
    all_urls = collect_all_sitemap_urls(sitemap_url, max_child_sitemaps=30)
    log(f"  Total URLs in sitemap tree: {len(all_urls)}")
    
    # Clean URLs
    seen = set()
    clean_urls = []
    for u in all_urls:
        u_clean = u.split("#")[0].strip().rstrip("/")
        if u_clean and u_clean not in seen:
            seen.add(u_clean)
            
            # Skip non-HTML resources
            if re.search(r'\.(jpg|jpeg|png|gif|svg|pdf|css|js|zip|xml|json|ico|woff|ttf|eot)$', u_clean, re.I):
                continue
            
            clean_urls.append(u_clean)
    
    log(f"  After cleaning: {len(clean_urls)}")
    
    # Extract parish names from URLs
    results = []
    for url in clean_urls:
        parish_name = extract_parish_name_from_url(url)
        results.append({
            "diocese": name,
            "state": state,
            "parish_name": parish_name.strip() if parish_name else "",
            "parish_url": url,
            "diocese_url": diocese_url,
            "source": "sitemap",
        })
    
    log(f"  → {len(results)} entries")
    return results

def main():
    with open(DIOCESE_JSON, encoding="utf-8") as f:
        dioceses = json.load(f)
    
    # Filter to those with sitemaps
    with_sitemaps = [d for d in dioceses if d.get("has_sitemap") and d.get("sitemap_url")]
    log(f"Total dioceses: {len(dioceses)}, with sitemaps: {len(with_sitemaps)}")
    
    # Load state
    state = {"done": []}
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
    
    done_names = set(state.get("done", []))
    
    limit = None
    for a in sys.argv:
        if a.startswith("--limit="):
            limit = int(a.split("=")[1])
    
    # Load existing results
    all_parishes = []
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, encoding="utf-8") as f:
            all_parishes = list(csv.DictReader(f))
        log(f"Existing results: {len(all_parishes)} parishes")
    
    existing_urls = {r["parish_url"].lower().rstrip("/") for r in all_parishes}
    
    to_process = [d for d in with_sitemaps if d["name"] not in done_names]
    if limit:
        to_process = to_process[:limit]
    
    log(f"To process: {len(to_process)} dioceses")
    
    for i, d in enumerate(to_process):
        log(f"\n[{i+1}/{len(to_process)}] {d['name']} ({d.get('state','')}) CMS: {d.get('cms','?')}")
        
        parishes = fetch_all_parish_urls(d)
        
        # Filter against existing
        new_parishes = [p for p in parishes if p["parish_url"].lower().rstrip("/") not in existing_urls]
        log(f"  New: {len(new_parishes)} / {len(parishes)} total")
        
        all_parishes.extend(new_parishes)
        for p in new_parishes:
            existing_urls.add(p["parish_url"].lower().rstrip("/"))
        
        done_names.add(d["name"])
        
        # Save incrementally
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "diocese", "state", "parish_name", "parish_url",
                "diocese_url", "source"
            ])
            w.writeheader()
            w.writerows(all_parishes)
        
        with open(STATE_FILE, "w") as f:
            json.dump({"done": list(done_names), "total": len(all_parishes),
                        "updated": datetime.now().isoformat()}, f, indent=2)
        
        time.sleep(0.5)
    
    # Summary
    by_state = Counter(p["state"] for p in all_parishes)
    by_diocese = Counter(p["diocese"] for p in all_parishes)
    
    print(f"\n{'='*60}")
    print(f"Complete!")
    print(f"Total parishes found: {len(all_parishes):,}")
    print(f"From {len(done_names)} dioceses")
    print(f"\nTop states:")
    for s, n in by_state.most_common(10):
        print(f"  {n:>5,}  {s}")
    print(f"\nTop dioceses:")
    for d, n in by_diocese.most_common(10):
        print(f"  {n:>5,}  {d[:50]}")
    print(f"\nFile: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Diocese Website Scraper — Direct HTTP
======================================
Scrapes Catholic diocese websites for parish/church directory pages
using direct HTTP requests (urllib/cloudscraper).

Strategy per diocese:
1. Fetch homepage, look for "Find a Church", "Parish Directory", "Parishes" links
2. Fetch directory pages, extract parish info
3. Save results as CSV for later enrichment

Usage:
    python scripts/scrapers/scrape_dioceses.py --list
    python scripts/scrapers/scrape_dioceses.py --run
    python scripts/scrapers/scrape_dioceses.py --run --limit=10
    python scripts/scrapers/scrape_dioceses.py --resume
"""
import csv, json, os, re, sys, time, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from collections import Counter

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
STATE_FILE = DATA_DIR / "diocese_scrape_state.json"
OUTPUT_CSV = DATA_DIR / "diocese_parishes.csv"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

# ─── Load Targets ──────────────────────────────────────────────────

def load_targets():
    """Load 195 US Catholic dioceses."""
    path = DATA_DIR / "catholic_dioceses.json"
    if not path.exists():
        log(f"File not found: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ─── Scraping ──────────────────────────────────────────────────────

def fetch(url, timeout=20):
    """Fetch a URL with retries."""
    for attempt in range(3):
        try:
            r = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            })
            with urllib.request.urlopen(r, timeout=timeout) as f:
                html = f.read().decode("utf-8", "replace")
                if len(html) > 100:
                    return html
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return None  # Blocked
            time.sleep(2**attempt)
        except Exception:
            time.sleep(2**attempt)
    return None

def find_directory_links(html, base_url):
    """Find links to directory/parish listing pages in homepage HTML."""
    if not html:
        return []
    
    links = []
    base_domain = urlparse(base_url).netloc.lower()
    
    # Keywords suggesting a directory page
    dir_keywords = [
        (r'find[-\s]*(?:a\s+)?church', "find-a-church"),
        (r'parish[-\s]*(?:locator|finder|directory|search)', "parish-directory"),
        (r'(?:our\s+)?parishes', "parishes"),
        (r'church\s+(?:directory|locator|finder|search)', "church-directory"),
        (r'mass[-\s]*(?:times|finder|locator|schedule)', "mass-times"),
        (r'location', "locations"),
        (r'worship[-\s]*(?:locator|times)', "worship"),
    ]
    
    for pattern, label in dir_keywords:
        matches = re.findall(
            r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>.*?' + pattern + r'.*?</a>',
            html, re.IGNORECASE | re.DOTALL
        )
        for href in matches:
            full_url = urljoin(base_url, href)
            if base_domain in urlparse(full_url).netloc.lower():
                links.append((full_url, label))
    
    # Also check navbar/header links
    nav_patterns = [
        r'<nav[^>]*>.*?(?:<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>.*?(?:parish|directory|find|church|location).*?</a>).*?</nav>',
    ]
    for pat in nav_patterns:
        nav_matches = re.findall(pat, html, re.IGNORECASE | re.DOTALL)
        for href in nav_matches:
            full_url = urljoin(base_url, href)
            if base_domain in urlparse(full_url).netloc.lower():
                links.append((full_url, "nav-link"))
    
    return list(set(links))  # Deduplicate

def extract_parishes(html, base_url):
    """Extract parish names and URLs from a directory listing page."""
    if not html:
        return []
    
    parishes = []
    base_domain = urlparse(base_url).netloc.lower()
    
    # Pattern 1: JSON-LD structured data
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                items = data
            else:
                items = [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in ("CatholicChurch", "Church", "Place"):
                    name = item.get("name", "")
                    url = item.get("url", "")
                    parishes.append({"name": name, "url": url})
        except:
            pass
    
    # Pattern 2: Links with church-sounding text
    church_patterns = [
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(St\.?\s+[A-Z][^<]{3,80}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Our\s+(?:Lady|Mother|Lord)\s+[^<]{3,80}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Holy\s+(?:Cross|Family|Trinity|Spirit|Name|Innocents|Rosary|Ghost|Redeemer)[^<]{3,80}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Sacred\s+Heart[^<]{0,50}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Immaculate\s+(?:Conception|Heart)[^<]{0,50}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Blessed\s+(?:Sacrament|Virgin)[^<]{0,50}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(Christ\s+(?:the\s+)?King[^<]{0,50}?)\s*</a>',
        r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>\s*(St\.?\s+[A-Z][^<]{3,80}?\s+(?:Church|Parish|Catholic))\s*</a>',
    ]
    
    seen = set()
    for pat in church_patterns:
        for m in re.finditer(pat, html, re.IGNORECASE):
            href, name = m.groups()
            full_url = urljoin(base_url, href.strip())
            name = re.sub(r'\s+', ' ', name.strip())
            
            # Deduplicate
            key = (name.lower(), full_url.lower())
            if key in seen:
                continue
            seen.add(key)
            
            # Only keep URLs on the same domain
            if base_domain in urlparse(full_url).netloc.lower():
                parishes.append({"name": name, "url": full_url})
    
    # Pattern 3: Table/list of parishes
    # Look for div/ul containing multiple church entries
    list_items = re.findall(
        r'<(?:li|div|tr)[^>]*class="[^"]*(?:parish|church|location)[^"]*"[^>]*>'
        r'(.*?)</(?:li|div|tr)>', html, re.IGNORECASE | re.DOTALL
    )
    for item in list_items:
        link = re.search(r'<a\s+(?:[^>]*?\s)?href="([^"]*)"[^>]*>(.*?)</a>', item, re.DOTALL)
        if link:
            href, text = link.groups()
            text = re.sub(r'<[^>]+>', '', text).strip()
            full_url = urljoin(base_url, href)
            name = re.sub(r'\s+', ' ', text)[:100]
            key = (name.lower(), full_url.lower())
            if key not in seen and name and len(name) > 5:
                seen.add(key)
                if base_domain in urlparse(full_url).netloc.lower():
                    parishes.append({"name": name, "url": full_url})
    
    return parishes

def scrape_diocese(target):
    """Scrape a single diocese website."""
    url = target.get("website", "").strip()
    name = target.get("name", "")
    state = target.get("state", "")
    
    if not url:
        return {"target": name, "state": state, "status": "no_url", "parishes": []}
    
    if not url.startswith("http"):
        url = "https://" + url
    
    log(f"  Fetching {url}")
    html = fetch(url)
    if not html:
        log(f"  ✗ Blocked / unreachable")
        return {"target": name, "state": state, "status": "blocked", "parishes": []}
    
    # Find directory pages
    dir_links = find_directory_links(html, url)
    log(f"  Found {len(dir_links)} directory links")
    
    all_parishes = []
    
    # Extract parishes from homepage first
    home_parishes = extract_parishes(html, url)
    all_parishes.extend(home_parishes)
    log(f"  Homepage parishes: {len(home_parishes)}")
    
    # Visit up to 3 directory pages
    for dir_url, label in dir_links[:3]:
        log(f"    Fetching {label}: {dir_url}")
        dir_html = fetch(dir_url)
        if dir_html:
            parishes = extract_parishes(dir_html, dir_url)
            log(f"    Found {len(parishes)} parishes")
            all_parishes.extend(parishes)
        time.sleep(1)
    
    # Deduplicate
    seen = set()
    unique = []
    for p in all_parishes:
        key = p["url"].lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    return {
        "target": name,
        "state": state,
        "status": "ok",
        "parishes": unique,
    }

# ─── Main ──────────────────────────────────────────────────────────

def main():
    targets = load_targets()
    
    if "--list" in sys.argv:
        print(f"\nTotal diocese targets: {len(targets)}")
        for t in targets:
            print(f"  {t.get('state','?'):5s} {t['name'][:45]:45s} {t.get('website','')}")
        return
    
    # Load state
    state = {}
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
    
    limit = None
    for a in sys.argv:
        if a.startswith("--limit="):
            limit = int(a.split("=")[1])
    
    resume_from = state.get("last_index", -1) + 1 if "--resume" in sys.argv else 0
    targets_to_process = targets[resume_from:]
    
    # --missing: skip dioceses already in output CSV
    if "--missing" in sys.argv and OUTPUT_CSV.exists():
        existing_rows = list(csv.DictReader(open(OUTPUT_CSV, encoding="utf-8")))
        scraped_dioceses = set(r["diocese"] for r in existing_rows)
        before = len(targets_to_process)
        targets_to_process = [t for t in targets_to_process if t["name"] not in scraped_dioceses]
        skipped = before - len(targets_to_process)
        if skipped:
            log(f"Skipped {skipped} already-scraped dioceses")
    
    if limit:
        targets_to_process = targets_to_process[:limit]
    
    log(f"Processing {len(targets_to_process)} dioceses (starting from index {resume_from})...")
    
    all_results = []
    for i, target in enumerate(targets_to_process):
        idx = resume_from + i
        log(f"\n[{idx+1}/{len(targets)}] {target['name']}")
        
        result = scrape_diocese(target)
        all_results.append(result)
        
        # Save state
        state["last_index"] = idx
        state["last_target"] = target["name"]
        state["updated"] = datetime.now().isoformat()
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        
        # Slow down
        time.sleep(1.5)
    
    # Generate output CSV
    rows = []
    for r in all_results:
        for p in r.get("parishes", []):
            rows.append({
                "diocese": r["target"],
                "state": r["state"],
                "status": r["status"],
                "parish_name": p["name"],
                "parish_url": p["url"],
            })
    
    if rows:
        # Append to existing
        existing = []
        if OUTPUT_CSV.exists():
            with open(OUTPUT_CSV, encoding="utf-8") as f:
                existing = list(csv.DictReader(f))
        
        # Deduplicate against existing
        existing_urls = {r["parish_url"].lower().rstrip("/") for r in existing}
        new_rows = [r for r in rows if r["parish_url"].lower().rstrip("/") not in existing_urls]
        
        all_rows = existing + new_rows
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(all_rows)
        
        log(f"\n{'='*60}")
        log(f"Done! {len(new_rows)} new parish links found")
        log(f"Total in CSV: {len(all_rows)}")
        log(f"File: {OUTPUT_CSV}")
    else:
        log("No results found.")

if __name__ == "__main__":
    main()

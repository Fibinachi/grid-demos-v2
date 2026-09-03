#!/usr/bin/env python3
"""
Facebook Church Page Scraper
=============================
Searches for church Facebook pages and extracts structured contact data.
Targets churches in the DB without existing Facebook URLs.

Strategy:
1. If church has a website, check for Facebook link on the homepage
2. Google search: site:facebook.com "church name" "city" "state"
3. Direct Facebook search as fallback
4. Scrape the Facebook page for contact info

Usage:
    python scripts/enrichment/facebook_scraper.py                    # Run full pipeline (local DB)
    python scripts/enrichment/facebook_scraper.py --limit 100        # First 100 churches
    python scripts/enrichment/facebook_scraper.py --state SC         # Only SC churches
    python scripts/enrichment/facebook_scraper.py --resume           # Resume from checkpoint
"""
import csv, json, os, re, sqlite3, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "facebook")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "facebook_pages.csv")
CHECKPOINT = os.path.join(OUT_DIR, "facebook_checkpoint.json")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]
UA_CYCLE = [0]
UA_LOCK = Lock()

def next_ua():
    with UA_LOCK:
        ua = USER_AGENTS[UA_CYCLE[0] % len(USER_AGENTS)]
        UA_CYCLE[0] += 1
        return ua

log_lock = Lock()
def log(msg):
    with log_lock:
        print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def fetch(url, timeout=15):
    """Fetch a URL with rotating User-Agent."""
    try:
        r = urllib.request.Request(url, headers={
            "User-Agent": next_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except Exception:
        return None

def find_fb_on_website(website):
    """Check a church's website for Facebook links."""
    if not website:
        return None
    try:
        html = fetch(website, timeout=10)
        if not html:
            return None
        # Look for Facebook URLs in the page
        patterns = [
            r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9.]+(?:/[a-zA-Z0-9.]+)?',
            r'https?://(?:www\.)?fb\.com/[a-zA-Z0-9.]+',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html, re.IGNORECASE):
                url = m.group(0).rstrip("/")
                # Filter out generic/share URLs
                if any(k in url.lower() for k in ["share", "sharer", "plugins", "dialog", "like"]):
                    continue
                # Filter out very short URLs (usually not pages)
                page_id = url.split("facebook.com/")[-1] if "facebook.com" in url else url.split("fb.com/")[-1]
                if len(page_id) > 3 and page_id != "pages":
                    return url
    except:
        pass
    return None

def google_search_fb(church_name, city, state):
    """Search Google for the church's Facebook page."""
    query = 'site:facebook.com "%s" "%s" "%s" church' % (church_name[:40], city[:20], state)
    search_url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    html = fetch(search_url, timeout=10)
    if not html:
        return None
    
    # Extract Facebook URLs from search results
    for m in re.finditer(r'https?://(?:www\.|m\.|web\.)?facebook\.com/[a-zA-Z0-9.]+(?:/[a-zA-Z0-9.]+)?', html, re.IGNORECASE):
        url = m.group(0).rstrip("/")
        if any(k in url.lower() for k in ["share", "sharer", "plugins", "dialog", "like", "login"]):
            continue
        page_id = url.split("facebook.com/")[-1]
        if len(page_id) > 3 and page_id != "pages":
            return url
    return None

def scrape_fb_page(page_url):
    """Scrape a public Facebook page for structured data."""
    result = {
        "page_url": page_url,
        "page_name": "",
        "category": "",
        "phone": "",
        "email": "",
        "website": "",
        "address": "",
        "city": "",
        "state": "",
        "zip": "",
        "service_times": [],
        "about_text": "",
        "staff_list": [],
        "follower_count": None,
        "created_date": "",
    }
    
    if not page_url:
        return result
    
    # Try to get the mobile version (simpler HTML)
    for try_url in [page_url.replace("www.", "m."), page_url, page_url + "/about"]:
        html = fetch(try_url, timeout=15)
        if not html:
            continue
        
        # Extract page name from title
        m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        if m:
            title = re.sub(r'\s+', ' ', m.group(1)).strip()
            # Facebook titles often have " | Facebook" or " - Facebook" suffix
            title = re.sub(r'\s*[|-]\s*Facebook\s*$', '', title, flags=re.I).strip()
            result["page_name"] = title
        
        # Extract category
        # Facebook pages have category info in meta or visible text
        for pat in [r'"category"[^:]*:\s*"([^"]+)"', r'class="[^"]*category[^"]*"[^>]*>([^<]+)<']:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                result["category"] = m.group(1).strip()
                break
        
        # Extract about text
        for pat in [r'"about"[^:]*:\s*"([^"]+)"', r'class="[^"]*about[^"]*"[^>]*>([^<]+)<']:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                result["about_text"] = m.group(1).strip()[:500]
                break
        
        # Extract phone
        for m in re.finditer(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html):
            p = m.group(0)
            digits = re.sub(r'\D', '', p)
            if len(digits) == 10:
                result["phone"] = "+1" + digits
                break
        
        # Extract email
        for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html):
            e = m.group(0).lower()
            if "facebook.com" not in e and "example.com" not in e and "test.com" not in e:
                result["email"] = e
                break
        
        # Extract website from Facebook page
        m = re.search(r'https?://(?:www\.)?(?!facebook\.com|fb\.com)[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s"\'<>&]*)?', html)
        if m:
            url = m.group(0).strip()
            if not any(d in url.lower() for d in ["facebook.com", "fb.com", "google.com", "youtube.com", "instagram.com"]):
                result["website"] = url
        
        # Extract address components
        for pat in [r'"street"[^:]*:\s*"([^"]+)"', r'"address"[^:]*:\s*"([^"]+)"']:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                result["address"] = m.group(1).strip()
                break
        for m in re.search(r'([A-Z][A-Za-z .]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?', html):
            if m:
                result["city"] = m.group(1).strip()
                result["state"] = m.group(2).strip()
                if m.group(3):
                    result["zip"] = m.group(3).strip()
                break
        
        # Extract follower count
        for pat in [r'(\d[\d,]*)\s*(?:followers?|likes?)', r'"follower_count"[^:]*:\s*(\d+)']:
            for m in re.finditer(pat, html, re.IGNORECASE):
                try:
                    result["follower_count"] = int(m.group(1).replace(",", ""))
                except:
                    pass
                break
        
        break  # Only need one successful page load
    
    return result

def process_church(row):
    """Process a single church: find Facebook page and scrape data."""
    church_id = row["id"]
    name = row["name"]
    city = row.get("city", "")
    state = row.get("state", "")
    website = row.get("website", "")
    
    result = {
        "church_id": church_id,
        "church_name": name,
        "facebook_page_found": False,
        "page_url": "",
        "page_name": "",
        "category": "",
        "phone": "",
        "email": "",
        "website": "",
        "address": "",
        "city": "",
        "state": "",
        "zip": "",
        "service_times": "",
        "about_text": "",
        "staff_list": "",
        "follower_count": "",
        "created_date": "",
        "source": "",
        "error": "",
    }
    
    page_url = None
    source = ""
    
    # Strategy 1: Check church's website for Facebook links
    if website:
        fb = find_fb_on_website(website)
        if fb:
            page_url = fb
            source = "website_link"
            time.sleep(0.5)
    
    # Strategy 2: Google search for Facebook page
    if not page_url and city and state:
        fb = google_search_fb(name, city, state)
        if fb:
            page_url = fb
            source = "google_search"
            time.sleep(1.0)
    
    # Strategy 3: Try name-only search
    if not page_url:
        fb = google_search_fb(name, "", state)
        if fb:
            page_url = fb
            source = "google_search_name_only"
            time.sleep(1.0)
    
    if page_url:
        result["facebook_page_found"] = True
        result["source"] = source
        
        # Scrape the Facebook page
        fb_data = scrape_fb_page(page_url)
        result["page_url"] = fb_data["page_url"]
        result["page_name"] = fb_data["page_name"]
        result["category"] = fb_data["category"]
        result["phone"] = fb_data["phone"]
        result["email"] = fb_data["email"]
        result["website"] = fb_data.get("website", "")
        result["address"] = fb_data["address"]
        result["city"] = fb_data.get("city", "")
        result["state"] = fb_data.get("state", "")
        result["zip"] = fb_data.get("zip", "")
        result["service_times"] = json.dumps(fb_data["service_times"])
        result["about_text"] = fb_data["about_text"][:500]
        result["staff_list"] = json.dumps(fb_data["staff_list"])
        result["follower_count"] = str(fb_data["follower_count"]) if fb_data["follower_count"] else ""
        result["created_date"] = fb_data["created_date"]
        
        time.sleep(1.0)  # Rate limit between churches
    else:
        result["error"] = "not_found"
    
    return result

def save_results(results, append=True):
    """Save results to CSV."""
    fieldnames = ["church_id", "church_name", "facebook_page_found", "page_url", "page_name",
                  "category", "phone", "email", "website", "address", "city", "state", "zip",
                  "service_times", "about_text", "staff_list", "follower_count", "created_date",
                  "source", "error"]
    
    mode = "a" if append and os.path.exists(OUT_CSV) else "w"
    with open(OUT_CSV, mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w":
            w.writeheader()
        w.writerows(results)
    
    log("Saved %d results to %s" % (len(results), OUT_CSV))

def save_checkpoint(processed_id):
    with open(CHECKPOINT, "w") as f:
        json.dump({"last_id": processed_id, "updated": datetime.now().isoformat()}, f)

def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        try:
            with open(CHECKPOINT) as f:
                return json.load(f).get("last_id", 0)
        except:
            pass
    return 0

def load_existing_found():
    """Load already-found Facebook URLs to avoid duplicates."""
    found = set()
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("page_url"):
                    found.add(row["page_url"])
                if row.get("church_id"):
                    found.add("id:" + row["church_id"])
    return found

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Limit churches to process")
    parser.add_argument("--state", help="Filter by state")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--no-website", action="store_true", help="Target churches without websites too")
    args = parser.parse_args()
    
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    # Build query - target churches most likely to have Facebook pages
    conditions = []
    
    # Exclude already-processed churches
    existing = load_existing_found()
    
    if args.state:
        conditions.append("state='%s'" % args.state)
    
    # Priority: churches with websites first (more likely to have FB), then without
    if args.no_website:
        # Include churches without websites
        order = "ORDER BY CASE WHEN website != '' THEN 0 ELSE 1 END, RANDOM()"
    else:
        conditions.append("website != ''")
        order = "ORDER BY RANDOM()"
    
    where = " AND ".join(conditions) if conditions else "1=1"
    
    cur.execute("SELECT id, name, city, state, website, phone, denomination FROM churches WHERE %s %s" % (where, order))
    rows = cur.fetchall()
    db.close()
    
    log("Loaded %d churches from DB" % len(rows))
    
    # Convert to dicts
    churches = []
    for r in rows:
        cid = str(r[0])
        if "id:" + cid in existing:
            continue
        churches.append({
            "id": cid,
            "name": r[1],
            "city": r[2] or "",
            "state": r[3] or "",
            "website": r[4] or "",
            "phone": r[5] or "",
            "denomination": r[6] or "",
        })
    
    if args.limit:
        churches = churches[:args.limit]
    
    log("Processing %d churches (%d already done)" % (len(churches), len(existing)))
    
    if args.resume:
        last_id = load_checkpoint()
        churches = [c for c in churches if int(c["id"]) > last_id]
        log("Resuming from church ID %d, %d remaining" % (last_id, len(churches)))
    
    t0 = time.time()
    processed = 0
    found_count = 0
    
    # Process sequentially to avoid overwhelming Facebook
    batch = []
    for church in churches:
        result = process_church(church)
        batch.append(result)
        processed += 1
        if result["facebook_page_found"]:
            found_count += 1
        
        if len(batch) >= 25:
            save_results(batch)
            save_checkpoint(int(church["id"]))
            log("Progress: %d/%d processed, %d found (%.1f%%)" % (
                processed, len(churches), found_count, 100*found_count/processed))
            batch = []
    
    if batch:
        save_results(batch)
        save_checkpoint(int(churches[-1]["id"]) if churches else 0)
    
    elapsed = time.time() - t0
    log("")
    log("=" * 55)
    log("FACEBOOK SCRAPER COMPLETE")
    log("=" * 55)
    log("  Processed: %d" % processed)
    log("  Found: %d (%.1f%%)" % (found_count, 100*found_count/processed if processed else 0))
    log("  Time: %dm %ds" % (elapsed // 60, elapsed % 60))
    log("  Results: %s" % OUT_CSV)

if __name__ == "__main__":
    main()

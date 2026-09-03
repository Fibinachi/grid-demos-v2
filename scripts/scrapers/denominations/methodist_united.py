#!/usr/bin/env python3
"""
Comprehensive Methodist Scraper
================================
Scrapes AME, AME Zion, CME, Free Methodist, Wesleyan directories.

Usage:
    python scripts/scrapers/scrape_methodist.py              # All bodies
    python scripts/scrapers/scrape_methodist.py --body cme   # Single
    python scripts/scrapers/scrape_methodist.py --dry-run
"""
import csv, json, os, re, sqlite3, sys, urllib.request, time
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DELAY = 0.5

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def fetch(url, timeout=15):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except Exception as e:
        return None

def normalize_name(name):
    name = re.sub(r'<[^>]+>', '', name).strip()
    name = re.sub(r'\s+', ' ', name)
    return name.strip(" ,-")

def do_import(results, denomination, source):
    """Import results into DB with matching."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    matched = 0
    inserted = 0
    
    for r in results:
        name = r.get("name", "").upper().strip()
        city = r.get("city", "").upper().strip()
        state = r.get("state", "").upper().strip()
        address = r.get("address", "").strip()
        website = r.get("website", "").strip()
        phone = re.sub(r"\D", "", r.get("phone", ""))[-10:] if r.get("phone") else ""
        
        if not name or not state:
            continue
        
        # Match strategies
        row = None
        for sql, params in [
            ("SELECT id, denomination, website FROM churches WHERE UPPER(name)=? AND state=? LIMIT 1", (name, state)),
            ("SELECT id, denomination, website FROM churches WHERE UPPER(name)=? AND city=? AND state=? LIMIT 1", (name, city, state)),
        ]:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row:
                break
        
        if row:
            matched += 1
            cid, existing_denom, existing_web = row
            updates = []
            uparams = []
            if not existing_denom:
                updates.append("denomination=?")
                uparams.append(denomination)
            if website and not existing_web:
                updates.append("website=?")
                uparams.append(website)
            if phone and len(phone) >= 10:
                updates.append("phone=COALESCE(NULLIF(phone,''),?)")
                uparams.append(phone)
            if address:
                updates.append("address=COALESCE(NULLIF(address,''),?)")
                uparams.append(address)
            if updates:
                uparams.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", uparams)
        else:
            inserted += 1
            cur.execute("""
                INSERT INTO churches (name, city, state, address, zip, phone, website, denomination, source)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (name, city, state, address, r.get("zip", ""), phone, website, denomination, source))
    
    db.commit()
    db.close()
    return matched, inserted

# ─── CME (Christian Methodist Episcopal) ────────────────────────────

def scrape_cme():
    """Scrape CME church directory."""
    log("  CME: Christian Methodist Episcopal...")
    results = []
    url = "https://www.c-m-e.org/churches"
    html = fetch(url)
    if not html:
        log("  CME: Failed to fetch")
        return results
    
    # Try to find church listings in the HTML
    # CME site uses simple HTML lists
    churches = re.findall(r'<li[^>]*>([^<]*(?:Church|Temple|Cathedral|Chapel)[^<]*)</li>', html, re.IGNORECASE)
    for c in churches:
        c = normalize_name(c)
        if c and len(c) > 10:
            results.append({"name": c, "denomination": "Christian Methodist Episcopal Church", "source": "cme_scrape"})
    
    log(f"  CME: Found {len(results)}")
    return results

# ─── Free Methodist ─────────────────────────────────────────────────

def scrape_free_methodist():
    """Scrape Free Methodist churches.
    NOTE: fmcusa.org/find-a-church is JS-rendered (1.3MB page).
    Try alternate API/discovery approaches."""
    log("  Free Methodist...")
    results = []
    
    # Try WordPress REST API
    for wp_url in [
        "https://fmcusa.org/wp-json/wp/v2/church?per_page=100",
        "https://fmcusa.org/wp-json/wp/v2/churches?per_page=100",
        "https://fmcusa.org/wp-json/tribe/events/v1/",
    ]:
        try:
            r = urllib.request.Request(wp_url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(r, timeout=10) as f:
                data = json.loads(f.read().decode())
            log(f"  WP API {wp_url}: found data")
            if isinstance(data, list):
                for item in data:
                    name = item.get("title", {}).get("rendered", "") if isinstance(item.get("title"), dict) else str(item.get("title", ""))
                    if name and len(name) > 5:
                        results.append({"name": name, "denomination": "Free Methodist Church", "source": "fmc_scrape"})
                if results:
                    break
            elif isinstance(data, dict):
                # Check for posts/venues in response
                for key in ["posts", "venues", "events", "data"]:
                    items = data.get(key, [])
                    if isinstance(items, list) and items:
                        for item in items:
                            name = item.get("title", "") or item.get("name", "") or item.get("post_title", "")
                            if name:
                                results.append({"name": str(name), "denomination": "Free Methodist Church", "source": "fmc_scrape"})
                        if results:
                            break
                if results:
                    break
        except Exception as e:
            log(f"  WP API {wp_url.split('/')[3]}: {str(e)[:40]}")
    
    if not results:
        log("  Free Methodist: No API found - needs Playwright/browser")
    
    log(f"  Free Methodist: Found {len(results)}")
    return results

# ─── Wesleyan ───────────────────────────────────────────────────────

def scrape_wesleyan():
    """Scrape Wesleyan Church directory."""
    log("  Wesleyan Church...")
    results = []
    
    urls = [
        "https://www.wesleyan.org/church-locator",
        "https://www.wesleyan.org/churches",
    ]
    
    for url in urls:
        html = fetch(url)
        if html and len(html) > 1000:
            entries = re.findall(r'class="[^"]*church[^"]*"[^>]*>([^<]+)', html)
            for e in entries:
                e = normalize_name(e)
                if e and len(e) > 10:
                    results.append({"name": e, "denomination": "Wesleyan Church", "source": "wesleyan_scrape"})
            if results:
                break
    
    log(f"  Wesleyan: Found {len(results)}")
    return results

# ─── Main ───────────────────────────────────────────────────────────

SCRAPERS = {
    "cme": ("Christian Methodist Episcopal Church", "cme_scrape", scrape_cme),
    "fmc": ("Free Methodist Church", "fmc_scrape", scrape_free_methodist),
    "wesleyan": ("Wesleyan Church", "wesleyan_scrape", scrape_wesleyan),
}

def main():
    dry_run = "--dry-run" in sys.argv
    body_filter = None
    for a in sys.argv:
        if a.startswith("--body="):
            body_filter = a.split("=")[1]
    
    targets = [body_filter] if body_filter else list(SCRAPERS.keys())
    
    log(f"Methodist Scraper ({'DRY RUN' if dry_run else 'FULL'})")
    
    all_results = {}
    for key in targets:
        if key not in SCRAPERS:
            log(f"  Unknown body: {key}")
            continue
        denom, source, scraper_fn = SCRAPERS[key]
        log(f"\nScraping {denom}...")
        results = scraper_fn()
        all_results[key] = {"denom": denom, "source": source, "results": results}
        
        if results and not dry_run:
            matched, inserted = do_import(results, denom, source)
            log(f"  Matched: {matched}, New: {inserted}")
    
    # Save CSV
    for key, data in all_results.items():
        if data["results"]:
            fname = os.path.join(OUT_DIR, f"{key}_churches.csv")
            with open(fname, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=data["results"][0].keys())
                w.writeheader()
                w.writerows(data["results"])
            log(f"  Saved {fname}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Convention & Association Church Scraper
========================================
Scrapes state convention websites for actual member church lists,
then tags those churches with their convention/association membership.

Target conventions with verified church directories:
- AL: alsbom.org/church-directory/
- SC: scbaptist.org
- KY: kybaptist.org/churches/
- WY: wyomingsbc.org/our-churches/
- VA (SBCV): sbcv.org/churches/
- DC: dcbaptist.org/churchfinder
- SC local associations: 26 association websites

Usage:
    python scripts/scrapers/scrape_convention_directories.py
    python scripts/scrapers/scrape_convention_directories.py --dry-run
"""
import csv, json, os, re, sqlite3, sys, time, urllib.request, urllib.error
from datetime import datetime
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
for _ in range(5):
    dbpath = os.path.join(PROJECT_DIR, "churches.db")
    if os.path.exists(dbpath) and os.path.getsize(dbpath) > 1024:
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DELAY = 0.5

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def fetch(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except Exception as e:
        return None

# Conventions with their own church directories (not redirects to churches.sbc.net)
CONVENTIONS = [
    {
        "name": "Alabama Baptist Convention",
        "denom": "Southern Baptist Convention",
        "url": "https://alsbom.org/church-directory/",
        "state": "AL",
        "association": "Alabama Baptist Convention",
        "patterns": [r'<a[^>]*href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel|Ministries))</a>',
                     r'<h[23][^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</h[23]>'],
    },
    {
        "name": "South Carolina Baptist Convention",
        "denom": "Southern Baptist Convention",
        "url": "https://scbaptist.org/churches",
        "state": "SC",
        "association": "South Carolina Baptist Convention",
        "patterns": [r'<a[^>]*href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</a>',
                     r'<h[23][^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</h[23]>'],
    },
    {
        "name": "Kentucky Baptist Convention",
        "denom": "Southern Baptist Convention",
        "url": "https://www.kybaptist.org/churches/",
        "state": "KY",
        "association": "Kentucky Baptist Convention",
        "patterns": [r'<a[^>]*href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</a>'],
    },
    {
        "name": "Wyoming Southern Baptist Convention",
        "denom": "Southern Baptist Convention",
        "url": "https://wyomingsbc.org/our-churches/",
        "state": "WY",
        "association": "Wyoming Southern Baptist Convention",
        "patterns": [r'<a[^>]*href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</a>'],
    },
    {
        "name": "Southern Baptist Conservatives of Virginia",
        "denom": "Southern Baptist Convention",
        "url": "https://www.sbcv.org/churches/",
        "state": "VA",
        "association": "Southern Baptist Conservatives of Virginia",
        "patterns": [r'<a[^>]*href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</a>'],
    },
    {
        "name": "District of Columbia Baptist Convention",
        "denom": "Southern Baptist Convention",
        "url": "https://www.dcbaptist.org/churchfinder",
        "state": "DC",
        "association": "District of Columbia Baptist Convention",
        "patterns": [r'<a[^>]*href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</a>'],
    },
    {
        "name": "Hawaii Pacific Baptist Convention",
        "denom": "Southern Baptist Convention",
        "url": "https://www.hpbaptist.net/pastorlesschurches/",
        "state": "HI",
        "association": "Hawaii Pacific Baptist Convention",
        "patterns": [r'<a[^>]*href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</a>'],
    },
    {
        "name": "Tennessee Baptist Mission Board",
        "denom": "Southern Baptist Convention",
        "url": "https://tnbaptist.org",
        "state": "TN",
        "association": "Tennessee Baptist Mission Board",
        "patterns": [r'<a[^>]*href="([^"]*)"[^>]*>([A-Z][A-Za-z0-9\s\.\'&#;-]{10,}?(?:Church|Baptist|Chapel))</a>'],
    },
]

def scrape_convention(conv):
    """Scrape a convention website for church listings."""
    log(f"Scraping {conv['name']}...")
    html = fetch(conv["url"])
    if not html:
        log(f"  FAILED to fetch {conv['url']}")
        return []
    
    churches = []
    for pat in conv["patterns"]:
        matches = re.findall(pat, html, re.I | re.DOTALL)
        for m in matches:
            if isinstance(m, tuple) and len(m) >= 2:
                url, name = m[0], m[1]
            elif isinstance(m, str):
                name = m
                url = ""
            else:
                continue
            name = re.sub(r'<[^>]+>', '', name).strip()
            name = re.sub(r'\s+', ' ', name).strip()
            if name and len(name) > 5 and not any(x in name.lower() for x in ['home', 'contact', 'about', 'staff', 'login', 'sign', 'search']):
                churches.append({"name": name, "url": url, "association": conv["association"], "state": conv["state"]})
    
    log(f"  Found {len(churches)} churches")
    return churches

def save_results(all_churches):
    """Save to CSV and import to DB with association tagging."""
    fp = os.path.join(OUT_DIR, "convention_member_churches.csv")
    with open(fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "url", "association", "state"])
        w.writeheader()
        for c in all_churches:
            w.writerow(c)
    log(f"Saved {len(all_churches)} to {fp}")
    return fp

def import_with_association(fp):
    """Import CSV and tag with association membership."""
    rows = list(csv.DictReader(open(fp, encoding="utf-8")))
    log(f"Importing {len(rows):,} records...")
    
    db = sqlite3.connect(DB_PATH, timeout=120)
    matched, inserted = 0, 0
    
    for row in rows:
        name = row.get("name", "").strip()
        assoc = row.get("association", "").strip()
        state = row.get("state", "").strip()
        
        if not name:
            continue
        
        # Try to match by name
        existing = db.execute(
            "SELECT id FROM churches WHERE LOWER(name)=LOWER(?) AND state=? LIMIT 1",
            (name, state)
        ).fetchone()
        
        if existing:
            # Tag with association membership
            db.execute("""UPDATE churches SET
                association = CASE 
                    WHEN association IS NULL OR association = '' THEN ?
                    ELSE association || '; ' || ?
                END,
                last_updated = datetime('now')
                WHERE id=?""",
                (assoc, assoc, existing[0])
            )
            matched += 1
    
    db.commit()
    db.close()
    log(f"Tagged {matched} churches with association membership")
    return matched

def main():
    dry_run = "--dry-run" in sys.argv
    
    all_churches = []
    for conv in CONVENTIONS:
        churches = scrape_convention(conv)
        all_churches.extend(churches)
        time.sleep(DELAY)
    
    log(f"\nTotal churches found: {len(all_churches)}")
    
    # Count by convention
    from collections import Counter
    by_conv = Counter(c["association"] for c in all_churches)
    for conv, cnt in by_conv.most_common():
        print(f"  {conv:45s} {cnt}")
    
    if not dry_run and all_churches:
        fp = save_results(all_churches)
        import_with_association(fp)
    
    log("Done!")

if __name__ == "__main__":
    main()

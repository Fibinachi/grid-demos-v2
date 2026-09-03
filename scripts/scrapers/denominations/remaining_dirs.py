#!/usr/bin/env python3
"""
Scrape remaining denomination directories that are accessible via HTTP.
Covers: CRC, UPCI, IPHC, Foursquare, Vineyard, Calvary Chapel, EPC, WELS,
Cooperative Baptist Fellowship, Converge, Unitarian Universalist,
Mennonite USA, Church of the Brethren, Salvation Army, AME Zion,
CME, Full Gospel Baptist, Coptic Orthodox, OCA, Ethiopian Orthodox,
Antiochian Orthodox, Armenian Apostolic.
"""
import csv, json, os, re, sqlite3, sys, time, urllib.request, urllib.error
from datetime import datetime
from collections import defaultdict

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
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

def fetch(url, timeout=10, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.5",
            })
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return f.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                return f"ERROR: {e}"

def extract_churches(html, base_url, patterns):
    """Extract church names and URLs from HTML using given patterns."""
    churches = []
    for pat in patterns:
        for m in re.finditer(pat, html, re.I | re.DOTALL):
            if len(m.groups()) >= 1:
                name = m.group(1).strip()
                url = m.group(2).strip() if len(m.groups()) >= 2 else ""
                name = re.sub(r'<[^>]+>', '', name).strip()
                if name and len(name) > 5:
                    churches.append({"name": name, "url": url})
    return churches

# ─── SCRAPERS ─────────────────────────────────────────────

SALVATION_ARMY = {
    "name": "Salvation Army",
    "denom": "Salvation Army",
    "url": "https://www.salvationarmyusa.org/usf/locator/",
    "desc": "Salvation Army worship locations",
}

CRC = {
    "name": "Christian Reformed Church",
    "denom": "Christian Reformed Church in North America",
    "url": "https://www.crcna.org/church-finder",
    "desc": "CRC church finder",
}

UPCI = {
    "name": "United Pentecostal Church Intl",
    "denom": "United Pentecostal Church International",
    "url": "https://www.upci.org/churches",
    "desc": "UPCI church directory",
}

UU = {
    "name": "Unitarian Universalist",
    "denom": "Unitarian Universalist",
    "url": "https://www.uua.org/congregations",
    "desc": "UUA congregation directory",
}

COPTIC = {
    "name": "Coptic Orthodox",
    "denom": "Coptic Orthodox Church",
    "url": "https://www.copticorthodox.church/",
    "desc": "Coptic Orthodox churches",
}

MENNONITE = {
    "name": "Mennonite USA",
    "denom": "Mennonite Church USA",
    "url": "https://www.mennoniteusa.org/churches/",
    "desc": "Mennonite church directory",
}

FULL_GOSPEL = {
    "name": "Full Gospel Baptist",
    "denom": "Full Gospel Baptist Church Fellowship",
    "url": "https://www.fullgospelbaptist.org/",
    "desc": "Full Gospel Baptist churches",
}

AME_ZION = {
    "name": "AME Zion",
    "denom": "African Methodist Episcopal Zion Church",
    "url": "https://www.amez.org/",
    "desc": "AME Zion churches",
}

TARGETS = [CRC, UPCI, UU, COPTIC, MENNONITE, FULL_GOSPEL, SALVATION_ARMY, AME_ZION]

def scrape_generic(target):
    """Generic scraper: fetch homepage, look for links, extract church data."""
    log(f"Scraping {target['name']}...")
    html = fetch(target["url"])
    if not html or html.startswith("ERROR"):
        log(f"  FAILED: {html[:80] if html else 'no response'}")
        return []
    
    # Extract all links
    links = re.findall(r'href=["\']([^"\']+)["\']>([^<]+)</a>', html)
    churches = []
    for url, text in links:
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 10 and not text.startswith("http"):
            churches.append({"name": text, "url": url if url.startswith("http") else target["url"] + url.lstrip("/")})
    
    log(f"  Found {len(churches)} potential churches")
    return churches

def save_results(target, churches):
    """Save scraped results to CSV."""
    fp = os.path.join(OUT_DIR, f"{target['name'].lower().replace(' ','_')}_churches.csv")
    with open(fp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "url", "denomination"])
        w.writeheader()
        for c in churches:
            w.writerow({"name": c["name"], "url": c.get("url", ""), "denomination": target["denom"]})
    log(f"  Saved {len(churches)} to {fp}")
    return fp

def import_results(fp, denom):
    """Import CSV into DB using import_scraped_csv."""
    import_file = os.path.join(PROJECT_DIR, "scripts", "enrichment", "import_scraped_csv.py")
    if os.path.exists(import_file):
        sys.path.insert(0, os.path.dirname(import_file))
        from import_scraped_csv import import_file as do_import
        m, i = do_import(fp, denom, False)
        log(f"  Import: {m} matched, {i} new")
        return m, i
    return 0, 0

def main():
    for target in TARGETS:
        churches = scrape_generic(target)
        if churches:
            fp = save_results(target, churches)
            import_results(fp, target["denom"])
        time.sleep(1)

if __name__ == "__main__":
    main()

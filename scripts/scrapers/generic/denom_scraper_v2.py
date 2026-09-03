#!/usr/bin/env python3
"""
Universal Denomination Scraper — for API-accessible directories
================================================================
Handles LCMS, PCA, RCA, COGIC, Moravian, and Catholic-Hierarchy.
Each scraper targets a specific denomination's directory API or HTML.

Usage:
    python scripts/scrapers/denom_scraper_v2.py --list          # List targets
    python scripts/scrapers/denom_scraper_v2.py lcms            # Single target
    python scripts/scrapers/denom_scraper_v2.py all             # All targets
    python scripts/scrapers/denom_scraper_v2.py --dry-run lcms  # Preview
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

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def fetch(url, timeout=15):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except Exception as e:
        return None

def fetch_json(url, timeout=15):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return json.loads(f.read().decode())
    except Exception:
        return None

from gw_filters.clean import clean_text as clean

def do_import(results, denomination, source):
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    matched = 0
    inserted = 0
    for r in results:
        name = r.get("name", "").upper().strip()
        city = r.get("city", "").upper().strip()
        state = r.get("state", "").upper().strip()
        if not name or not state:
            continue
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
            if r.get("website") and not existing_web:
                updates.append("website=?")
                uparams.append(r["website"])
            if updates:
                uparams.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", uparams)
        else:
            inserted += 1
            cur.execute("""
                INSERT OR IGNORE INTO churches 
                (name, city, state, address, zip, phone, website, denomination, source)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (name, city, state, r.get("address",""), r.get("zip",""), 
                  r.get("phone",""), r.get("website",""), denomination, source))
    db.commit()
    db.close()
    return matched, inserted

# ─── TARGETS ─────────────────────────────────────────────────────────

TARGETS = {}

# 1. LCMS — locator.lcms.org has a REST API
def scrape_lcms():
    log("  LCMS: Lutheran Church--Missouri Synod...")
    results = []
    for state in ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
                  "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
                  "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
                  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
                  "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]:
        data = fetch_json(f"https://locator.lcms.org/api/locations?state={state}&limit=1000")
        if data and isinstance(data, list):
            for item in data:
                results.append({
                    "name": clean(item.get("name","")),
                    "address": clean(f"{item.get('address','')} {item.get('address2','')}"),
                    "city": clean(item.get("city","")),
                    "state": clean(item.get("state","")),
                    "zip": clean(item.get("zip","")),
                    "phone": clean(item.get("phone","")),
                    "website": clean(item.get("website","")),
                })
        time.sleep(0.5)
    log(f"  LCMS: {len(results)} found")
    return results
TARGETS["lcms"] = ("Lutheran Church--Missouri Synod", "lcms_scrape", scrape_lcms)

# 2. PCA — pcaac.org WordPress REST API
def scrape_pca():
    log("  PCA: Presbyterian Church in America...")
    results = []
    page = 1
    while True:
        data = fetch_json(f"https://www.pcaac.org/wp-json/wp/v2/church?per_page=100&page={page}")
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        for item in data:
            title = item.get("title", {}).get("rendered", "")
            if title:
                results.append({"name": clean(title), "denomination": "Presbyterian Church in America"})
        page += 1
        time.sleep(0.3)
    log(f"  PCA: {len(results)} found")
    return results
TARGETS["pca"] = ("Presbyterian Church in America", "pca_scrape", scrape_pca)

# 3. RCA — rca.org WordPress REST API
def scrape_rca():
    log("  RCA: Reformed Church in America...")
    results = []
    data = fetch_json("https://www.rca.org/wp-json/wp/v2/church?per_page=100")
    if data and isinstance(data, list):
        for item in data:
            title = item.get("title", {}).get("rendered", "")
            if title:
                results.append({"name": clean(title), "denomination": "Reformed Church in America"})
    log(f"  RCA: {len(results)} found")
    return results
TARGETS["rca"] = ("Reformed Church in America", "rca_scrape", scrape_rca)

# 4. COGIC — cogic.org locator
def scrape_cogic():
    log("  COGIC: Church of God in Christ...")
    results = []
    html = fetch("https://www.cogic.org/locator/")
    if html:
        entries = re.findall(r'<div[^>]*class="[^"]*locator[^"]*"[^>]*>.*?<h[23][^>]*>(.*?)</h', html, re.DOTALL)
        for e in entries:
            name = clean(re.sub(r"<[^>]+>", "", e))
            if name and len(name) > 5:
                results.append({"name": name, "denomination": "Church of God in Christ"})
    log(f"  COGIC: {len(results)} found")
    return results
TARGETS["cogic"] = ("Church of God in Christ", "cogic_scrape", scrape_cogic)

# 5. Moravian — moravian.org WP API
def scrape_moravian():
    log("  Moravian Church...")
    results = []
    data = fetch_json("https://www.moravian.org/wp-json/wp/v2/church?per_page=100")
    if data and isinstance(data, list):
        for item in data:
            title = item.get("title", {}).get("rendered", "")
            if title:
                results.append({"name": clean(title), "denomination": "Moravian Church"})
    log(f"  Moravian: {len(results)} found")
    return results
TARGETS["moravian"] = ("Moravian Church", "moravian_scrape", scrape_moravian)

# 6. Catholic-Hierarchy — static HTML diocese pages
def scrape_catholic():
    log("  Catholic-Hierarchy: Roman Catholic Church...")
    results = []
    html = fetch("https://www.catholic-hierarchy.org/country/scus1.html")
    if html:
        links = re.findall(r'<a[^>]*href="([^"]*diocese[^"]*)"[^>]*>([^<]+)</a>', html)
        for href, name in links[:50]:
            name = clean(name)
            if name and "diocese" not in name.lower():
                results.append({"name": name, "denomination": "Roman Catholic Church", "website": f"https://www.catholic-hierarchy.org/{href}"})
    log(f"  Catholic-Hierarchy: {len(results)} found")
    return results
TARGETS["catholic"] = ("Roman Catholic Church", "catholic_scrape", scrape_catholic)

# ─── MAIN ────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    
    if not args or "--list" in sys.argv:
        print("Available targets:")
        for key, (denom, source, _) in sorted(TARGETS.items()):
            print(f"  {key:10s} {denom:45s} ({source})")
        return
    
    targets = TARGETS.keys() if "all" in args else [a for a in args if a in TARGETS]
    
    for key in targets:
        if key not in TARGETS:
            log(f"Unknown target: {key}")
            continue
        denom, source, fn = TARGETS[key]
        log(f"\nScraping {denom}...")
        results = fn()
        if results:
            fname = os.path.join(OUT_DIR, f"{key}_churches.csv")
            with open(fname, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=results[0].keys())
                w.writeheader()
                w.writerows(results)
            log(f"  Saved {fname}")
            
            if not dry_run:
                m, i = do_import(results, denom, source)
                log(f"  Imported: {m} matched, {i} new")

if __name__ == "__main__":
    main()

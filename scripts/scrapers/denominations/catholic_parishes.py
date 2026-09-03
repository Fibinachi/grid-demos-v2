#!/usr/bin/env python3
"""
Catholic Parish Scraper
========================
Scrapes Catholic parishes from masstimes.org (has ~17K US parishes).
Also attempts USCCB diocese directory.

Usage:
    python scripts/scrapers/scrape_catholic.py
    python scripts/scrapers/scrape_catholic.py --source masstimes
    python scripts/scrapers/scrape_catholic.py --dry-run
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

STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
          "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
          "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
          "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
          "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def fetch(url, timeout=15):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except Exception as e:
        return None

def scrape_masstimes():
    """Scrape Catholic parishes from masstimes.org state pages."""
    log("  masstimes.org state pages...")
    results = []
    
    for state in STATES:
        url = f"https://www.masstimes.org/churches/{state}"
        html = fetch(url)
        if not html:
            log(f"  {state}: failed")
            continue
        
        # Find church entries - masstimes uses structured cards
        # Try JSON-LD first
        ld_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        for ld_text in ld_matches:
            try:
                data = json.loads(ld_text)
                if isinstance(data, dict):
                    name = data.get("name", "")
                    addr = data.get("address", {})
                    if name and "catholic" in name.lower():
                        results.append({
                            "name": name,
                            "address": f"{addr.get('streetAddress','')}, {addr.get('addressLocality','')}, {addr.get('addressRegion','')} {addr.get('postalCode','')}",
                            "city": addr.get("addressLocality", ""),
                            "state": addr.get("addressRegion", ""),
                            "zip": addr.get("postalCode", ""),
                            "phone": data.get("telephone", ""),
                            "denomination": "Roman Catholic Church",
                            "source": "masstimes",
                        })
            except:
                pass
        
        # Also try finding churches in HTML cards
        cards = re.findall(r'<div[^>]*class="[^"]*(?:church|parish)[^"]*"[^>]*>', html, re.IGNORECASE)
        if cards:
            for card in cards[:5]:  # Sample
                pass
        
        time.sleep(DELAY)
        if len(results) % 50 == 0 and results:
            log(f"  {len(results)} found so far...")
    
    log(f"  Total: {len(results)}")
    return results

def scrape_gcatholic():
    """Scrape from gcatholic.org (comprehensive parish lists)."""
    log("  gcatholic.org...")
    results = []
    
    # gcatholic has pages for each diocese
    # Try the US dioceses list
    urls = [
        "https://www.gcatholic.org/dioceses/data/country-US.htm",
        "https://gcatholic.org/dioceses/country/US.htm",
    ]
    
    for url in urls:
        html = fetch(url)
        if html and len(html) > 5000:
            # Find diocese links and parishes
            diocese_links = re.findall(r'<a[^>]*href="([^"]*diocese[^"]*)"[^>]*>([^<]+)</a>', html, re.IGNORECASE)
            log(f"  Found {len(diocese_links)} diocese links")
            if diocese_links:
                results.append({"note": f"Found {len(diocese_links)} dioceses on gcatholic"})
            break
    
    return results

def do_import(results):
    """Import into DB."""
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
                uparams.append("Roman Catholic Church")
            if r.get("phone"):
                updates.append("phone=COALESCE(NULLIF(phone,''),?)")
                uparams.append(r["phone"])
            if r.get("address"):
                updates.append("address=COALESCE(NULLIF(address,''),?)")
                uparams.append(r["address"])
            if updates:
                uparams.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", uparams)
        else:
            inserted += 1
            cur.execute("""
                INSERT INTO churches (name, city, state, address, zip, phone, denomination, source)
                VALUES (?,?,?,?,?,?,?,?)
            """, (name, city, state, r.get("address", ""), r.get("zip", ""), r.get("phone", ""), "Roman Catholic Church", r.get("source", "catholic_scrape")))
    
    db.commit()
    db.close()
    return matched, inserted

def main():
    dry_run = "--dry-run" in sys.argv
    
    log(f"Catholic Scraper ({'DRY RUN' if dry_run else 'FULL'})")
    
    # Try masstimes first
    log("Source: masstimes.org")
    results = scrape_masstimes()
    
    if not results:
        log("Masstimes returned nothing, trying gcatholic...")
        results = scrape_gcatholic()
    
    if results and not dry_run:
        matched, inserted = do_import(results)
        log(f"\nResults: {len(results)} total, {matched} matched, {inserted} new")
    
    # Save CSV
    if results:
        fname = os.path.join(OUT_DIR, "catholic_parishes.csv")
        with open(fname, "w", newline="", encoding="utf-8") as f:
            if results:
                w = csv.DictWriter(f, fieldnames=results[0].keys())
                w.writeheader()
                w.writerows(results)
        log(f"Saved {fname}")

if __name__ == "__main__":
    main()

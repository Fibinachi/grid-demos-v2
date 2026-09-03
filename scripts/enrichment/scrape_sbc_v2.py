#!/usr/bin/env python3
"""
SBC Directory Scraper — v2
===========================
Scrapes all ~34,500 SBC churches from churches.sbc.net WP-JSON API.
Phase 1: Get names + links from API (346 pages, ~6 min at 1/sec)
Phase 2: Scrape individual pages for city/state/pastor/phone (parallel workers)
Phase 3: Import into DB with city+state+name matching

Usage:
    python scripts/enrichment/scrape_sbc_v2.py              # Full scrape + import
    python scripts/enrichment/scrape_sbc_v2.py --csv-only   # Phases 1+2 only, save CSV
    python scripts/enrichment/scrape_sbc_v2.py --import-csv path  # Phase 3 only
    python scripts/enrichment/scrape_sbc_v2.py --resume path     # Resume, scrape missing details
"""
import csv, json, os, re, sqlite3, sys, time, urllib.request, urllib.error
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
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "sbc_churches_v2.csv")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
API_BASE = "https://churches.sbc.net/wp-json/wp/v2/church"
STATES_PAT = r'(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)'

log_lock = Lock()
def log(msg):
    with log_lock:
        print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def getj(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=15) as f:
        raw = f.read()
        return json.loads(raw.decode("utf-8-sig"))

def scrape_page(url):
    """Scrape an individual SBC church page for city, state, pastor, phone."""
    result = {"city": "", "state": "", "pastor": "", "phone": ""}
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=15) as f:
            html = f.read().decode("utf-8", "replace")
        
        # Extract city, state (e.g. "Grantsburg, WI")
        for m in re.finditer(r'([A-Z][A-Za-z .]{2,40}),\s*' + STATES_PAT, html):
            cs = m.group(0).strip()
            if "font" not in cs.lower() and "px" not in cs.lower() and "color" not in cs.lower():
                parts = cs.split(",")
                result["city"] = parts[0].strip()
                result["state"] = parts[1].strip()
                break
        
        # Extract pastor
        for m in re.finditer(r'(?:Pastor|Reverend|Rev\.?|Dr\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})', html):
            result["pastor"] = m.group(0).strip()
            break
        
        # Extract phone (skip fake numbers)
        for m in re.finditer(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html):
            p = m.group(0)
            digits = re.sub(r'\D', '', p)
            if len(digits) == 10 and not all(d == '0' for d in digits) and not all(d == digits[0] for d in digits):
                ctx = html[max(0, m.start()-50):m.end()+50]
                if "font" not in ctx.lower() and "color" not in ctx.lower():
                    result["phone"] = p
                    break
    except Exception:
        pass
    return result

# ═══════════════════════════════════════════════════════════════
# PHASE 1: Get names + links from API
# ═══════════════════════════════════════════════════════════════

def phase1_get_links():
    """Get all church names + links from the WP-JSON API."""
    log("Phase 1: Fetching church names + links from API...")
    
    url1 = API_BASE + "?per_page=100&page=1"
    data1 = getj(url1)
    r = urllib.request.Request(url1, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=15) as f:
        total = int(f.headers.get("X-WP-Total", 0))
        pages = (total + 99) // 100
    
    log("Total: %d churches across %d pages" % (total, pages))
    
    churches = []
    for page in range(1, pages + 1):
        url = "%s?per_page=100&page=%d" % (API_BASE, page)
        try:
            data = getj(url)
            for c in data:
                title = c.get("title", {}).get("rendered", "").strip()
                link = c.get("link", "").strip()
                if title:
                    churches.append({"name": title, "website": link})
            if page % 50 == 0:
                log("  Page %d/%d: %d churches" % (page, pages, len(churches)))
        except Exception as e:
            log("  Page %d error: %s, retrying..." % (page, str(e)[:60]))
            time.sleep(5)
            try:
                data = getj(url)
                for c in data:
                    title = c.get("title", {}).get("rendered", "").strip()
                    link = c.get("link", "").strip()
                    if title:
                        churches.append({"name": title, "website": link})
            except:
                log("  Page %d: retry failed, continuing" % page)
        time.sleep(1.0)
    
    log("Phase 1 complete: %d churches" % len(churches))
    return churches

# ═══════════════════════════════════════════════════════════════
# PHASE 2: Scrape individual pages for details
# ═══════════════════════════════════════════════════════════════

def phase2_scrape_details(churches, workers=8):
    """Scrape each church's page for city/state/pastor/phone."""
    total = len(churches)
    to_scrape = [(i, c) for i, c in enumerate(churches) if c.get("website")]
    log("Phase 2: Scraping %d pages (%d workers)..." % (len(to_scrape), workers))
    
    completed = [0]
    completed_lock = Lock()
    last_log = [time.time()]
    
    def scrape_one(item):
        i, c = item
        details = scrape_page(c["website"])
        with completed_lock:
            completed[0] += 1
            done = completed[0]
            now = time.time()
            if done % 300 == 0 or done == len(to_scrape):
                elapsed = now - last_log[0]
                rate = done / (now - time.time() + total)
                remaining = (len(to_scrape) - done) / max(rate, 0.1)
                log("  Scraped %d/%d (%.1f%%) ~%.0fs remaining" % (
                    done, len(to_scrape), 100*done/len(to_scrape), remaining))
                last_log[0] = now
        return i, details
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(scrape_one, item) for item in to_scrape]
        for future in as_completed(futures):
            i, details = future.result()
            churches[i]["city"] = details["city"]
            churches[i]["state"] = details["state"]
            churches[i]["pastor"] = details["pastor"]
            churches[i]["phone"] = details["phone"]
    
    with_city = sum(1 for c in churches if c.get("city"))
    with_pastor = sum(1 for c in churches if c.get("pastor"))
    with_phone = sum(1 for c in churches if c.get("phone"))
    log("Phase 2: city=%d pastor=%d phone=%d" % (with_city, with_pastor, with_phone))

def save_csv(churches):
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "website", "city", "state", "pastor", "phone"])
        w.writeheader()
        w.writerows(churches)
    log("Saved: %s" % OUT_CSV)

def load_csv(csv_path):
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ═══════════════════════════════════════════════════════════════
# PHASE 3: Import into DB
# ═══════════════════════════════════════════════════════════════

def phase3_import(churches):
    """Import SBC churches into DB with city+state+name matching."""
    total = len(churches)
    log("Phase 3: Importing %d SBC churches..." % total)
    
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    matched = 0
    multi_match = 0
    inserted = 0
    skipped = 0
    websites_added = 0
    
    for row in churches:
        name = (row.get("name") or "").strip().upper()
        website = (row.get("website") or "").strip()
        city = (row.get("city") or "").strip()
        state = (row.get("state") or "").strip()
        pastor = (row.get("pastor") or "").strip()
        phone = (row.get("phone") or "").strip()
        
        if not name:
            skipped += 1
            continue
        
        # Match by name + state if we have both
        if state:
            cur.execute("SELECT id, website, denomination, city FROM churches WHERE name=? AND state=? LIMIT 2", (name, state))
        else:
            cur.execute("SELECT id, website, denomination, city FROM churches WHERE name=? LIMIT 2", (name,))
        
        results = cur.fetchall()
        
        if len(results) == 1:
            cid, existing_web, existing_denom, existing_city = results[0]
            matched += 1
            
            updates = []
            params = []
            if website and (not existing_web):
                updates.append("website=?")
                params.append(website)
                updates.append("website_scrape_status='found'")
                updates.append("website_source='sbc_directory'")
                updates.append("website_confidence=0.85")
                websites_added += 1
            if phone:
                digits = re.sub(r'\D', '', phone)
                if len(digits) >= 10:
                    updates.append("phone=COALESCE(phone,?)")
                    params.append(digits)
            if not existing_denom or existing_denom == "":
                updates.append("denomination='Southern Baptist Convention'")
                updates.append("classification_source=COALESCE(NULLIF(classification_source,''),'sbc_directory')")
            if updates:
                params.append(cid)
                cur.execute("UPDATE churches SET %s WHERE id=?" % ", ".join(updates), params)
            
            if pastor:
                pn = re.sub(r'^(Pastor|Reverend|Rev\.?|Dr\.?)\s+', '', pastor, flags=re.I).strip()
                if pn:
                    cur.execute("INSERT OR IGNORE INTO church_staff (church_id, name, role, source, confidence, last_updated) VALUES (?, ?, 'Pastor', 'sbc_directory', 85, datetime('now'))", (cid, pn))
        
        elif len(results) > 1:
            multi_match += 1
            # Try city match within state
            if city and state:
                cur.execute("SELECT id, website FROM churches WHERE name=? AND state=? AND city LIKE ? LIMIT 1",
                           (name, state, "%%%s%%" % city[:15]))
                result = cur.fetchone()
                if result:
                    cid, existing_web = result
                    if website and (not existing_web):
                        cur.execute("UPDATE churches SET website=?, website_source='sbc_directory', website_confidence=0.85, denomination='Southern Baptist Convention' WHERE id=?", (website, cid))
                        websites_added += 1
                    if pastor:
                        pn = re.sub(r'^(Pastor|Reverend|Rev\.?|Dr\.?)\s+', '', pastor, flags=re.I).strip()
                        if pn:
                            cur.execute("INSERT OR IGNORE INTO church_staff (church_id, name, role, source, confidence) VALUES (?, ?, 'Pastor', 'sbc_directory', 85)", (cid, pn))
                    matched += 1
                else:
                    cid = results[0][0]
                    existing_web = results[0][1]
                    if website and (not existing_web):
                        cur.execute("UPDATE churches SET website=?, website_source='sbc_directory', website_confidence=0.85 WHERE id=?", (website, cid))
                        websites_added += 1
        else:
            inserted += 1
            phone_clean = re.sub(r'\D', '', phone) if phone else ""
            cur.execute("INSERT INTO churches (name, website, city, state, phone, denomination, source, website_source, website_scrape_status, website_confidence, classification_source, last_updated) VALUES (?, ?, ?, ?, ?, 'Southern Baptist Convention', 'sbc_directory', 'sbc_directory', 'found', 0.85, 'sbc_directory', datetime('now'))", (name, website, city, state, phone_clean))
            if pastor:
                pn = re.sub(r'^(Pastor|Reverend|Rev\.?|Dr\.?)\s+', '', pastor, flags=re.I).strip()
                if pn:
                    cur.execute("INSERT INTO church_staff (church_id, name, role, source, confidence) VALUES (?, ?, 'Pastor', 'sbc_directory', 85)", (cur.lastrowid, pn))
    
    db.commit()
    db.close()
    
    log("")
    log("=" * 55)
    log("SBC IMPORT RESULTS")
    log("=" * 55)
    log("  Total SBC records: %d" % total)
    log("  Matched (existing): %d" % matched)
    log("  Multi-match resolved: %d" % multi_match)
    log("  New churches inserted: %d" % inserted)
    log("  Websites added: %d" % websites_added)
    log("  Skipped: %d" % skipped)
    
    db2 = sqlite3.connect(DB_PATH)
    c2 = db2.cursor()
    c2.execute("SELECT COUNT(*) FROM churches WHERE denomination='Southern Baptist Convention'")
    sbc_total = c2.fetchone()[0]
    c2.execute("SELECT COUNT(*) FROM churches WHERE website_source='sbc_directory'")
    sbc_web = c2.fetchone()[0]
    c2.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''")
    total_web = c2.fetchone()[0]
    db2.close()
    log("")
    log("  DB now has %d SBC churches" % sbc_total)
    log("  %d with websites from SBC directory" % sbc_web)
    log("  Total churches with websites: %d" % total_web)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-only", action="store_true", help="Phases 1+2 only")
    parser.add_argument("--import-csv", help="Phase 3 only from CSV")
    parser.add_argument("--resume", help="Resume from CSV, scrape missing details")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers")
    parser.add_argument("--limit", type=int, default=0, help="Limit for testing")
    args = parser.parse_args()
    
    t0 = time.time()
    
    if args.import_csv:
        churches = load_csv(args.import_csv)
        log("Loaded %d churches from %s" % (len(churches), args.import_csv))
        phase3_import(churches)
    elif args.resume:
        churches = load_csv(args.resume)
        need = [c for c in churches if not c.get("city") and c.get("website")]
        log("Loaded %d, %d need city/state" % (len(churches), len(need)))
        if need:
            phase2_scrape_details(churches, args.workers)
            save_csv(churches)
        phase3_import(churches)
    elif args.csv_only:
        churches = phase1_get_links()
        if args.limit:
            churches = churches[:args.limit]
        phase2_scrape_details(churches, args.workers)
        save_csv(churches)
    else:
        churches = phase1_get_links()
        if args.limit:
            churches = churches[:args.limit]
        phase2_scrape_details(churches, args.workers)
        save_csv(churches)
        phase3_import(churches)
    
    elapsed = time.time() - t0
    log("Total time: %dm %ds" % (elapsed // 60, elapsed % 60))

if __name__ == "__main__":
    main()

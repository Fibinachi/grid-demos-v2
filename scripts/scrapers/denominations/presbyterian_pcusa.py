#!/usr/bin/env python3
"""
PCUSA Congregation Scraper (v2 - fixed name matching)
======================================================
The PCUSA API returns names as "Church Name, City, ST" — we strip the
city/state suffix and use UPPER() for case-insensitive matching.
Also tries prefix matching for "FIRST PRESBYTERIAN CHURCH" variants.

Usage:
    python scripts/scrapers/scrape_pcusa.py              # Full scrape
    python scripts/scrapers/scrape_pcusa.py --dry-run    # Show first 10 only
"""
import csv, json, os, re, sqlite3, sys, urllib.request
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
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "pcusa_congregations.csv")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
API_URL = "https://www.pcusa.org/api/congregations"

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def clean_name(raw_name):
    """Strip ', City, ST' suffix from PCUSA name format."""
    return re.sub(r",\s*[^,]+,\s*[A-Z]{2}\s*$", "", raw_name).strip()

def fetch_all():
    log(f"Fetching PCUSA congregations from {API_URL}...")
    r = urllib.request.Request(API_URL, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as f:
        data = json.loads(f.read().decode("utf-8"))
    log(f"  Got {len(data)} congregations")
    return data

def import_to_db(congregations, dry_run=False):
    if dry_run:
        log(f"  DRY RUN - first 10 cleaned names:")
        for c in congregations[:10]:
            raw = c.get("name","")
            cleaned = clean_name(raw)
            print(f"    {raw:55s} -> {cleaned}")
        return 0, 0
    
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    matched = 0
    inserted = 0
    
    for c in congregations:
        raw_name = (c.get("name") or "").strip()
        name = clean_name(raw_name)
        name_upper = name.upper()
        city = (c.get("city") or "").strip().upper()
        state = (c.get("state") or "").strip().upper()
        address = (c.get("address1") or "").strip()
        zip_code = (c.get("zip") or "").strip()
        website = (c.get("website") or "").strip()
        phone = re.sub(r"\D", "", (c.get("phone") or ""))[-10:] if c.get("phone") else ""
        presbytery = (c.get("synod_presbytery") or "").strip()
        
        if not name or not state:
            continue
        
        row = None
        
        # Strategy 1: UPPER(name) + state
        cur.execute("SELECT id, denomination, city, website FROM churches WHERE UPPER(name)=? AND state=? LIMIT 1", (name_upper, state))
        row = cur.fetchone()
        
        # Strategy 2: UPPER(name) + city + state
        if not row and city:
            cur.execute("SELECT id, denomination, city, website FROM churches WHERE UPPER(name)=? AND city=? AND state=? LIMIT 1", (name_upper, city, state))
            row = cur.fetchone()
        
        # Strategy 3: First 20 chars + state (catches "FIRST PRESBYTERIAN CHURCH OF X" vs "First Presbyterian Church")
        if not row:
            prefix = name_upper[:20]
            cur.execute("""
                SELECT id, denomination, city, website FROM churches 
                WHERE SUBSTR(UPPER(name),1,?)=? AND state=? LIMIT 1
            """, (len(prefix), prefix, state))
            row = cur.fetchone()
        
        if row:
            matched += 1
            cid, existing_denom, existing_city, existing_web = row
            updates = []
            params = []
            
            if not existing_denom:
                updates.append("denomination=?")
                params.append("Presbyterian Church (U.S.A.)")
            if website and not existing_web:
                updates.append("website=?")
                params.append(website)
            if phone:
                updates.append("phone=COALESCE(NULLIF(phone,''),?)")
                params.append(phone)
            if presbytery:
                updates.append("presbytery=COALESCE(NULLIF(presbytery,''),?)")
                params.append(presbytery)
            if address:
                updates.append("address=COALESCE(NULLIF(address,''),?)")
                params.append(address)
            
            if updates:
                params.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", params)
        else:
            inserted += 1
            cur.execute("""
                INSERT INTO churches 
                (name, website, address, city, state, zip, phone, 
                 denomination, source, presbytery)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (name_upper, website or "", address, city, state, zip_code, phone,
                  "Presbyterian Church (U.S.A.)", "pcusa_api", presbytery))
        
        if (matched + inserted) % 1000 == 0:
            log(f"    Processed {matched + inserted}/{len(congregations)}...")
    
    db.commit()
    db.close()
    return matched, inserted

def main():
    dry_run = "--dry-run" in sys.argv
    log(f"PCUSA Scraper v2 ({'DRY RUN' if dry_run else 'FULL'})")
    congregations = fetch_all()
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        if congregations:
            w = csv.DictWriter(f, fieldnames=congregations[0].keys())
            w.writeheader()
            w.writerows(congregations)
    log(f"  Saved raw data to {OUT_CSV}")
    
    matched, inserted = import_to_db(congregations, dry_run)
    log(f"\n=== PCUSA IMPORT RESULTS ===")
    log(f"  Total congregations: {len(congregations)}")
    log(f"  Matched existing: {matched}")
    log(f"  New churches inserted: {inserted}")

if __name__ == "__main__":
    main()

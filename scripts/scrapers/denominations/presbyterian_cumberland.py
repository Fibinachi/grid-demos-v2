#!/usr/bin/env python3
"""
Cumberland Presbyterian Church Scraper
========================================
Scrapes cpcmc.org/find-a-church for all ~668 Cumberland Presbyterian congregations.

Uses Playwright to load the map page, set "Show entries" to "All", and
extract the full datatable with names, addresses, cities, states, ZIPs.

The Cumberland Presbyterian Church has a hierarchical structure:
- General Assembly (national)
- 4 Synods (regional): East, West, Central, Hispanic
- ~32 Presbyteries (local districts)
- ~668 Congregations

Usage:
    python scripts/scrapers/scrape_cumberland.py              # Full scrape + import
    python scripts/scrapers/scrape_cumberland.py --dry-run    # Preview only
    python scripts/scrapers/scrape_cumberland.py --limit 10   # First 10 only
"""
import csv, json, os, sqlite3, sys, time
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        for candidate in [
            r"E:\grid",
            os.path.expanduser("~/grantwizard"),
            os.getcwd(),
        ]:
            if os.path.exists(os.path.join(candidate, "churches.db")):
                PROJECT_DIR = candidate
                break
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "cumberland_churches.csv")

DENOM = "Cumberland Presbyterian Church"
SOURCE = "cumberland_scrape"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def scrape_page(url, limit=None):
    """Use Playwright to load the page and extract the datatable."""
    from playwright.sync_api import sync_playwright
    
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)
        
        # Clear the WPGMZA table search box to show all rows
        search_box = page.locator('input[aria-controls="wpgmza_table_7"]')
        if search_box.count() == 0:
            search_box = page.get_by_role("searchbox", name="Search:")
        if search_box.count() > 0:
            search_box.fill("")
            page.wait_for_timeout(1000)
        
        # Set "Show entries" to "All"
        select = page.locator('select[name$="_length"]')
        if select.count() > 0:
            select.select_option("All")
            page.wait_for_timeout(3000)
        
        # Extract table data
        rows = page.locator("table tbody tr").all()
        log(f"  Found {len(rows)} rows in table")
        
        for i, row in enumerate(rows):
            if limit and i >= limit:
                break
            cells = row.locator("td").all()
            if len(cells) >= 10:
                name = cells[0].inner_text().strip()
                city = cells[2].inner_text().strip() if len(cells) > 2 else ""
                street = cells[3].inner_text().strip() if len(cells) > 3 else ""
                state = cells[5].inner_text().strip() if len(cells) > 5 else ""
                postal = cells[6].inner_text().strip() if len(cells) > 6 else ""
                country = cells[7].inner_text().strip() if len(cells) > 7 else ""
                slug = cells[9].inner_text().strip() if len(cells) > 9 else ""
                
                results.append({
                    "name": name,
                    "address": street,
                    "city": city,
                    "state": state,
                    "zip": postal,
                    "country": country,
                    "slug": slug,
                })
        
        browser.close()
    
    return results


def do_import(results):
    """Import Cumberland Presbyterian church data into the database."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    matched = 0
    inserted = 0
    for r in results:
        name = r.get("name", "").upper().strip()
        city = r.get("city", "").upper().strip()
        state = r.get("state", "").upper().strip()
        if not name or not state:
            log(f"  SKIP (no name/state): {r.get('name','?')}")
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
                uparams.append(DENOM)
            if updates:
                uparams.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", uparams)
        else:
            inserted += 1
            cur.execute("""
                INSERT OR IGNORE INTO churches 
                (name, city, state, address, zip, denomination, source)
                VALUES (?,?,?,?,?,?,?)
            """, (
                name, city, state,
                r.get("address", ""),
                r.get("zip", ""),
                DENOM, SOURCE
            ))
    
    db.commit()
    db.close()
    return matched, inserted


def main():
    dry_run = "--dry-run" in sys.argv
    limit = None
    for a in sys.argv[1:]:
        if a.startswith("--limit="):
            limit = int(a.split("=")[1])
    
    url = "https://cpcmc.org/find-a-church/"
    log(f"Scraping Cumberland Presbyterian Church directory...")
    results = scrape_page(url, limit=limit)
    
    if not results:
        log("ERROR: No results scraped!")
        return
    
    # Save CSV
    fields = ["name", "address", "city", "state", "zip", "country", "slug"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    log(f"Saved {len(results)} records to {OUT_CSV}")
    
    # Summary
    with_addr = sum(1 for r in results if r.get("address"))
    with_city = sum(1 for r in results if r.get("city"))
    with_state = sum(1 for r in results if r.get("state"))
    log(f"\nResults summary:")
    log(f"  Total:        {len(results)}")
    log(f"  With address:  {with_addr}")
    log(f"  With city:     {with_city}")
    log(f"  With state:    {with_state}")
    
    log(f"\nSample:")
    for r in results[:5]:
        log(f"  {r.get('name','?'):50s} | {r.get('city','?'):20s} | {r.get('state','?'):2s} | {r.get('address',''):30s}")
    
    # Import if not dry run
    if not dry_run and results:
        matched, inserted = do_import(results)
        log(f"\nImport: {matched} matched, {inserted} new records")
    
    return results


if __name__ == "__main__":
    main()

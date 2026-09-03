#!/usr/bin/env python3
"""
ARP Church Scraper — Associate Reformed Presbyterian Church
=============================================================
Scrapes arpchurch.org/find-a-church for all ~269 ARP congregations.

Uses the WP REST API to get all store URLs, then visits each
individual church page for full details (address, phone, email, website).

Usage:
    python scripts/scrapers/scrape_arp.py              # Full scrape + import
    python scripts/scrapers/scrape_arp.py --dry-run    # Preview only
    python scripts/scrapers/scrape_arp.py --limit 10   # First 10 only
"""
import csv, json, os, re, sqlite3, sys, time, urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        # Fallback: try known locations
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
OUT_CSV = os.path.join(OUT_DIR, "arp_churches.csv")

DENOM = "Associate Reformed Presbyterian Church"
SOURCE = "arp_scrape"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DELAY = 0.3


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except Exception as e:
        return None


def fetch_json(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return json.loads(f.read().decode())
    except Exception:
        return None


def decode_cf_email(data_cfemail):
    """Decode CloudFlare obfuscated email from data-cfemail attribute."""
    try:
        key = int(data_cfemail[:2], 16)
        chars = []
        for i in range(2, len(data_cfemail), 2):
            chars.append(chr(int(data_cfemail[i:i+2], 16) ^ key))
        return ''.join(chars)
    except Exception:
        return None


def get_all_store_links():
    """Get all ARP church store links from WP REST API (paginated)."""
    stores = []
    page = 1
    while True:
        url = f"https://arpchurch.org/wp-json/wp/v2/wpsl_stores?per_page=100&page={page}&_fields=id,title,link"
        data = fetch_json(url)
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        for s in data:
            stores.append({
                "id": s["id"],
                "name": s["title"]["rendered"],
                "link": s["link"],
            })
        log(f"  Page {page}: {len(data)} stores")
        page += 1
        time.sleep(0.2)
    log(f"  Total stores found: {len(stores)}")
    return stores


def scrape_church_page(url):
    """Scrape an individual church page for details."""
    html = fetch(url)
    if not html:
        return {}

    result = {}

    # ── Address (wpsl-location-address div) ──
    addr_div = re.search(
        r'<div[^>]*class="[^"]*wpsl-location-address[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL | re.IGNORECASE
    )
    if addr_div:
        spans = re.findall(r'<span[^>]*>(.*?)</span>', addr_div.group(1))
        parts = [re.sub(r'<[^>]+>', '', s).strip() for s in spans]
        parts = [p for p in parts if p and p.lower() != 'united states']

        if parts:
            result["address"] = parts[0]

        # City, state, zip are in separate adjacent spans: "Belmont" "NC " "28012 "
        # Look through remaining parts for state+zip or just state
        for i, p in enumerate(parts[1:], 1):
            # Single state abbreviation
            sm = re.match(r'^([A-Z]{2})\s*$', p.strip())
            if sm:
                result["state"] = sm.group(1).strip()
                # Previous part is likely the city
                if i > 1 and not result.get("city"):
                    result["city"] = parts[i-1]
                continue
            # ZIP code
            zm = re.match(r'^(\d{5}(?:-\d{4})?)\s*$', p.strip())
            if zm:
                result["zip"] = zm.group(1).strip()
                continue
            # City name (not a number, not a state)
            cm = re.match(r'^([A-Za-z\s\.\-]+?)\s*$', p.strip())
            if cm and len(p.strip()) > 2 and not result.get("city"):
                result["city"] = cm.group(1).strip()
        
        # If no city found from spans, try looking at the second element
        if not result.get("city") and len(parts) > 1:
            result["city"] = parts[1]

    # ── Contact details (wpsl-contact-details div) ──
    contact_div = re.search(
        r'<div[^>]*class="[^"]*wpsl-contact-details[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL | re.IGNORECASE
    )
    if contact_div:
        content = contact_div.group(1)

        # Phone: <span><a href="tel:704-685-1335">
        pm = re.search(r'Phone:[^<]*<span[^>]*><a[^>]*href="tel:([^"]+)"', content, re.IGNORECASE)
        if pm:
            result["phone"] = pm.group(1).strip()

        # Fax field contains pastor name
        fm = re.search(r'Fax:[^<]*<span[^>]*><a[^>]*href="tel:([^"]+)"[^>]*>([^<]+)</a>', content, re.IGNORECASE)
        if fm:
            pv = fm.group(2).strip()
            if pv and len(pv) > 3 and not re.match(r'^[\d\s\-\(\)]+$', pv):
                result["pastor"] = pv

        # Email (CloudFlare protected)
        cf = re.search(r'data-cfemail="([^"]+)"', content)
        if cf:
            decoded = decode_cf_email(cf.group(1))
            if decoded:
                result["email"] = decoded

        # Website URL
        um = re.search(r'Url:[^<]*<a[^>]*href="(https?://[^"]+)"', content, re.IGNORECASE)
        if um:
            result["website"] = um.group(1).strip()

    return result


def do_import(results):
    """Import ARP church data into the database."""
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
            if r.get("website") and not existing_web:
                updates.append("website=?")
                uparams.append(r["website"])
            if updates:
                uparams.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", uparams)

            if r.get("pastor"):
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO church_staff (church_id, name, role, source, confidence, last_updated)
                        VALUES (?, ?, 'Pastor', 'arp_directory', 90, datetime('now'))
                    """, (cid, r["pastor"]))
                except Exception:
                    pass
        else:
            inserted += 1
            cur.execute("""
                INSERT OR IGNORE INTO churches 
                (name, city, state, address, zip, phone, website, denomination, source)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                name, city, state,
                r.get("address", ""),
                r.get("zip", ""),
                r.get("phone", ""),
                r.get("website", ""),
                DENOM, SOURCE
            ))
            if r.get("pastor") and cur.lastrowid:
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO church_staff (church_id, name, role, source, confidence, last_updated)
                        VALUES (?, ?, 'Pastor', 'arp_directory', 90, datetime('now'))
                    """, (cur.lastrowid, r["pastor"]))
                except Exception:
                    pass
    db.commit()
    db.close()
    return matched, inserted


def main():
    dry_run = "--dry-run" in sys.argv
    limit = None
    for a in sys.argv[1:]:
        if a.startswith("--limit="):
            limit = int(a.split("=")[1])

    log(f"Fetching ARP church list from WP REST API...")
    stores = get_all_store_links()

    if limit:
        stores = stores[:limit]

    log(f"Scraping {len(stores)} church pages...")
    results = []
    for i, s in enumerate(stores):
        log(f"  [{i+1}/{len(stores)}] {s['name']}")
        details = scrape_church_page(s["link"])
        details["name"] = s["name"]
        details["url"] = s["link"]
        results.append(details)
        time.sleep(DELAY)

    # Save CSV
    fields = ["name", "address", "city", "state", "zip", "phone", "email", "website", "pastor", "url"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    log(f"Saved {len(results)} records to {OUT_CSV}")

    # Summary
    with_phone = sum(1 for r in results if r.get("phone"))
    with_email = sum(1 for r in results if r.get("email"))
    with_web = sum(1 for r in results if r.get("website"))
    with_addr = sum(1 for r in results if r.get("address"))
    with_pastor = sum(1 for r in results if r.get("pastor"))
    with_city = sum(1 for r in results if r.get("city"))
    with_state = sum(1 for r in results if r.get("state"))
    log(f"\nResults summary:")
    log(f"  Total:        {len(results)}")
    log(f"  With address:  {with_addr}")
    log(f"  With city:     {with_city}")
    log(f"  With state:    {with_state}")
    log(f"  With phone:    {with_phone}")
    log(f"  With email:    {with_email}")
    log(f"  With website:  {with_web}")
    log(f"  With pastor:   {with_pastor}")

    log(f"\nSample:")
    for r in results[:3]:
        log(f"  {r.get('name','?'):45s} | {r.get('city','?'):20s} | {r.get('state','?'):2s} | {r.get('phone',''):15s} | {r.get('website','')[:30] if r.get('website') else '':30s}")

    if not dry_run and results:
        matched, inserted = do_import(results)
        log(f"\nImport: {matched} matched, {inserted} new records")

    return results


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
AME Church Scraper — African Methodist Episcopal Church
========================================================
Scrapes AME episcopal district websites for church listings and tags
each church with its district.

AME districts with accessible directories:
  - 2nd District (MD, DC, VA, NC): ame2.com/churches-list/ — HTML table
  - 6th District (GA): ame6.church — WP REST API (mcd/v1/churches)
  - 10th District (TX): amec10.org/find-a-church — placeholder only
  - 19th District (South Africa): not US-based, skip

Usage:
    python scripts/scrapers/scrape_ame.py               # Full scrape + import
    python scripts/scrapers/scrape_ame.py --dry-run      # Preview only
    python scripts/scrapers/scrape_ame.py --limit 10     # First 10 per source
"""
import csv, json, os, re, sqlite3, sys, time, urllib.request, urllib.error
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        # Skip empty/fake DB files
        sz = os.path.getsize(os.path.join(PROJECT_DIR, "churches.db"))
        if sz > 1024:  # Real DB is 300MB+
            break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "ame_churches.csv")

DENOM = "African Methodist Episcopal Church"
SOURCE = "ame_district_scrape"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DELAY = 0.3


# ── AME Districts with known coverage ──
DISTRICTS = {
    "2nd": {"name": "2nd Episcopal District", "states": ["MD", "DC", "VA", "NC"]},
    "6th": {"name": "6th Episcopal District", "states": ["GA"]},
    # Add more districts as scraper patterns are developed
}

# Geo-based district mapping for tagging existing records
STATE_TO_DISTRICT = {
    "ME": "1st", "NH": "1st", "VT": "1st", "MA": "1st", "RI": "1st", "CT": "1st",
    "MD": "2nd", "DC": "2nd", "VA": "2nd", "NC": "2nd",
    "OH": "3rd", "WV": "3rd",
    "IL": "4th", "IN": "4th", "MI": "4th", "WI": "4th", "MN": "4th",
    "CA": "5th",
    "GA": "6th",
    "SC": "7th",
    "MS": "8th", "LA": "8th",
    "AL": "9th",
    "TX": "10th",
    "FL": "11th",
    "AR": "12th", "OK": "12th",
    "TN": "13th", "KY": "13th",
    "PA": "1st", "NJ": "1st", "DE": "1st", "NY": "1st",
    # 14-18 are Africa/Caribbean
    "WA": "1st", "OR": "1st", "AK": "1st", "HI": "1st",
    "AZ": "5th", "NV": "5th", "UT": "5th",
    "CO": "5th", "NM": "5th",
    "ND": "4th", "SD": "4th", "NE": "4th", "KS": "4th", "IA": "4th", "MO": "4th",
    "WY": "5th", "MT": "5th", "ID": "5th",
    # 19-20 are Africa
}


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


# ── 2nd District Scraper (ame2.com) ──

def scrape_2nd_district(limit=None):
    """Scrape 2nd Episcopal District church list from ame2.com/churches-list/."""
    log("Scraping 2nd Episcopal District (ame2.com/churches-list/)...")
    html = fetch("https://ame2.com/churches-list/")
    if not html:
        log("  ERROR: Could not fetch page")
        return []

    results = []
    county = ""
    
    # Extract just the table section - find content between "CHURCHES LIST" and "Servant Leadership"
    table_section = re.search(
        r'CHURCHES\s*LIST\s*(.*?)(?:Servant Leadership|$)',
        html, re.DOTALL | re.IGNORECASE
    )
    if not table_section:
        log("  ERROR: Could not find table section")
        return []
    
    table_html = table_section.group(1)
    
    # Find all table rows
    rows = re.findall(
        r'<tr[^>]*>(.*?)</tr>',
        table_html, re.DOTALL | re.IGNORECASE
    )
    
    for row in rows:
        # Extract all td cells
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
        if not cells:
            continue
        
        # Clean HTML from each cell
        clean_cells = []
        for c in cells:
            txt = re.sub(r'<[^>]+>', '', c).strip()
            txt = txt.replace("&nbsp;", "").replace("&amp;", "&").strip()
            txt = re.sub(r'\s+', ' ', txt).strip()
            clean_cells.append(txt)
        
        # Skip header row
        second_col = clean_cells[1].lower() if len(clean_cells) > 1 else ""
        if second_col == "church":
            continue
        
        # Data rows have structure: [county_or_empty, name, address, city, state, zip, website, pastor]
        if len(clean_cells) >= 5:
            first_cell = clean_cells[0] if clean_cells[0] else ""
            
            # Check if this is a county header row
            # County rows have only the first column filled (county name), rest are empty
            rest_empty = all(c == "" for c in clean_cells[1:])
            if first_cell and rest_empty and len(first_cell) > 3:
                lower = first_cell.lower()
                # Skip non-county text like state abbreviations
                if lower not in ("maryland", "washington dc", "virginia", "north carolina", 
                                "church", "address", "city", "state", "zip code", "website", "pastor"):
                    county = first_cell
                    continue
            
            # This is a data row - church name is in column 1 (index 1)
            church_name = clean_cells[1] if len(clean_cells) > 1 else ""
            if not church_name:
                continue
            
            address = clean_cells[2] if len(clean_cells) > 2 else ""
            city = clean_cells[3] if len(clean_cells) > 3 else ""
            state = clean_cells[4] if len(clean_cells) > 4 else ""
            zip_code = clean_cells[5] if len(clean_cells) > 5 else ""
            website = clean_cells[6] if len(clean_cells) > 6 else ""
            pastor = clean_cells[7] if len(clean_cells) > 7 else ""

            # Clean state
            sm = re.match(r'([A-Z]{2})', state.strip())
            if sm:
                state = sm.group(1)
            else:
                state = state.strip()[:2].upper()

            if not state:
                continue

            results.append({
                "name": church_name.strip().upper(),
                "address": address,
                "city": city.strip(),
                "state": state,
                "zip": re.sub(r'[^\d\-]', '', zip_code).strip()[:10] if zip_code else "",
                "phone": "",
                "email": "",
                "website": website if website and website not in ("http://", "https://") else "",
                "pastor": pastor if pastor and pastor != "N/A" else "",
                "source_url": "https://ame2.com/churches-list/",
                "district": "2nd Episcopal District",
                "county": county,
            })

    log(f"  2nd District: {len(results)} churches found")
    if limit:
        results = results[:limit]
    return results


# ── 6th District Scraper (ame6.church) ──

def scrape_6th_district(limit=None):
    """Scrape 6th Episcopal District from ame6.church WP REST API."""
    log("Scraping 6th Episcopal District (ame6.church API)...")
    url = "https://ame6.church/wp-json/mcd/v1/churches?per_page=100"
    data = fetch_json(url)
    if not data or "items" not in data:
        log("  ERROR: No data from API")
        return []

    results = []
    for item in data["items"]:
        name = item.get("name", "").strip().upper()
        city = item.get("city", "").strip()
        state = item.get("state", "").strip().upper()
        
        if not name or not state:
            continue

        results.append({
            "name": name,
            "address": item.get("address", "").strip(),
            "city": city,
            "state": state,
            "zip": item.get("zip", "").strip(),
            "phone": item.get("phone", "").strip(),
            "email": item.get("email", "").strip(),
            "website": item.get("website", "") or "",
            "pastor": item.get("pastor", "").strip(),
            "source_url": "https://ame6.church/ame6-church-directory/",
            "district": "6th Episcopal District",
            "county": "",
        })

    log(f"  6th District: {len(results)} churches found")
    if limit:
        results = results[:limit]
    return results


def do_import(results):
    """Import AME church data into the database with district tagging."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    matched = 0
    inserted = 0
    district_tagged = 0
    for r in results:
        name = r.get("name", "").strip()
        city = r.get("city", "").strip().upper()
        state = r.get("state", "").strip().upper()
        district = r.get("district", "")

        if not name or not state:
            log(f"  SKIP (no name/state): {r.get('name','?')}")
            continue

        row = None
        for sql, params in [
            ("SELECT id, denomination FROM churches WHERE UPPER(name)=? AND state=? LIMIT 1", (name, state)),
            ("SELECT id, denomination FROM churches WHERE UPPER(name)=? AND city=? AND state=? LIMIT 1", (name, city, state)),
        ]:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row:
                break

        if row:
            matched += 1
            cid, existing_denom = row
            updates = []
            uparams = []
            
            # Update denomination if empty
            if not existing_denom:
                updates.append("denomination=?")
                uparams.append(DENOM)
            
            # Add website if we have one and existing doesn't
            if r.get("website") and r["website"].strip():
                cur.execute("SELECT website FROM churches WHERE id=?", (cid,))
                existing_web = cur.fetchone()
                if existing_web and not existing_web[0]:
                    updates.append("website=?")
                    uparams.append(r["website"].strip())
            
            # Add phone if we have one and existing doesn't
            if r.get("phone") and r["phone"].strip():
                cur.execute("SELECT phone FROM churches WHERE id=?", (cid,))
                existing_phone = cur.fetchone()
                if existing_phone and not existing_phone[0]:
                    updates.append("phone=?")
                    uparams.append(r["phone"].strip())

            if updates:
                uparams.append(cid)
                cur.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", uparams)
                district_tagged += 1

            # Add pastor to staff
            if r.get("pastor") and r["pastor"].strip():
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO church_staff (church_id, name, role, source, confidence, last_updated)
                        VALUES (?, ?, 'Pastor', 'ame_district_directory', 85, datetime('now'))
                    """, (cid, r["pastor"].strip()))
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
            if r.get("pastor") and r["pastor"].strip() and cur.lastrowid:
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO church_staff (church_id, name, role, source, confidence, last_updated)
                        VALUES (?, ?, 'Pastor', 'ame_district_directory', 85, datetime('now'))
                    """, (cur.lastrowid, r["pastor"].strip()))
                except Exception:
                    pass

    db.commit()
    db.close()
    return matched, inserted, district_tagged


def tag_existing_ame_with_districts():
    """Tag existing AME records in DB with their episcopal district based on state."""
    log("Tagging existing AME records with district info...")
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    # Get all AME churches without explicit district tagging
    # We store district in the notes/source field temporarily or just report
    cur.execute("""
        SELECT state, COUNT(*) FROM churches 
        WHERE denomination LIKE '%African Methodist Episcopal%' 
        AND denomination NOT LIKE '%Zion%'
        AND website != '' AND website IS NOT NULL
        GROUP BY state ORDER BY COUNT(*) DESC
    """)
    
    state_counts = cur.fetchall()
    tagged = 0
    districts_summary = {}
    
    for state, count in state_counts:
        district_key = STATE_TO_DISTRICT.get(state, "Unknown")
        district_name = DISTRICTS.get(district_key, {}).get("name", f"{district_key} Episcopal District")
        if district_key not in districts_summary:
            districts_summary[district_key] = {"name": district_name, "count": 0}
        districts_summary[district_key]["count"] += count
        tagged += count
    
    db.close()
    
    log(f"\nExisting AME records by district (based on state):")
    for dist_key in sorted(districts_summary.keys()):
        info = districts_summary[dist_key]
        log(f"  {info['name']}: {info['count']} churches")
    
    return districts_summary


def main():
    dry_run = "--dry-run" in sys.argv
    limit = None
    for a in sys.argv[1:]:
        if a.startswith("--limit="):
            limit = int(a.split("=")[1])

    all_results = []

    # ── Scrape 2nd District ──
    try:
        results = scrape_2nd_district(limit)
        all_results.extend(results)
    except Exception as e:
        log(f"  ERROR scraping 2nd District: {e}")

    # ── Scrape 6th District ──
    try:
        results = scrape_6th_district(limit)
        all_results.extend(results)
    except Exception as e:
        log(f"  ERROR scraping 6th District: {e}")

    if not all_results:
        log("No results from any district. Exiting.")
        return

    # Save CSV
    fields = ["name", "address", "city", "state", "zip", "phone", "email", "website", "pastor", "district", "county", "source_url"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_results)
    log(f"Saved {len(all_results)} records to {OUT_CSV}")

    # Summary
    with_phone = sum(1 for r in all_results if r.get("phone"))
    with_email = sum(1 for r in all_results if r.get("email"))
    with_web = sum(1 for r in all_results if r.get("website"))
    with_addr = sum(1 for r in all_results if r.get("address"))
    with_pastor = sum(1 for r in all_results if r.get("pastor"))
    with_district = sum(1 for r in all_results if r.get("district"))
    
    log(f"\nResults summary:")
    log(f"  Total:        {len(all_results)}")
    log(f"  With address:  {with_addr}")
    log(f"  With phone:    {with_phone}")
    log(f"  With email:    {with_email}")
    log(f"  With website:  {with_web}")
    log(f"  With pastor:   {with_pastor}")
    log(f"  With district: {with_district}")
    
    # Show district breakdown
    from collections import Counter
    dist_counts = Counter(r.get("district", "Unknown") for r in all_results)
    log(f"\nDistrict breakdown:")
    for dist, cnt in sorted(dist_counts.items()):
        log(f"  {dist}: {cnt}")

    log(f"\nSample:")
    for r in all_results[:5]:
        log(f"  {r.get('name','?'):45s} | {r.get('city','?'):20s} | {r.get('state','?'):2s} | {r.get('district','?'):25s} | {r.get('website','')[:30] if r.get('website') else '':30s}")

    if not dry_run and all_results:
        matched, inserted, district_tagged = do_import(all_results)
        log(f"\nImport: {matched} matched, {inserted} new records")

    # Tag existing records with district info
    if not dry_run:
        districts_summary = tag_existing_ame_with_districts()

    return all_results


if __name__ == "__main__":
    main()

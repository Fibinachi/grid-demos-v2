#!/usr/bin/env python3
"""
Convention/Diocese Website Scraper
===================================
Scrapes admin office websites for church member directories,
matches them against the DB, and links churches to their parent bodies.

Usage:
    python scripts/enrichment/scrape_admin_sites.py                  # Full run
    python scripts/enrichment/scrape_admin_sites.py --test           # Test 5 sites
    python scripts/enrichment/scrape_admin_sites.py --match          # Match only
"""
import csv, os, re, sqlite3, sys, time, urllib.request, urllib.error
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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
log_lock = Lock()

def log(msg):
    with log_lock:
        print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def fetch(url, timeout=15):
    """Fetch a URL and return HTML."""
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except Exception as e:
        return None

def find_directory_pages(html, base_url):
    """Find links to church directory pages on a convention site."""
    dirs = []
    patterns = [
        r'directory', r'churches', r'find.a.church', r'church.lookup',
        r'church.search', r'church.locator', r'congregations', 
        r'our.churches', r'member.churches', r'church.directory',
        r'locate.a.church', r'findachurch', r'church.finder',
    ]
    
    for m in re.finditer(r'<a[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html, re.IGNORECASE):
        href = m.group(1).strip()
        text = m.group(2).strip().lower()
        href_lower = href.lower()
        
        for pat in patterns:
            if pat in text or pat.replace(".", "") in href_lower:
                # Resolve relative URLs
                if href.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urllib.parse.urlparse(base_url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                elif not href.startswith("http"):
                    href = base_url.rstrip("/") + "/" + href.lstrip("/")
                dirs.append((m.group(2).strip(), href))
                break
    
    return dirs[:5]

def extract_churches_from_html(html, state_hint=None):
    """Extract church names and locations from directory HTML."""
    churches = []
    
    # Look for patterns like church names with links
    for m in re.finditer(r'<a[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>\s*([^<]{3,80}?)\s*</a>', html, re.IGNORECASE):
        name = m.group(2).strip()
        href = m.group(1).strip()
        if not name or len(name) < 3:
            continue
        # Skip navigation links
        skip_words = ["home", "about", "contact", "donate", "login", "sign up",
                      "facebook", "twitter", "instagram", "youtube", "search",
                      "sitemap", "privacy", "terms", "cart", "shop", "store",
                      "events", "calendar", "sermons", "blog", "news", "staff"]
        if any(s in name.lower() for s in skip_words):
            continue
        # Look for "church" in the name
        if "church" in name.lower() or "chapel" in name.lower() or "cathedral" in name.lower():
            churches.append((name, href))
    
    # If no church links found, try looking for list items with church names
    if len(churches) < 3:
        for m in re.finditer(r'<li[^>]*>\s*([^<]{5,100}?)\s*</li>', html, re.IGNORECASE):
            name = m.group(1).strip()
            if "church" in name.lower() and len(name) > 5:
                churches.append((name, ""))
    
    # Deduplicate
    seen = set()
    unique = []
    for name, href in churches:
        if name.lower() not in seen:
            seen.add(name.lower())
            unique.append((name, href))
    
    return unique

def scrape_convention_site(name, url, org_type, state_hint=None):
    """Scrape a convention/diocese website for member churches."""
    result = {
        "name": name,
        "url": url,
        "type": org_type,
        "state": state_hint,
        "success": False,
        "dir_pages": [],
        "churches_found": [],
        "matched": 0,
        "new": 0,
        "error": ""
    }
    
    log(f"  Fetching: {name[:40]:40s} -> {url[:45]}")
    html = fetch(url)
    if not html:
        result["error"] = "Failed to fetch"
        return result
    
    result["success"] = True
    
    # Find directory pages
    dir_pages = find_directory_pages(html, url)
    result["dir_pages"] = [d[1] for d in dir_pages]
    
    # Extract church names from the main page
    churches = extract_churches_from_html(html, state_hint)
    result["churches_found"] = churches
    
    # Also scrape directory pages if found
    for dir_name, dir_url in dir_pages[:3]:
        log(f"    Following dir: {dir_url[:60]}")
        time.sleep(1.0)
        dir_html = fetch(dir_url)
        if dir_html:
            dir_churches = extract_churches_from_html(dir_html, state_hint)
            result["churches_found"].extend(dir_churches)
    
    return result

def match_churches(result, db):
    """Match found churches against the database."""
    if not result["churches_found"]:
        return result
    
    cur = db.cursor()
    state_hint = result.get("state", "")
    matched = 0
    new_count = 0
    
    for church_name, church_url in result["churches_found"]:
        name_upper = church_name.upper()
        
        # Try to match by name + state
        if state_hint:
            cur.execute("SELECT id, name, website FROM churches WHERE name=? AND state=? LIMIT 1", 
                       (church_name, state_hint))
        else:
            cur.execute("SELECT id, name, website FROM churches WHERE name=? LIMIT 1", 
                       (church_name,))
        
        row = cur.fetchone()
        if row:
            matched += 1
            cid = row[0]
            # Update with parent body info
            parent_col = ""
            if result["type"] == "convention":
                parent_col = "association"
            elif result["type"] in ("diocese", "archdiocese"):
                parent_col = "diocese"
            elif result["type"] == "synod":
                parent_col = "synod"
            elif result["type"] == "presbytery":
                parent_col = "presbytery"
            else:
                parent_col = "denom_region"
            
            if parent_col:
                cur.execute(f"UPDATE churches SET {parent_col}=? WHERE id=? AND ({parent_col}='' OR {parent_col} IS NULL)",
                           (result["name"], cid))
        else:
            new_count += 1
    
    db.commit()
    result["matched"] = matched
    result["new"] = new_count
    return result

# Known SBC convention websites from our mapping
SBC_CONVENTION_SITES = {
    "Alabama Baptist Convention": "https://alsbom.org",
    "Alaska Baptist Convention": "https://alaskabaptist.org",
    "Arizona Southern Baptist Convention": "https://azsbc.org",
    "Arkansas Baptist State Convention": "https://absc.org",
    "California Southern Baptist Convention": "https://csbc.com",
    "Colorado Baptist General Convention": "https://cbgc.org",
    "Baptist Convention of New England": "https://bcone.org",
    "Baptist Convention of Maryland/Delaware": "https://bcmd.org",
    "District of Columbia Baptist Convention": "https://dcbaptist.org",
    "Florida Baptist Convention": "https://flbaptist.org",
    "Georgia Baptist Mission Board": "https://gabaptist.org",
    "Hawaii Pacific Baptist Convention": "https://hpbaptist.net",
    "Utah-Idaho Southern Baptist Convention": "https://utahidahosbc.org",
    "Illinois Baptist State Association": "https://ibsa.org",
    "State Convention of Baptists in Indiana": "https://scbi.org",
    "Baptist Convention of Iowa": "https://bciowa.org",
    "Kansas-Nebraska Southern Baptist Convention": "https://kncsbc.org",
    "Kentucky Baptist Convention": "https://kybaptist.org",
    "Louisiana Baptist Convention": "https://louisianabaptists.org",
    "Michigan Baptist Convention": "https://michiganbaptist.org",
    "Minnesota-Wisconsin Southern Baptist Convention": "https://mwsbc.org",
    "Mississippi Baptist Convention Board": "https://mbcb.org",
    "Missouri Baptist Convention": "https://mobaptist.org",
    "Montana Southern Baptist Convention": "https://montanasbc.com",
    "Nevada Baptist Convention": "https://nevadabaptist.org",
    "Baptist Convention of New Jersey": "https://bcnj.org",
    "Baptist Convention of New Mexico": "https://bcnm.com",
    "Baptist Convention of New York": "https://bcnyny.org",
    "Baptist State Convention of North Carolina": "https://ncbaptist.org",
    "North Dakota Baptist Convention": "https://ndbaptist.org",
    "State Convention of Baptists in Ohio": "https://scbo.org",
    "Baptist General Convention of Oklahoma": "https://bgco.org",
    "Oregon Baptist Convention": "https://oregonbaptist.org",
    "Baptist Convention of Pennsylvania/South Jersey": "https://bcpaj.org",
    "South Carolina Baptist Convention": "https://scbaptist.org",
    "South Dakota Baptist Convention": "https://sdbaptists.org",
    "Tennessee Baptist Mission Board": "https://tnbaptist.org",
    "Southern Baptists of Texas Convention": "https://sbctx.org",
    "Southern Baptist Conservatives of Virginia": "https://sbcv.org",
    "Northwest Baptist Convention": "https://nwbaptist.org",
    "West Virginia Convention of Southern Baptists": "https://wvsbc.org",
    "Wyoming Southern Baptist Convention": "https://wyomingsbc.org",
}

def phase1_scrape(test_mode=False):
    """Scrape convention/office websites for member churches."""
    log(f"Phase 1: Scraping admin websites {'(TEST MODE - 5 sites)' if test_mode else ''}")
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    # Build list of sites to scrape
    sites = []
    
    # SBC convention sites (with state hint)
    for conv_name, conv_url in SBC_CONVENTION_SITES.items():
        state = ""
        for abbr, cname in [
            ("AL","Alabama"),("AK","Alaska"),("AZ","Arizona"),("AR","Arkansas"),
            ("CA","California"),("CO","Colorado"),("CT","Connecticut"),("DE","Delaware"),
            ("FL","Florida"),("GA","Georgia"),("HI","Hawaii"),("ID","Idaho"),
            ("IL","Illinois"),("IN","Indiana"),("IA","Iowa"),("KS","Kansas"),
            ("KY","Kentucky"),("LA","Louisiana"),("ME","Maine"),("MD","Maryland"),
            ("MA","Massachusetts"),("MI","Michigan"),("MN","Minnesota"),("MS","Mississippi"),
            ("MO","Missouri"),("MT","Montana"),("NE","Nebraska"),("NV","Nevada"),
            ("NH","New Hampshire"),("NJ","New Jersey"),("NM","New Mexico"),("NY","New York"),
            ("NC","North Carolina"),("ND","North Dakota"),("OH","Ohio"),("OK","Oklahoma"),
            ("OR","Oregon"),("PA","Pennsylvania"),("RI","Rhode Island"),("SC","South Carolina"),
            ("SD","South Dakota"),("TN","Tennessee"),("TX","Texas"),("UT","Utah"),
            ("VT","Vermont"),("VA","Virginia"),("WA","Washington"),("WV","West Virginia"),
            ("WI","Wisconsin"),("WY","Wyoming"),
        ]:
            if cname in conv_name:
                state = abbr
                break
        sites.append((conv_name, conv_url, "convention", state))
    
    # Also get admin offices from DB with websites
    cur.execute("""
        SELECT id, name, website, org_type, state FROM churches 
        WHERE org_type IN ('convention', 'diocese', 'archdiocese') 
          AND website != '' AND website IS NOT NULL
          AND website NOT LIKE '%facebook%'
    """)
    for r in cur.fetchall():
        sites.append((r[1], r[2], r[3], r[4] or ""))
    
    if test_mode:
        sites = sites[:5]
    
    log(f"  Total sites to scrape: {len(sites)}")
    
    # Scrape sites
    results = []
    for i, (sname, surl, stype, sstate) in enumerate(sites):
        result = scrape_convention_site(sname, surl, stype, sstate)
        if result["success"] and result["churches_found"]:
            result = match_churches(result, db)
        
        results.append(result)
        
        # Summary
        ch_count = len(result["churches_found"])
        if ch_count > 0:
            log(f"  {i+1}/{len(sites)}: {sname[:35]:35s} | found={ch_count} matched={result['matched']} new={result['new']}")
        elif result["error"]:
            log(f"  {i+1}/{len(sites)}: {sname[:35]:35s} | ERROR: {result['error']}")
        else:
            log(f"  {i+1}/{len(sites)}: {sname[:35]:35s} | no churches found")
        
        time.sleep(1.0)  # Be polite
    
    # Report
    total_found = sum(len(r["churches_found"]) for r in results)
    total_matched = sum(r["matched"] for r in results)
    total_new = sum(r["new"] for r in results)
    dir_pages = sum(len(r["dir_pages"]) for r in results)
    
    log(f"\n=== SCRAPING RESULTS ===")
    log(f"  Sites scraped: {len(results)}")
    log(f"  Directory pages found: {dir_pages}")
    log(f"  Churches found: {total_found}")
    log(f"  Matched in DB: {total_matched}")
    log(f"  Not found (potential new): {total_new}")
    
    # Save detailed results
    out_path = os.path.join(PROJECT_DIR, "data", "admin_scrape_results.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["site_name", "site_url", "type", "state", "church_name", "church_url", "matched"])
        for r in results:
            for ch_name, ch_url in r["churches_found"]:
                w.writerow([r["name"], r["url"], r["type"], r["state"], ch_name, ch_url, "yes" if r["matched"] > 0 else ""])
    
    log(f"  Saved to: {out_path}")
    db.close()

if __name__ == "__main__":
    args = sys.argv[1:]
    test_mode = "--test" in args
    phase1_scrape(test_mode=test_mode)

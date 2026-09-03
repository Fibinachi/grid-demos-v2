#!/usr/bin/env python3
"""
SC Baptist Association Scraper
===============================
Scrapes all SC Baptist association websites to find member churches,
then cross-references against unlabeled Baptist churches in our DB.

Usage:
    python scripts/scrapers/scrape_sc_baptist_associations.py
"""
import csv, json, os, re, sqlite3, time, urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        PROJECT_DIR = os.path.expanduser("~/grantwizard")
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def fetch(url, timeout=15):
    headers = {
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        r = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode('utf-8', 'replace')
    except:
        return None

# Known SC Baptist association websites
# Source: scbaptist.org associations page + research
ASSOCIATIONS = {
    "aiken": "https://www.aikenbaptistassociation.org",
    "allendale-hampton": "",
    "barnwell-bamberg": "",
    "beaverdam": "",
    "broad-river": "",
    "carolina": "",
    "charleston": "",
    "chester": "",
    "chesterfield": "",
    "colleton": "",
    "columbia-metro": "",
    "edgefield": "",
    "edisto": "",
    "florence": "",
    "greenville": "",
    "kershaw": "",
    "lakelands": "",
    "laurens": "",
    "lexington": "",
    "marion": "",
    "moriah": "",
    "north-spartan": "",
    "orangeburg-calhoun": "",
    "palmetto": "",
    "pee-dee": "",
    "pickens-twelve-mile": "",
    "piedmont": "",
    "reedy-river": "",
    "ridge": "",
    "saluda": "",
    "santee": "",
    "savannah-river": "",
    "screven": "",
    "southeast": "",
    "spartanburg-county": "",
    "three-rivers": "",
    "union-county": "",
    "waccamaw": "",
    "welsh-neck": "",
    "williamsburg": "",
    "woodruff": "",
    "york": "",
}

def try_discover_association_websites():
    """Try to discover association websites from scbaptist.org."""
    log("Discovering association websites from scbaptist.org...")
    html = fetch("https://www.scbaptist.org/associations/")
    if not html:
        log("  Failed to fetch scbaptist.org")
        return
    
    # Find association links: /associations/{name}-baptist-association/
    links = re.findall(r'href="(https://www\.scbaptist\.org/associations/([^/]+)-baptist-association/)"', html)
    log("  Found %d associations on scbaptist.org" % len(links))
    
    for url, slug in links:
        log("  Checking %s..." % slug)
        assoc_html = fetch(url)
        if assoc_html:
            # Try to find the association's own website
            # Often listed as a link or in the contact info
            website = ""
            m = re.search(r'href="(https?://(?:www\.)?(?!scbaptist)[^"]*)"[^>]*>(?:Visit|www\.|Website)', assoc_html, re.I)
            if m:
                website = m.group(1).rstrip('/')
            else:
                # Guess based on common patterns
                guesses = [
                    "https://www.%sbaptistassociation.org" % slug,
                    "https://www.%s-baptist.org" % slug,
                    "https://%sbaptist.com" % slug,
                    "https://%sassociation.org" % slug.replace('-', ''),
                ]
                for guess in guesses:
                    try:
                        r = urllib.request.Request(guess, headers={'User-Agent': UA}, method='HEAD')
                        urllib.request.urlopen(r, timeout=5)
                        website = guess
                        break
                    except:
                        pass
            
            if website:
                key = slug.replace('-', ' ')
                log("    -> %s" % website)
                ASSOCIATIONS[slug] = website

def scrape_association_churches(url, assoc_name):
    """Scrape church list from an association website."""
    churches = set()
    
    # Try /churches page
    for path in ['/churches', '/churches/', '/our-churches', '/member-churches', '/church-directory']:
        html = fetch(url + path)
        if html:
            # Extract church names - various patterns
            # Pattern: Name | Church (Aiken site style)
            found = re.findall(r'([A-Z][A-Za-z\s\.]+(?:Baptist|Church|Chapel|Worship|Fellowship|Community)[A-Za-z\s\.]*)\s*\|\s*Church', html)
            for f in found:
                churches.add(f.strip())
            
            # Pattern: <li>Church Name</li>
            found2 = re.findall(r'<li[^>]*>([A-Z][A-Za-z\s\.&]+(?:Baptist|Church))</li>', html)
            for f in found2:
                churches.add(f.strip())
            
            # Pattern: plain text in main content
            found3 = re.findall(r'>([A-Z][A-Za-z\s\.]{5,}(?:Baptist Church|Baptist Chapel|Mission))<', html)
            for f in found3:
                if 'Baptist' in f or 'Church' in f:
                    churches.add(f.strip())
        
        if churches:
            break
    
    return churches

def normalize_name(name):
    """Normalize a church name for matching."""
    n = name.upper().strip()
    n = re.sub(r'\s+', ' ', n)
    n = n.replace('&', 'AND')
    n = re.sub(r'[^\w\s]', '', n)
    return n.strip()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--discover-only', action='store_true', help='Only discover association websites')
    parser.add_argument('--process', action='store_true', help='Process and tag DB records')
    args = parser.parse_args()
    
    # Discover association websites
    try_discover_association_websites()
    
    # Save discovered websites
    assoc_fp = os.path.join(OUT_DIR, 'baptist_associations.json')
    with open(assoc_fp, 'w') as f:
        json.dump(ASSOCIATIONS, f, indent=2)
    log("Saved association list to %s" % assoc_fp)
    
    if args.discover_only:
        return
    
    # Scrape each association
    all_assoc_churches = {}
    for slug, url in ASSOCIATIONS.items():
        if not url:
            continue
        log("Scraping %s..." % slug)
        churches = scrape_association_churches(url, slug)
        all_assoc_churches[slug] = list(churches)
        log("  Found %d churches" % len(churches))
        time.sleep(1)
    
    # Save scraped churches
    churches_fp = os.path.join(OUT_DIR, 'baptist_association_churches.json')
    with open(churches_fp, 'w') as f:
        json.dump(all_assoc_churches, f, indent=2)
    log("Saved association churches to %s" % churches_fp)
    
    if not args.process:
        return
    
    # Cross-reference with DB
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    # Get all unlabeled Baptist churches in SC
    rows = cur.execute("""
        SELECT id, name, city FROM churches 
        WHERE state='SC' 
          AND (denomination IS NULL OR denomination = '' OR denomination = ' ')
          AND UPPER(name) LIKE '%BAPTIST%'
          AND UPPER(name) NOT LIKE '%ASSOCIATION%'
          AND UPPER(name) NOT LIKE '%CONVENTION%'
          AND UPPER(name) NOT LIKE '%FOUNDATION%'
          AND UPPER(name) NOT LIKE '%COURIER%'
          AND UPPER(name) NOT LIKE '%FUND%'
    """).fetchall()
    
    log("\nCross-referencing %d unlabeled Baptist churches against association lists..." % len(rows))
    
    # Build normalized set of all association churches
    assoc_normalized = set()
    assoc_name_map = {}
    for slug, churches in all_assoc_churches.items():
        for c in churches:
            n = normalize_name(c)
            assoc_normalized.add(n)
            assoc_name_map[n] = slug
    
    found_sbc = 0
    not_found = 0
    
    for r in rows:
        cid, name, city = r
        db_name = normalize_name(name)
        
        # Check if this church name matches any association church
        is_sbc = False
        matched_assoc = ""
        
        for an in assoc_normalized:
            # Try exact match
            if db_name == an:
                is_sbc = True
                matched_assoc = assoc_name_map.get(an, '')
                break
            # Try if DB name contains association name or vice versa
            if db_name in an or an in db_name:
                is_sbc = True
                matched_assoc = assoc_name_map.get(an, '')
                break
        
        if is_sbc:
            cur.execute("""
                UPDATE churches SET denomination='Southern Baptist Convention', 
                    notes=COALESCE(NULLIF(notes,''),'') || ? WHERE id=?
            """, ('; SBC via ' + matched_assoc + ' association', cid))
            found_sbc += 1
        else:
            not_found += 1
    
    db.commit()
    db.close()
    log("Tagged %d as SBC through associations, %d remain unclassified" % (found_sbc, not_found))

if __name__ == '__main__':
    main()

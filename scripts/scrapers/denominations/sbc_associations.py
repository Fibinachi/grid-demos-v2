"""Scrape all SC Baptist association websites for member churches."""
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

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def fetch(url, timeout=15):
    headers = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    try:
        r = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode('utf-8', 'replace')
    except:
        return None

# Association slugs from scbaptist.org + known websites from prior research
ASSOCIATIONS = {
    "aiken": {"name": "Aiken Baptist Association", "url": "https://www.aikenbaptistassociation.org"},
    "allendale-hampton": {"name": "Allendale-Hampton Baptist Association", "url": ""},
    "barnwell-bamberg": {"name": "Barnwell-Bamberg Baptist Association", "url": ""},
    "beaverdam": {"name": "Beaverdam Baptist Association", "url": ""},
    "broad-river": {"name": "Broad River Baptist Association", "url": ""},
    "carolina": {"name": "Carolina Baptist Association", "url": ""},
    "charleston": {"name": "Charleston Baptist Association", "url": ""},
    "chester": {"name": "Chester Baptist Association", "url": ""},
    "chesterfield": {"name": "Chesterfield Baptist Association", "url": ""},
    "colleton": {"name": "Colleton Baptist Association", "url": ""},
    "columbia-metro": {"name": "Columbia Metro Baptist Association", "url": ""},
    "edgefield": {"name": "Edgefield Baptist Association", "url": ""},
    "edisto": {"name": "Edisto Baptist Association", "url": ""},
    "florence": {"name": "Florence Baptist Association", "url": ""},
    "greenville": {"name": "Greenville Baptist Association", "url": ""},
    "kershaw": {"name": "Kershaw Baptist Association", "url": ""},
    "lakelands": {"name": "Lakelands Baptist Association", "url": ""},
    "laurens": {"name": "Laurens Baptist Association", "url": ""},
    "lexington": {"name": "Lexington Baptist Association", "url": ""},
    "marion": {"name": "Marion Baptist Association", "url": ""},
    "moriah": {"name": "Moriah Baptist Association", "url": ""},
    "north-spartan": {"name": "North Spartan Baptist Association", "url": ""},
    "orangeburg-calhoun": {"name": "Orangeburg-Calhoun Baptist Association", "url": ""},
    "palmetto": {"name": "Palmetto Baptist Association", "url": ""},
    "pee-dee": {"name": "Pee Dee Baptist Association", "url": ""},
    "pickens-twelve-mile": {"name": "Pickens-Twelve Mile Baptist Association", "url": ""},
    "piedmont": {"name": "Piedmont Baptist Association", "url": ""},
    "reedy-river": {"name": "Reedy River Baptist Association", "url": ""},
    "ridge": {"name": "Ridge Baptist Association", "url": ""},
    "saluda": {"name": "Saluda Baptist Association", "url": ""},
    "santee": {"name": "Santee Baptist Association", "url": ""},
    "savannah-river": {"name": "Savannah River Baptist Association", "url": ""},
    "screven": {"name": "Screven Baptist Association", "url": ""},
    "southeast": {"name": "Southeast Baptist Association", "url": ""},
    "spartanburg-county": {"name": "Spartanburg County Baptist Network", "url": ""},
    "three-rivers": {"name": "Three Rivers Baptist Association", "url": ""},
    "union-county": {"name": "Union County Baptist Association", "url": ""},
    "waccamaw": {"name": "Waccamaw Baptist Association", "url": ""},
    "welsh-neck": {"name": "Welsh Neck Baptist Association", "url": ""},
    "williamsburg": {"name": "Williamsburg Baptist Association", "url": ""},
    "woodruff": {"name": "Woodruff Baptist Association", "url": ""},
    "york": {"name": "York Baptist Association", "url": ""},
}

def try_guess_websites():
    """Try common URL patterns for association websites."""
    patterns = [
        "https://www.{slug}baptistassociation.org",
        "https://www.{slug}-baptist.org",
        "https://www.{slug}baptist.com",
        "https://{slug}baptist.com",
        "https://{slug}baptistassociation.com",
        "https://{slug}association.org",
        "https://{slug}baptist.org",
    ]
    
    for slug, info in ASSOCIATIONS.items():
        if info["url"]:
            continue
        slug_clean = slug.replace('-', '')
        for pattern in patterns:
            guess = pattern.format(slug=slug_clean)
            try:
                r = urllib.request.Request(guess, headers={'User-Agent': UA}, method='HEAD')
                urllib.request.urlopen(r, timeout=3)
                info["url"] = guess
                log("  %s -> %s" % (info["name"][:30], guess))
                break
            except:
                continue

def scrape_association_churches(url, assoc_name):
    """Scrape church list from an association website."""
    churches = set()
    
    # Try common church directory paths
    paths = ['/churches', '/churches/', '/our-churches', '/member-churches', 
             '/church-directory', '/our-churches/', '/members', '/church-locator']
    
    for path in paths:
        html = fetch(url + path)
        if not html:
            continue
        
        # Pattern 1: "Name | Church" (FaithConnector style like Aiken)
        found = re.findall(r'([A-Z][A-Za-z\s\.\'\-&]+(?:Baptist|Church|Chapel|Worship|Fellowship|Community|Temple|Cathedral)[A-Za-z\s\.\'\-&]*?)\s*\|\s*Church', html)
        for f in found:
            churches.add(f.strip())
        
        # Pattern 2: <li> or <a> with church name in main content
        if not churches:
            found2 = re.findall(r'<a[^>]*href="[^"]*"[^>]*>([A-Z][A-Za-z\s\.\'\-&]{8,}(?:Baptist|Church))</a>', html)
            for f in found2:
                if 'Baptist' in f or 'Church' in f:
                    churches.add(f.strip())
        
        # Pattern 3: Plain text in page
        if not churches:
            # Get main content area
            main = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL | re.I)
            if main:
                found3 = re.findall(r'>([A-Z][A-Za-z\s\.\'\-&]{8,}(?:Baptist Church|Baptist Chapel|Missionary Baptist))<', main.group(1))
                for f in found3:
                    churches.add(f.strip())
        
        if churches:
            log("    Found %d churches via %s" % (len(churches), path))
            break
    
    return churches


def main():
    log("Discovering association websites...")
    try_guess_websites()
    
    found_sites = sum(1 for v in ASSOCIATIONS.values() if v["url"])
    log("Found websites for %d/%d associations" % (found_sites, len(ASSOCIATIONS)))
    
    # Save discovered URLs
    fp = os.path.join(OUT_DIR, 'baptist_associations.json')
    with open(fp, 'w') as f:
        json.dump(ASSOCIATIONS, f, indent=2)
    
    # Scrape each association
    all_churches = {}  # slug -> [church names]
    
    for slug, info in ASSOCIATIONS.items():
        if not info["url"]:
            log("Skipping %s (no website found)" % info["name"][:30])
            continue
        
        log("Scraping %s..." % info["name"][:35])
        churches = scrape_association_churches(info["url"], info["name"])
        all_churches[slug] = list(churches)
        if churches:
            for c in list(churches)[:3]:
                log("    %s" % c[:50])
        time.sleep(0.5)
    
    # Save scraped churches
    cfp = os.path.join(OUT_DIR, 'baptist_association_churches.json')
    with open(cfp, 'w') as f:
        json.dump(all_churches, f, indent=2)
    
    total = sum(len(v) for v in all_churches.values())
    log("\nTotal churches found across all associations: %d" % total)
    
    # Cross-reference with DB for the remaining unlabeled
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    # Build normalized set of all association church names
    assoc_set = set()
    assoc_source = {}
    for slug, churches in all_churches.items():
        for c in churches:
            n = re.sub(r'[^A-Z0-9\s]', '', c.upper().strip())
            n = re.sub(r'\s+', ' ', n)
            assoc_set.add(n)
            if n not in assoc_source:
                assoc_source[n] = slug
    
    # Get remaining unlabeled Baptist churches in SC
    rows = cur.execute("""
        SELECT id, name, city FROM churches 
        WHERE state='SC'
          AND (denomination IS NULL OR denomination = '' OR denomination = ' ' 
               OR denomination = 'Independent Baptist')
          AND UPPER(name) LIKE '%BAPTIST%'
        ORDER BY name
    """).fetchall()
    
    log("\nCross-referencing %d unlabeled churches against association lists..." % len(rows))
    
    tagged = 0
    still_independent = 0
    
    for r in rows:
        cid, name, city = r
        db_name = re.sub(r'[^A-Z0-9\s]', '', name.upper().strip())
        db_name = re.sub(r'\s+', ' ', db_name)
        
        matched = False
        source = ""
        
        for an in assoc_set:
            if db_name == an or (db_name in an and len(db_name) > 10) or (an in db_name and len(an) > 10):
                matched = True
                source = assoc_source.get(an, '')
                break
        
        # Also check against the SBC sitemap list
        if not matched:
            # Check if already tagged
            pass
        
        if matched:
            cur.execute("UPDATE churches SET denomination='Southern Baptist Convention', notes=COALESCE(NULLIF(notes,''),'') || ? WHERE id=?", 
                       ('; SBC via ' + source + ' association', cid))
            tagged += 1
        elif cur.execute("SELECT denomination FROM churches WHERE id=?", (cid,)).fetchone()[0] == 'Independent Baptist':
            still_independent += 1
    
    db.commit()
    db.close()
    
    log("Tagged %d additional as SBC via associations" % tagged)
    log("Remaining Independent Baptist: %d" % still_independent)
    log("Done!")


if __name__ == '__main__':
    main()

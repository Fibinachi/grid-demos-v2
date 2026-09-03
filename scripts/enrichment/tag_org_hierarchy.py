#!/usr/bin/env python3
"""
Tag & Link Denominational Hierarchy
====================================
Phase 1: Tag all database records with organizational type (org_type)
Phase 2: Build known denomination-to-parent mappings
Phase 3: Scrape office websites for member directories
Phase 4: Link churches to their parent conventions/associations/dioceses

Usage:
    python scripts/enrichment/tag_org_hierarchy.py --tag-only
    python scripts/enrichment/tag_org_hierarchy.py --map-sbc
    python scripts/enrichment/tag_org_hierarchy.py --scrape
    python scripts/enrichment/tag_org_hierarchy.py --all
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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

log_lock = Lock()
def log(msg):
    with log_lock:
        print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def get_db():
    return sqlite3.connect(DB_PATH)

# ═══════════════════════════════════════════════════════════════
# PHASE 1: Tag organizational types
# ═══════════════════════════════════════════════════════════════

ORG_RULES = [
    # (name_pattern, org_type, priority)
    # Priority: higher = more specific, lower = generic fallback
    (r'\bSeminary\b', 'seminary', 50),
    (r'\bTheological\s+(Seminary|School|Institute)\b', 'seminary', 55),
    (r'\bSchool of (Theology|Divinity|Ministry)\b', 'seminary', 50),
    (r'\bCollege\b', 'college', 30),  # generic, many churches have "College" in name
    (r'\bUniversity\b', 'university', 30),
    
    (r'\bDiocese\b', 'diocese', 60),
    (r'\bArchdiocese\b', 'archdiocese', 60),
    (r'\bDiocesan\b', 'diocese', 55),
    
    (r'\bPresbytery\b', 'presbytery', 60),
    (r'\bSynod\b', 'synod', 60),
    
    (r'\bConference\s+of\s+the\b', 'conference', 50),
    (r'\bAnnual\s+Conference\b', 'conference', 55),
    (r'\bUnion\s+Conference\b', 'conference', 50),
    (r'\bConference\s+of\s+Churches\b', 'conference', 55),
    
    (r'\bConvention\b', 'convention', 50),
    (r'\bBaptist\s+General\s+Convention\b', 'convention', 60),
    (r'\bState\s+Baptist\s+Convention\b', 'convention', 60),
    (r'\bBaptist\s+Convention\b', 'convention', 55),
    
    (r'\bMission\s+Board\b', 'mission_board', 60),
    (r'\bExecutive\s+(Board|Committee)\b', 'executive_board', 60),
    
    (r'\bDistrict\s+(Council|Office|Board)\b', 'district', 50),
    (r'\bDistrict\s+of\s+the\b', 'district', 40),
    
    (r'\bHeadquarters\b', 'headquarters', 55),
    
    (r'\bPublishing\b', 'publishing', 50),
    (r'\bResource\s+Center\b', 'resource_center', 40),
    
    (r'\bFoundation\b', 'foundation', 25),  # very generic
    (r'\bCamp\b', 'camp', 25),
    (r'\bRetreat\s+Center\b', 'retreat_center', 40),
    (r'\bRetreat\b', 'retreat', 25),
    
    # Generic: anything with "church" is a church
    (r'\bChurch\b', 'church', 10),
    (r'\bChapel\b', 'church', 10),
    (r'\bCathedral\b', 'church', 10),
    (r'\bParish\b', 'parish', 45),
    (r'\bMinistries?\b', 'ministry', 15),
    (r'\bFellowship\b', 'fellowship', 15),
    (r'\bTabernacle\b', 'church', 10),
    (r'\bTemple\b', 'church', 10),
    (r'\bCongregation\b', 'church', 10),
    (r'\bAssembly\b', 'church', 10),
]

def classify_org_type(name):
    """Classify a record's organizational type based on name patterns."""
    if not name:
        return "unknown"
    best_type = "unknown"
    best_prio = 0
    
    for pattern, org_type, priority in ORG_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            if priority > best_prio:
                best_type = org_type
                best_prio = priority
    
    return best_type

def phase1_tag():
    """Tag all records with their organizational type."""
    log("Phase 1: Tagging organizational types...")
    db = get_db()
    cur = db.cursor()
    
    # Add org_type column if not exists
    cur.execute("PRAGMA table_info(churches)")
    cols = [col[1] for col in cur.fetchall()]
    if "org_type" not in cols:
        log("  Adding org_type column...")
        cur.execute("ALTER TABLE churches ADD COLUMN org_type TEXT DEFAULT 'church'")
    
    # Count current
    cur.execute("SELECT COUNT(*) FROM churches")
    total = cur.fetchone()[0]
    log(f"  Total records: {total}")
    
    # Classify batch by batch
    BATCH = 1000
    offset = 0
    
    while offset < total:
        cur.execute(f"SELECT id, name FROM churches LIMIT {BATCH} OFFSET {offset}")
        rows = cur.fetchall()
        if not rows:
            break
        
        for rid, name in rows:
            ot = classify_org_type(name)
            cur.execute("UPDATE churches SET org_type=? WHERE id=?", (ot, rid))
        
        db.commit()
        offset += BATCH
        if offset % 10000 == 0:
            log(f"  Tagged {offset}/{total}")
    
    # Final count
    cur.execute("SELECT org_type, COUNT(*) FROM churches GROUP BY org_type ORDER BY COUNT(*) DESC")
    log("Tagging complete:")
    total = 0
    for t, cnt in cur.fetchall():
        log(f"  {t:20s}: {cnt}")
        total += cnt
    log(f"  {'TOTAL':20s}: {total}")
    db.close()

# ═══════════════════════════════════════════════════════════════
# PHASE 2: SBC State Convention Mapping
# ═══════════════════════════════════════════════════════════════

# Known SBC state conventions and their official names
SBC_STATE_CONVENTIONS = {
    "AL": "Alabama Baptist Convention",
    "AK": "Alaska Baptist Convention",
    "AZ": "Arizona Southern Baptist Convention",
    "AR": "Arkansas Baptist State Convention",
    "CA": "California Southern Baptist Convention",
    "CO": "Colorado Baptist General Convention",
    "CT": "Baptist Convention of New England",  # CT is in BCNE
    "DE": "Baptist Convention of Maryland/Delaware",
    "DC": "District of Columbia Baptist Convention",
    "FL": "Florida Baptist Convention",
    "GA": "Georgia Baptist Mission Board",
    "HI": "Hawaii Pacific Baptist Convention",
    "ID": "Utah-Idaho Southern Baptist Convention",
    "IL": "Illinois Baptist State Association",
    "IN": "State Convention of Baptists in Indiana",
    "IA": "Baptist Convention of Iowa",
    "KS": "Kansas-Nebraska Southern Baptist Convention",
    "KY": "Kentucky Baptist Convention",
    "LA": "Louisiana Baptist Convention",
    "ME": "Baptist Convention of New England",  # ME is in BCNE
    "MD": "Baptist Convention of Maryland/Delaware",
    "MA": "Baptist Convention of New England",
    "MI": "Michigan Baptist Convention",
    "MN": "Minnesota-Wisconsin Southern Baptist Convention",
    "MS": "Mississippi Baptist Convention Board",
    "MO": "Missouri Baptist Convention",
    "MT": "Montana Southern Baptist Convention",
    "NE": "Kansas-Nebraska Southern Baptist Convention",
    "NV": "Nevada Baptist Convention",
    "NH": "Baptist Convention of New England",
    "NJ": "Baptist Convention of New Jersey",
    "NM": "Baptist Convention of New Mexico",
    "NY": "Baptist Convention of New York",
    "NC": "Baptist State Convention of North Carolina",
    "ND": "North Dakota Baptist Convention",
    "OH": "State Convention of Baptists in Ohio",
    "OK": "Baptist General Convention of Oklahoma",
    "OR": "Oregon Baptist Convention",
    "PA": "Baptist Convention of Pennsylvania/South Jersey",
    "RI": "Baptist Convention of New England",
    "SC": "South Carolina Baptist Convention",
    "SD": "South Dakota Baptist Convention",
    "TN": "Tennessee Baptist Mission Board",
    "TX": "Southern Baptists of Texas Convention",
    "UT": "Utah-Idaho Southern Baptist Convention",
    "VT": "Baptist Convention of New England",
    "VA": "Southern Baptist Conservatives of Virginia",
    "WA": "Northwest Baptist Convention",
    "WV": "West Virginia Convention of Southern Baptists",
    "WI": "Minnesota-Wisconsin Southern Baptist Convention",
    "WY": "Wyoming Southern Baptist Convention",
}

SBC_CONVENTION_WEBSITES = {
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

def phase2_map_sbc():
    """Map SBC churches to their state conventions based on state field."""
    log("Phase 2: Mapping SBC churches to state conventions...")
    db = get_db()
    cur = db.cursor()
    
    # Count SBC churches per state
    cur.execute("""
        SELECT state, COUNT(*) FROM churches 
        WHERE denomination LIKE '%Southern Baptist%'
          AND state != '' AND state IS NOT NULL
        GROUP BY state ORDER BY COUNT(*) DESC
    """)
    state_counts = cur.fetchall()
    log(f"  SBC churches with state: {sum(c for _, c in state_counts)}")
    
    updated = 0
    no_map = 0
    for state, cnt in state_counts:
        if state in SBC_STATE_CONVENTIONS:
            convention_name = SBC_STATE_CONVENTIONS[state]
            cur.execute("""
                UPDATE churches SET association=? 
                WHERE denomination LIKE '%Southern Baptist%' 
                  AND state=? AND state!='' AND state IS NOT NULL
                  AND (association='' OR association IS NULL)
            """, (convention_name, state))
            updated += cur.rowcount
        else:
            no_map += cnt
    
    db.commit()
    log(f"  Updated {updated} SBC churches with state convention info")
    
    # Also update the convention lookup records themselves
    for state, conv_name in SBC_STATE_CONVENTIONS.items():
        # Check if we have a record for this convention
        for variant in [conv_name, conv_name.replace("Mission Board", "Convention").replace("Board", "Convention")]:
            cur.execute("""
                UPDATE churches SET org_type='state_convention', denom_region=?
                WHERE name LIKE ? AND (org_type='church' OR org_type IS NULL)
            """, (state, f"%{variant[:30]}%"))
    
    db.commit()
    db.close()
    log(f"  Mapped {updated} SBC churches across {len([s for s,c in state_counts if s in SBC_STATE_CONVENTIONS])} states")

# ═══════════════════════════════════════════════════════════════
# PHASE 3: Scrape office websites for member directories
# ═══════════════════════════════════════════════════════════════

def try_scrape_convention_page(url, org_name, org_type):
    """Try to scrape a convention/association website for church directory links."""
    results = []
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=15) as f:
            html = f.read().decode("utf-8", "replace")
        
        # Look for church directory links
        church_links = []
        
        # Pattern: links containing "church" in text
        for m in re.finditer(r'<a[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html, re.IGNORECASE):
            href = m.group(1).strip()
            text = m.group(2).strip()
            if text and ("church" in text.lower() or "churches" in text.lower()):
                church_links.append((text, href))
        
        # Look for directory pages
        dir_links = []
        for m in re.finditer(r'<a[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html, re.IGNORECASE):
            href = m.group(1).strip()
            text = m.group(2).strip().lower()
            if any(kw in text for kw in ["directory", "churches", "find a church", "locations", 
                                           "congregations", "member", "our churches"]):
                dir_links.append((m.group(2).strip(), href))
        
        return {
            "success": True,
            "church_links": church_links[:20],
            "dir_links": dir_links[:10],
            "title": (re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE) or [None, "unknown"])[1],
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}

def phase3_scrape():
    """Scrape office websites for member directories."""
    log("Phase 3: Scraping admin office websites...")
    db = get_db()
    cur = db.cursor()
    
    # Get offices with websites
    cur.execute("""
        SELECT id, name, website, org_type FROM churches 
        WHERE org_type IN ('convention', 'diocese', 'archdiocese', 'synod', 
                           'presbytery', 'conference', 'mission_board')
          AND website != '' AND website IS NOT NULL
          AND website NOT LIKE '%facebook%'
    """)
    offices = cur.fetchall()
    log(f"  Found {len(offices)} admin offices with websites to check")
    
    for oid, name, website, otype in offices[:30]:  # Limit to 30 for now
        result = try_scrape_convention_page(website, name, otype)
        if result["success"]:
            log(f"  OK: {name[:40]:40s} | dir_links={len(result['dir_links'])} church_links={len(result['church_links'])}")
            # Save result to a JSON file for later processing
        else:
            log(f"  FAIL: {name[:40]:40s} | {result.get('error','')}")
        time.sleep(1.0)
    
    db.close()

# ═══════════════════════════════════════════════════════════════
# PHASE 4: Link churches to parent bodies (Catholic, etc.)
# ═══════════════════════════════════════════════════════════════

# Known Catholic diocese mappings (state → diocese)
CATHOLIC_DIOCESES_BY_STATE = {
    "AL": ["Diocese of Birmingham", "Diocese of Mobile"],
    "AK": ["Archdiocese of Anchorage-Juneau", "Diocese of Fairbanks"],
    "AZ": ["Diocese of Phoenix", "Diocese of Tucson"],
    "AR": ["Diocese of Little Rock"],
    "CA": ["Archdiocese of Los Angeles", "Archdiocese of San Francisco", 
           "Diocese of Fresno", "Diocese of Monterey", "Diocese of Oakland",
           "Diocese of Orange", "Diocese of Sacramento", "Diocese of San Bernardino",
           "Diocese of San Diego", "Diocese of San Jose", "Diocese of Santa Rosa",
           "Diocese of Stockton"],
    "CO": ["Archdiocese of Denver", "Diocese of Colorado Springs", "Diocese of Pueblo"],
    "CT": ["Archdiocese of Hartford", "Diocese of Bridgeport", "Diocese of Norwich"],
    # ... could expand but this gives the idea
}

def phase4_link():
    """Link churches to parent bodies using known mappings + scraped data."""
    log("Phase 4: Linking churches to parent bodies...")
    db = get_db()
    cur = db.cursor()
    
    # Already done in phase2 for SBC
    
    # For Catholic churches, try to link by state
    cur.execute("""
        UPDATE churches SET diocese='Roman Catholic Diocese (see state)'
        WHERE denomination='Roman Catholic Church'
          AND (diocese='' OR diocese IS NULL)
          AND state != '' AND state IS NOT NULL
    """)
    catholic_linked = cur.rowcount
    db.commit()
    log(f"  Marked {catholic_linked} Catholic churches for diocese assignment")
    
    db.close()

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else ["--all"]
    
    if "--tag-only" in args:
        phase1_tag()
    elif "--map-sbc" in args:
        phase2_map_sbc()
    elif "--scrape" in args:
        phase3_scrape()
    elif "--link" in args:
        phase4_link()
    else:  # --all
        log("Starting full tagging + hierarchy pipeline")
        phase1_tag()
        phase2_map_sbc()
        phase3_scrape()
        phase4_link()
        log("All phases complete!")

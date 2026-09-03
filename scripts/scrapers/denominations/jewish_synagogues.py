#!/usr/bin/env python3
"""
Jewish Congregation Scraper
============================
Scrapes Jewish congregations from online directories across all major movements.

Sources:
  - URJ (Reform):      urj.org/urj-congregations-communities   ~850 congregations
  - Chabad:            chabad.org/jewish-centers/{state}.htm   ~3,500 centers
  - USCJ (Conservative): uscj.org/network                      ~600 congregations
  - OU (Orthodox):     ou.org/synagogue-finder/                ~1,000 congregations

Usage:
    python scripts/scrapers/scrape_jewish.py
    python scripts/scrapers/scrape_jewish.py --source urj
    python scripts/scrapers/scrape_jewish.py --workers 4
    python scripts/scrapers/scrape_jewish.py --dry-run
"""
import csv, json, os, re, sqlite3, sys, urllib.request, urllib.parse, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import argparse

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DELAY = 0.3

STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
          "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
          "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
          "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
          "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]

STATES_FULL = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
    "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa",
    "KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland",
    "MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi",
    "MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire",
    "NJ":"New Jersey","NM":"New Mexico","NY":"New York","NC":"North Carolina",
    "ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania",
    "RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota","TN":"Tennessee",
    "TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington",
    "WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming",
}

# Movement labels
MOVEMENT = {
    "urj": "Reform",
    "uscj": "Conservative",
    "ou": "Orthodox",
    "chabad": "Chabad",
}


def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))


def fetch(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except Exception as e:
        log("  FETCH ERROR %s: %s" % (url[:80], e))
        return None


# ═══════════════════════════════════════════════════════════════════
# URJ (Reform) — urj.org/urj-congregations-communities
# ═══════════════════════════════════════════════════════════════════
def scrape_urj():
    """Scrape URJ Reform congregations from directory."""
    log("=== URJ (Reform) ===")
    results = []
    page = 0
    has_more = True
    
    while has_more:
        url = "https://urj.org/urj-congregations-communities"
        if page > 0:
            url += "?page=%d" % page
        html = fetch(url)
        if not html:
            break
        
        # Find congregation cards
        # Each card has: h3 with name, address text, website link
        # Pattern: <h3><a href="/congregations/...">NAME</a></h3>
        blocks = re.findall(
            r'<h3[^>]*><a[^>]*href="(/congregations/[^"]+)"[^>]*>([^<]+)</a></h3>\s*'
            r'<[^>]*>([^<]*)</[^>]*>\s*'  # address line
            r'(?:<a[^>]*href="(https?://[^"]+)"[^>]*>)?',  # optional website
            html, re.DOTALL
        )
        
        if not blocks:
            # Try alternative parsing
            blocks = re.findall(
                r'heading[^>]*>([^<]+)</h[^>]*>.*?'
                r'(?:PO Box|Suite|Drive|Street|Road|Ave|Blvd|Lane|Way)[^<]*',
                html, re.DOTALL
            )
            if not blocks:
                log("  Page %d: No more results" % page)
                break
        
        for match in re.finditer(
            r'<h3[^>]*><a[^>]*href="(/congregations/[^"]+)"[^>]*>([^<]+)</a></h3>'
            r'\s*<[^>]*>([^<]*)</[^>]*>'
            r'(?:\s*<a[^>]*href="(https?://[^"]+)"[^>]*>)?',
            html, re.DOTALL
        ):
            slug = match.group(1)
            name = match.group(2).strip()
            addr = match.group(3).strip()
            website = match.group(4).strip() if match.group(4) else ""
            
            # Parse address
            city = state = zipcode = ""
            addr_parts = addr.split(",")
            if len(addr_parts) >= 2:
                city = addr_parts[-2].strip()
                state_zip = addr_parts[-1].strip() if len(addr_parts) > 1 else ""
                m = re.match(r'([A-Z]{2})\s+(\d{5}(?:-\d{4})?)?', state_zip)
                if m:
                    state = m.group(1)
                    zipcode = m.group(2) or ""
            
            results.append({
                "name": name,
                "address": addr,
                "city": city,
                "state": state,
                "zip": zipcode,
                "website": website,
                "source": "urj",
                "movement": "Reform",
            })
        
        # Check if there's a next page
        if 'rel="next"' not in html and 'next' not in html.lower():
            has_more = False
        page += 1
        time.sleep(DELAY)
    
    log("  Found %d URJ congregations" % len(results))
    return results


# ═══════════════════════════════════════════════════════════════════
# Chabad — chabad.org/jewish-centers/{state}.htm
# ═══════════════════════════════════════════════════════════════════
def scrape_chabad(workers=4):
    """Scrape Chabad centers from state-level directory pages."""
    log("=== Chabad ===")
    
    def fetch_state(st):
        state_full = STATES_FULL.get(st, st)
        url = "https://www.chabad.org/jewish-centers/%s.htm" % state_full
        html = fetch(url)
        if not html:
            log("  %s: No data" % st)
            return []
        
        state_results = []
        
        # Try JSON-LD data first
        json_blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            html, re.DOTALL
        )
        for jb in json_blocks:
            try:
                data = json.loads(jb)
                if isinstance(data, dict) and data.get("@type") in ("Place", "LocalBusiness"):
                    state_results.append(_parse_chabad_json(data, st))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") in ("Place", "LocalBusiness"):
                            state_results.append(_parse_chabad_json(item, st))
            except:
                pass
        
        # If JSON-LD didn't yield results, try HTML parsing
        if not state_results:
            # Look for center listings in the page
            # Chabad pages often have cards with name, address, link
            for m in re.finditer(
                r'<a[^>]*href="(/[^"]*center[^"]*)"[^>]*>([^<]+)</a>',
                html, re.IGNORECASE
            ):
                center_url = "https://www.chabad.org" + m.group(1)
                center_name = m.group(2).strip()
                state_results.append({
                    "name": center_name,
                    "website": center_url,
                    "state": st,
                    "source": "chabad",
                    "movement": "Chabad",
                })
        
        if not state_results:
            log("  %s: %d from JSON-LD" % (st, len(state_results)))
        else:
            log("  %s: %d found" % (st, len(state_results)))
        time.sleep(DELAY)
        return state_results
    
    all_results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_state, st): st for st in STATES}
        for f in as_completed(futures):
            try:
                all_results.extend(f.result())
            except Exception as e:
                log("  Worker error for %s: %s" % (futures[f], e))
    
    log("  Found %d Chabad centers total" % len(all_results))
    return all_results


def _parse_chabad_json(data, state):
    """Parse a Chabad JSON-LD entry."""
    name = data.get("name", "")
    addr = data.get("address", {})
    if isinstance(addr, dict):
        street = addr.get("streetAddress", "")
        city = addr.get("addressLocality", "")
        st = addr.get("addressRegion", state)
        zipcode = addr.get("postalCode", "")
    else:
        street = city = st = zipcode = ""
    
    geo = data.get("geo", {})
    lat = geo.get("latitude") if isinstance(geo, dict) else None
    lng = geo.get("longitude") if isinstance(geo, dict) else None
    
    url = data.get("url", "")
    
    return {
        "name": name,
        "address": street,
        "city": city,
        "state": st,
        "zip": zipcode,
        "website": url,
        "latitude": lat,
        "longitude": lng,
        "source": "chabad",
        "movement": "Chabad",
    }


# ═══════════════════════════════════════════════════════════════════
# USCJ (Conservative) — uscj.org/network
# ═══════════════════════════════════════════════════════════════════
def scrape_uscj():
    """Scrape USCJ Conservative congregations."""
    log("=== USCJ (Conservative) ===")
    results = []
    
    # USCJ network page uses a search/API approach
    # Try the main network page first
    html = fetch("https://uscj.org/network")
    if html:
        # Look for congregation listings in the page
        for m in re.finditer(
            r'<a[^>]*href="(/congregations/[^"]+)"[^>]*>([^<]+)</a>',
            html, re.IGNORECASE
        ):
            slug = m.group(1)
            name = m.group(2).strip()
            results.append({
                "name": name,
                "website": "https://uscj.org" + slug,
                "source": "uscj",
                "movement": "Conservative",
            })
    
    # Try the member lounge API if available
    # USCJ also has a finder API at /find/congregations
    api_urls = [
        "https://uscj.org/find/congregations",
        "https://uscj.org/api/congregations",
    ]
    for api_url in api_urls:
        api_html = fetch(api_url)
        if api_html:
            try:
                data = json.loads(api_html)
                if isinstance(data, list):
                    for item in data:
                        results.append({
                            "name": item.get("title", item.get("name", "")),
                            "address": item.get("address", ""),
                            "city": item.get("city", ""),
                            "state": item.get("state", ""),
                            "zip": item.get("zip", ""),
                            "website": item.get("url", item.get("website", "")),
                            "source": "uscj",
                            "movement": "Conservative",
                        })
                break
            except:
                pass
    
    log("  Found %d USCJ congregations" % len(results))
    return results


# ═══════════════════════════════════════════════════════════════════
# OU (Orthodox) — ou.org/synagogue-finder/
# ═══════════════════════════════════════════════════════════════════
def scrape_ou():
    """Scrape OU Orthodox synagogues."""
    log("=== OU (Orthodox) ===")
    results = []
    
    # OU's synagogue finder uses a search interface
    # Try the API endpoint if available
    api_url = "https://www.ou.org/wp-json/ou/v1/synagogues"
    html = fetch(api_url)
    if html:
        try:
            data = json.loads(html)
            if isinstance(data, list):
                for item in data:
                    results.append({
                        "name": item.get("title", item.get("name", "")),
                        "address": item.get("address", ""),
                        "city": item.get("city", ""),
                        "state": item.get("state", ""),
                        "zip": item.get("zip", ""),
                        "website": item.get("url", item.get("website", "")),
                        "source": "ou",
                        "movement": "Orthodox",
                    })
        except:
            pass
    
    # Also try the synagogue finder page
    html = fetch("https://www.ou.org/synagogue-finder/")
    if html:
        # Look for JSON data embedded in the page
        for m in re.finditer(r'var\s+synagogues\s*=\s*(\[.*?\]);', html, re.DOTALL):
            try:
                data = json.loads(m.group(1))
                for item in data:
                    results.append({
                        "name": item.get("name", ""),
                        "city": item.get("city", ""),
                        "state": item.get("state", ""),
                        "zip": item.get("zip", ""),
                        "website": item.get("url", ""),
                        "source": "ou",
                        "movement": "Orthodox",
                    })
            except:
                pass
    
    if not results:
        log("  OU API returned no data (may need JS rendering)")
    
    log("  Found %d OU synagogues" % len(results))
    return results


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════
def save_results(results, filename):
    """Save results to CSV and return unique records."""
    seen = set()
    unique = []
    for r in results:
        key = (r["name"].upper(), r.get("city", "").upper(), r.get("state", ""))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    fp = os.path.join(OUT_DIR, filename)
    with open(fp, "w", newline="", encoding="utf-8") as f:
        if unique:
            writer = csv.DictWriter(f, fieldnames=unique[0].keys())
            writer.writeheader()
            writer.writerows(unique)
    log("  Saved %d unique records to %s" % (len(unique), fp))
    return unique


def import_to_db(results):
    """Insert Jewish congregations into churches.db."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check which columns exist
    cols = {r[1] for r in cur.execute("PRAGMA table_info(churches)").fetchall()}
    
    inserted = 0
    skipped = 0
    for r in results:
        name = r["name"]
        city = r.get("city", "")
        state = r.get("state", "")
        website = r.get("website", "")
        
        if not name or not state:
            continue
        
        # Check for existing by name+city+state
        existing = cur.execute(
            "SELECT id FROM churches WHERE UPPER(name)=? AND UPPER(city)=? AND state=?",
            (name.upper(), city.upper(), state)
        ).fetchone()
        
        if existing:
            # Update existing record with website/denom info if missing
            if website and "website" in cols:
                cur.execute(
                    "UPDATE churches SET website=COALESCE(NULLIF(website,''),?), "
                    "denomination=COALESCE(NULLIF(denomination,''),?), "
                    "faith_tradition='jewish', "
                    "jewish_movement=COALESCE(NULLIF(jewish_movement,''),?), "
                    "source=COALESCE(NULLIF(source,''),'jewish_scrape') "
                    "WHERE id=? AND (website IS NULL OR website='')",
                    (website, r.get("movement", "Jewish"), r.get("movement", ""), existing[0])
                )
            skipped += 1
        else:
            # Insert new record
            cols_list = ["name", "city", "state", "source", "faith_tradition", "jewish_movement", "notes"]
            vals_list = [
                name, city, state, "jewish_scrape", "jewish",
                r.get("movement", "Jewish"),
                "Source: %s" % r.get("source", "")
            ]
            
            if website and "website" in cols:
                cols_list.append("website")
                vals_list.append(website)
            if r.get("address") and "address" in cols:
                cols_list.append("address")
                vals_list.append(r.get("address", ""))
            if r.get("zip") and "zip" in cols:
                cols_list.append("zip")
                vals_list.append(r.get("zip", ""))
            if r.get("latitude") and "latitude" in cols:
                cols_list.append("latitude")
                vals_list.append(r.get("latitude"))
            if r.get("longitude") and "longitude" in cols:
                cols_list.append("longitude")
                vals_list.append(r.get("longitude"))
            
            placeholders = ",".join("?" for _ in vals_list)
            try:
                cur.execute(
                    "INSERT INTO churches (%s) VALUES (%s)" % (",".join(cols_list), placeholders),
                    vals_list
                )
                inserted += 1
            except Exception as e:
                log("  INSERT ERROR: %s - %s" % (name[:50], e))
    
    conn.commit()
    conn.close()
    log("  DB: %d inserted, %d updated/skipped" % (inserted, skipped))


def main():
    parser = argparse.ArgumentParser(description="Jewish congregation scraper")
    parser.add_argument("--source", choices=["all", "urj", "chabad", "uscj", "ou"],
                        default="all", help="Source to scrape")
    parser.add_argument("--workers", type=int, default=4,
                        help="Worker threads for parallel scraping")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't write to DB, just save CSV")
    parser.add_argument("--import-only", action="store_true",
                        help="Import existing CSV to DB without scraping")
    args = parser.parse_args()
    
    if args.import_only:
        # Import existing CSV
        results = []
        for fname in ["jewish_urj.csv", "jewish_chabad.csv", "jewish_uscj.csv", "jewish_ou.csv"]:
            fp = os.path.join(OUT_DIR, fname)
            if os.path.exists(fp):
                with open(fp, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    results.extend(list(reader))
                log("Loaded %s records from %s" % (len(results), fname))
        if results:
            import_to_db(results)
        return
    
    all_results = []
    sources = ["urj", "chabad", "uscj", "ou"] if args.source == "all" else [args.source]
    
    for src in sources:
        if src == "urj":
            r = scrape_urj()
            save_results(r, "jewish_urj.csv")
            all_results.extend(r)
        elif src == "chabad":
            r = scrape_chabad(workers=args.workers)
            save_results(r, "jewish_chabad.csv")
            all_results.extend(r)
        elif src == "uscj":
            r = scrape_uscj()
            save_results(r, "jewish_uscj.csv")
            all_results.extend(r)
        elif src == "ou":
            r = scrape_ou()
            save_results(r, "jewish_ou.csv")
            all_results.extend(r)
    
    # Save combined
    combined = save_results(all_results, "jewish_all.csv")
    
    log("\n=== Summary ===")
    log("  Total unique congregations: %d" % len(combined))
    
    if not args.dry_run and combined:
        import_to_db(combined)
    
    log("Done!")


if __name__ == "__main__":
    main()
